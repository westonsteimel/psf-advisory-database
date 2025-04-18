"""Tool which imports OSV data from PSF CVE Numbering Authority CVEs"""

import copy
import json
import os
import re
import typing
from pathlib import Path

import cvelib.cve_api
import osv_utils
import urllib3

ADVISORIES_DIR = Path(__file__).parent.parent / "advisories"
CVE_API_TOKEN = os.environ["CVE_API_TOKEN"]
CVE_USERNAME = os.environ["CVE_USERNAME"]
CVE_ENV = os.environ.get("CVE_ENV", "prod")

HTTP = urllib3.PoolManager()
CVE_API = cvelib.cve_api.CveApi(
    org="PSF",
    username=CVE_USERNAME,
    api_key=CVE_API_TOKEN,
    env=CVE_ENV,
)


def main():
    for cve_id, cve_record in published_cpython_cves():
        update_osv_from_cve(cve_id, cve_record)


def published_cpython_cves() -> typing.Iterable[tuple[str, dict[str, typing.Any]]]:
    """Iterate over the list of published CVEs for CPython"""

    for cve_ref in CVE_API.list_cves(state="PUBLISHED"):
        cve_id = cve_ref["cve_id"]
        cve_record = CVE_API.show_cve_record(cve_id)

        # Skip non-CPython CVEs
        if not any(
            affected["product"] == "CPython"
            for affected in cve_record["containers"]["cna"]["affected"]
        ):
            continue

        yield cve_id, cve_record


def update_osv_from_cve(cve_id: str, cve_record: dict[str, typing.Any]) -> None:
    osv_id = osv_utils.get_osv_id(
        "python", lambda osv: cve_id in osv.get("aliases", ())
    )

    # If this is a new OSV record then we rely on the allocator.
    if not osv_id:
        osv_id = f"PSF-0000-{cve_id}"
        osv_json = {
            "schema_version": "1.5.0",
            "id": osv_id,
            "aliases": [cve_id],
        }

    # Otherwise we can load the existing OSV record
    else:
        osv_json = json.loads((ADVISORIES_DIR / f"python/{osv_id}.json").read_text())

    # Keep track of the existing JSON, so we don't end up updating the file
    # with noisy formatting changes. Unfortunately some OSV tooling is opinionated about formatting.
    existing_osv_json = copy.deepcopy(osv_json)

    # Start updating the OSV record with CVE record data.
    cve_cna = cve_record["containers"]["cna"]
    cve_meta = cve_record["cveMetadata"]

    details = None
    if "descriptions" in cve_cna:
        assert cve_cna["descriptions"][0]["lang"] == "en"
        details = cve_cna["descriptions"][0]["value"]

    cwe_ids = []
    for problem_type in cve_cna.get("problemTypes", []):
        cwe_ids.extend(problem_type.get("cwdId", []))

    git_commit_re = re.compile(
        r"https://github.com/python/cpython/commit/([a-f0-9]{20,})"
    )
    fixed_events = []
    references = []
    for ref in cve_cna["references"]:
        ref_tags = ref.get("tags", ())
        ref_type = "WEB"  # Default reference type for OSV.

        if "patch" in ref_tags and (
            match := git_commit_re.search(
                ref["url"],
            )
        ):
            ref_type = "FIX"
            fixed_events.append({"fixed": match.group(1)})
        elif "vendor-advisory" in ref_tags:
            ref_type = "ADVISORY"
        elif "issue-tracking" in ref_tags:
            ref_type = "REPORT"
        references.append({"type": ref_type, "url": ref["url"]})

    # Find if there's an existing 'introduced' event. We assume
    # a single 'affected' and 'ranges' entry in an OSV record.
    introduced_event = {"introduced": "0"}
    if len(osv_json.get("affected", [])) == 1:
        assert len(osv_json["affected"][0]["ranges"]) == 1
        osv_range = osv_json["affected"][0]["ranges"][0]
        assert osv_range["type"] == "GIT"
        assert osv_range["repo"] == "https://github.com/python/cpython"
        for osv_range_event in osv_range["events"]:
            if "introduced" in osv_range_event:
                introduced_event = osv_range_event
                break

    osv_json.update(
        {
            "published": f"{cve_meta['datePublished'].rstrip('Z')}Z",
            "modified": f"{cve_meta['dateUpdated'].rstrip('Z')}Z",
            "details": details,
            "affected": [
                {
                    "ranges": [
                        {
                            "type": "GIT",
                            "events": [introduced_event, *fixed_events],
                            "repo": "https://github.com/python/cpython",
                        }
                    ]
                }
            ],
            "references": references,
            "database_specific": {"cwe_ids": cwe_ids},
        }
    )

    def without_timestamps(value):
        """
        Helper that strips the timestamps from OSV records,
        which can change on CVEs from other data providers.
        """
        new_value = copy.deepcopy(value)
        new_value.pop("published", None)
        new_value.pop("modified", None)
        return new_value

    # Only update if there's data differences, not timestamp differences.
    if without_timestamps(existing_osv_json) != without_timestamps(osv_json):
        with (ADVISORIES_DIR / f"python/{osv_id}.json").open("w") as f:
            f.truncate()
            f.write(json.dumps(osv_json, indent=2))


if __name__ == "__main__":
    main()
