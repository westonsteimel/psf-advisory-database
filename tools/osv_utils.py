"""Utility to update an OSV record with partial data"""

import json
import re
import typing
from collections import OrderedDict
from pathlib import Path

import packaging.version

ADVISORIES_DIR = Path(__file__).parent.parent / "advisories"
HISTORICAL_ADVISORIES_DIR = Path(__file__).parent.parent / "historical-advisories"

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
    "schema_version": OSV_SCHEMA_VERSION,
    "affected": [
        {
            "ranges": [],
        }
    ],
    "references": [],
    "database_specific": {"cwe_ids": []},
}
PRODUCT_TO_REPO = {
    "python": "https://github.com/python/cpython",
    "pip": "https://github.com/pypa/pip",
}


def update_osv_record(
    *,
    product: str,
    cve_id: str,
    historical: bool = False,
    summary: str | None = None,
    details: str | None = None,
    published: str | None = None,
    modified: str | None = None,
    cwe_ids: None | list[str] = None,
    affected_ranges_git: None | list[tuple[str, str]] = None,
    affected_ranges_ecosystem: None | list[tuple[str, str]] = None,
):
    base_dir = HISTORICAL_ADVISORIES_DIR if historical else ADVISORIES_DIR
    osv_filepath = base_dir / product / f"{cve_id}.json"
    try:
        with osv_filepath.open(mode="r") as f:
            osv = json.loads(f.read())
    except FileNotFoundError:
        osv = OSV_TEMPLATE.copy()

    # Projects that aren't a part of a packaging ecosystem
    # shouldn't set a 'affected[].package' field.
    if osv_package := PRODUCT_TO_OSV_PACKAGE[product]:
        if osv_package is None:
            osv["affected"][0]["package"] = osv_package
    else:
        osv["affected"][0].pop("package", None)

    # Merge the new data into the existing OSV. Don't overwrite existing values.
    osv["id"] = cve_id
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

        git_range["events"] = [
            {key: val}
            for key, val in sorted(set(current_events) | set(affected_ranges_git))
        ]

    if affected_ranges_ecosystem:
        ecosystem_range = get_osv_range(
            osv,
            range_type="ECOSYSTEM",
            range_default={"type": "ECOSYSTEM", "events": []},
        )
        current_events = [list(event.items())[0] for event in ecosystem_range["events"]]
        new_events = set(current_events) | set(affected_ranges_ecosystem)

        # If there's no 'introduced' key we add an ('introduced', '0.0.0')
        if not any(action == "introduced" for action, _ in new_events):
            new_events.add(("introduced", "0.0.0"))

        def ecosystem_sort_key(action_and_version):
            action, version = action_and_version
            # Ties on the version will go to whether the action is 'fixed' or 'introduced'.
            # We want 'fixed' to always go after 'introduced'.
            return (packaging.version.Version(version), action == "fixed")

        ecosystem_range["events"] = [
            {key: val} for key, val in sorted(new_events, key=ecosystem_sort_key)
        ]

    write_osv_record(osv=osv, filepath=osv_filepath)


def write_osv_record(*, osv: dict[str, typing.Any], filepath: Path):
    with filepath.open(mode="w") as f:
        f.truncate()
        f.write(
            sorted_json_dumps(
                osv,
                keys=[
                    "schema_version",
                    "id",
                    "modified",
                    "published",
                    "withdrawn",
                    "aliases",
                    "related",
                    "summary",
                    "details",
                    "severity",
                    "affected",
                    "references",
                    "credits",
                    "timeline",
                    "database_specific",
                ],
            )
        )


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


def sorted_json_dumps(value, keys):
    """Lets us be picky about the top-level keys in the JSON structure :)"""
    dct = OrderedDict(
        sorted(
            value.items(),
            key=lambda kv: (keys.index(kv[0]), kv[0])
            if kv[0] in keys
            else (len(keys) + 1, kv[0]),
        )
    )
    return json.dumps(dct, indent=2)
