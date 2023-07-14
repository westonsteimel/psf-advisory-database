"""Utility to update an OSV record with partial data"""

import json
import re
import typing
from collections import OrderedDict
from pathlib import Path

historical_advisories_dir = Path(__file__).parent.parent / "historical-advisories"
product_to_osv_package = {
    "python": {
        "ecosystem": "generic",
        "name": "Python",
        "purl": "pkg:generic/python",
    },
    "pip": {
        "ecosystem": "generic",
        "name": "pip",
        "purl": "pkg:pypi/pip",
    },
}
osv_template = {
    "schema_version": "1.5.0",
    "affected": [
        {
            "ranges": [],
        }
    ],
    "references": [],
    "database_specific": {"cwe_ids": []},
}


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


def update_osv_record(
    *,
    product: str,
    cve_id: str,
    details: str | None = None,
    published: str | None = None,
    modified: str | None = None,
    cwe_ids: None | list[str] = None,
    affected_ranges_git: None | list[tuple[str, str]] = None,
    affected_ranges_semver: None | list[tuple[str, str]] = None,
):
    osv_filepath = historical_advisories_dir / product / f"{cve_id}.json"
    try:
        with osv_filepath.open(mode="r") as f:
            osv = json.loads(f.read())
    except FileNotFoundError:
        osv = osv_template.copy()
    osv["affected"][0]["package"] = product_to_osv_package[product]

    # Merge the CVE JSON into the OSV value. Don't overwrite existing values.
    osv["id"] = cve_id
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
        ranges = osv["affected"][0]["ranges"]
        git_ranges = [range_ for range_ in ranges if range_["type"] == "GIT"]
        if not git_ranges:
            git_range = {"type": "GIT", "events": []}
            ranges.append(git_range)
        else:
            assert len(git_ranges) == 1
            git_range = git_ranges[0]
        current_events = [list(event.items())[0] for event in git_range["events"]]
        git_range["events"] = [
            {key: val}
            for key, val in sorted(set(current_events) | set(affected_ranges_git))
        ]

    with osv_filepath.open(mode="w") as f:
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
                    "database_specific",
                ],
            )
        )
