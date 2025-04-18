"""Utility to update an OSV record with partial data"""

import copy
import datetime
import json
import os
import re
import secrets
import typing
from pathlib import Path

import packaging.version

NOW_UTC = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
ADVISORIES_DIR = Path(__file__).parent.parent / "advisories"

OSV_SCHEMA_VERSION = "1.5.0"
PRODUCT_TO_OSV_PACKAGE = {
    "python": None,
    "pip": {
        "ecosystem": "generic",
        "name": "pip",
        "purl": "pkg:pypi/pip",
    },
}
OSV_TEMPLATE = {
    "modified": NOW_UTC,
    "published": NOW_UTC,
    "schema_version": OSV_SCHEMA_VERSION,
    "id": None,
    "aliases": [],
    "affected": [
        {
            "ranges": [],
        }
    ],
    "references": [],
    "credits": [],
    "database_specific": {"cwe_ids": []},
}
PRODUCT_TO_REPO = {
    "python": "https://github.com/python/cpython",
    "pip": "https://github.com/pypa/pip",
}


def get_osv_id(
    product: str, condition: typing.Callable[[typing.Any], bool]
) -> str | None:
    """Lookup an OSV by a defined condition"""
    osv_filedir = ADVISORIES_DIR / product
    for osv_filename in os.listdir(osv_filedir):
        osv = json.loads((osv_filedir / osv_filename).read_text())
        if condition(osv):
            return osv["id"]
    return None


def update_osv_record(
    *,
    product: str,
    cve_id: str | None = None,
    osv_id: str | None = None,
    summary: str | None = None,
    details: str | None = None,
    published: str | None = None,
    modified: str | None = None,
    cwe_ids: None | list[str] = None,
    affected_ranges_git: None | list[tuple[str, str]] = None,
    references: None | list[tuple[str, str]] = None,
):
    osv_filedir = ADVISORIES_DIR / product
    if osv_id is not None and cve_id is not None:
        raise ValueError("Must provide one of either 'cve_id' or 'osv_id'")

    # Look for an existing advisory that references the CVE
    elif cve_id is not None:
        osv_id = get_osv_id(
            product=product, condition=lambda osv: cve_id in osv.get("aliases", [])
        )

    # If we can't find one, we allocate a new ID.
    if osv_id is None:
        osv_id = f"PSF-0000-{secrets.token_hex(8)}"

    osv_filepath = osv_filedir / f"{osv_id}.json"
    try:
        with osv_filepath.open(mode="r") as f:
            osv = json.loads(f.read())
        original_osv = copy.deepcopy(osv)
    except FileNotFoundError:
        osv = copy.deepcopy(OSV_TEMPLATE)
        original_osv = {}

    # Projects that aren't a part of a packaging ecosystem
    # shouldn't set a 'affected[].package' field.
    if osv_package := PRODUCT_TO_OSV_PACKAGE[product]:
        if osv_package is None:
            osv["affected"][0]["package"] = osv_package
    else:
        osv["affected"][0].pop("package", None)

    # Merge the new data into the existing OSV. Don't overwrite existing values.
    osv["id"] = osv_id
    if cve_id:
        osv["aliases"] = sorted(set(osv.get("aliases", ())) | {cve_id})
    if summary:
        osv.setdefault("summary", summary)
    if details:
        osv.setdefault("details", details)
    if published:
        if "published" in osv:
            osv["published"] = min(osv["published"], published)
        else:
            osv["published"] = published
    if modified:
        if "modified" in osv:
            osv["modified"] = max(osv["modified"], modified)
        else:
            osv["modified"] = modified

    if references:
        current_refs = [(ref["type"], ref["url"]) for ref in osv.get("references", [])]
        new_refs = set(current_refs) | set(references)

        # Remove duplicated type=WEB references. Prefer the non-WEB type.
        non_web_urls = [url for type_, url in new_refs if type_ != "WEB"]

        osv["references"] = [
            {"type": type_, "url": url}
            for type_, url in sorted(new_refs)
            # This is where the de-duplication of type=WEB URLs happens.
            if type_ != "WEB" or url not in non_web_urls
        ]

    if cwe_ids:
        osv["database_specific"]["cwe_ids"] = natsort(
            set(cwe_ids) | set(osv["database_specific"]["cwe_ids"])
        )

    if affected_ranges_git:
        git_repo = PRODUCT_TO_REPO[product]
        git_range = get_osv_range(
            osv,
            range_type="GIT",
            range_default={"type": "GIT", "events": [], "repo": git_repo},
        )
        current_events = [list(event.items())[0] for event in git_range["events"]]
        new_events = set(current_events) | set(affected_ranges_git)

        # If there's no explicit 'introduced' event we add one to show that
        # all commits not explicitly fixed are affected.
        if not any(action == "introduced" for action, _ in new_events):
            new_events.add(("introduced", "0"))

        git_range["events"] = [
            {key: val}
            for key, val in sorted(
                new_events, key=lambda kv: (kv[0] != "introduced",) + kv
            )
        ]

    # Update the modified time if the content has changed at all.
    # This check means we don't update the modified time for formatting.
    # We use the global 'NOW_UTC' because then all modified records will be
    # a part of the same batch instead of distinct per record.
    if original_osv != osv:
        osv["modified"] = NOW_UTC

    with osv_filepath.open(mode="w") as f:
        f.truncate()
        f.write(json.dumps(osv, indent=2))


def get_osv_range(osv, *, range_type: str, range_default: typing.Any) -> typing.Any:
    """Find a range within the 'affected[0].ranges that matches the type,
    otherwise create one and modified the 'osv' structure passed to the function
    then pull out the individual events to be used (if any!)
    """
    ranges = osv["affected"][0]["ranges"]
    ranges_of_type = [range_ for range_ in ranges if range_["type"] == range_type]
    if not ranges_of_type:
        range_of_type = range_default
        ranges.append(range_of_type)
    else:
        assert len(ranges_of_type) == 1
        range_of_type = ranges_of_type[0]

    # A few assertations to ensure that the default range is okay!
    assert range_of_type["type"] == range_type
    range_of_type.setdefault("events", [])
    assert isinstance(range_of_type["events"], list)

    # Transform the list of events into key-value pairs.
    return range_of_type


def natsort(items):
    """Natural sorting for identifiers"""
    return sorted(
        items,
        key=lambda x: [
            int(part) if part.isdigit() else part.lower()
            for part in re.split(r"([0-9]+)", x)
        ],
    )
