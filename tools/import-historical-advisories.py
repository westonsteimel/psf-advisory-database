"""Tool which imports data about historical CVEs for scoped projects"""
import re

import urllib3
import yaml
from osv_utils import get_osv_id, natsort, update_osv_record

http = urllib3.PoolManager()

historical_cve_ids = {
    "python": [
        # Manually submitted CVE IDs
        "CVE-2023-33595",
        "CVE-2023-36632",
        "CVE-2022-488565",
        "CVE-2022-488566",
        "CVE-2023-38898",
        "CVE-2022-48560",
        "CVE-2022-48564",
        "CVE-2007-4559",
        # List of CVE IDs was taken from https://github.com/vstinner/python-security
        "CVE-2007-4965",
        "CVE-2008-1679",
        "CVE-2008-1721",
        "CVE-2008-1887",
        "CVE-2008-2315",
        "CVE-2008-2316",
        "CVE-2008-3142",
        "CVE-2008-3143",
        "CVE-2008-3144",
        "CVE-2008-4864",
        "CVE-2008-5031",
        "CVE-2009-4134",
        "CVE-2010-1449",
        "CVE-2010-1450",
        "CVE-2010-1634",
        "CVE-2010-2089",
        "CVE-2010-3492",
        "CVE-2010-3493",
        "CVE-2011-1015",
        "CVE-2011-1521",
        "CVE-2011-3389",
        "CVE-2011-4940",
        "CVE-2011-4944",
        "CVE-2012-0845",
        "CVE-2012-0876",
        "CVE-2012-1150",
        "CVE-2012-2135",
        "CVE-2013-0340",
        "CVE-2013-1752",
        "CVE-2013-1752",
        "CVE-2013-1752",
        "CVE-2013-1752",
        "CVE-2013-1752",
        "CVE-2013-1752",
        "CVE-2013-1753",
        "CVE-2013-2099",
        "CVE-2013-4238",
        "CVE-2013-7040",
        "CVE-2013-7338",
        "CVE-2013-7440",
        "CVE-2014-1912",
        "CVE-2014-2667",
        "CVE-2014-4616",
        "CVE-2014-7185",
        "CVE-2014-9365",
        "CVE-2015-1283",
        "CVE-2015-20107",
        "CVE-2016-0718",
        "CVE-2016-0718",
        "CVE-2016-0772",
        "CVE-2016-2183",
        "CVE-2016-3189",
        "CVE-2016-4472",
        "CVE-2016-5636",
        "CVE-2016-5699",
        "CVE-2016-9063",
        "CVE-2016-9840",
        "CVE-2016-9841",
        "CVE-2016-9842",
        "CVE-2016-9843",
        "CVE-2016-1000110",
        "CVE-2017-9233",
        "CVE-2017-1000158",
        "CVE-2018-1060",
        "CVE-2018-1061",
        "CVE-2018-14647",
        "CVE-2018-20406",
        "CVE-2018-25032",
        "CVE-2018-1000030",
        "CVE-2018-1000117",
        "CVE-2019-5010",
        "CVE-2019-9636",
        "CVE-2019-9740",
        "CVE-2019-9947",
        "CVE-2019-9948",
        "CVE-2019-10160",
        "CVE-2019-12900",
        "CVE-2019-16056",
        "CVE-2019-16935",
        "CVE-2019-18348",
        "CVE-2019-20907",
        "CVE-2020-8315",
        "CVE-2020-8492",
        "CVE-2020-10735",
        "CVE-2020-10735",
        "CVE-2020-14422",
        "CVE-2020-15523",
        "CVE-2020-26116",
        "CVE-2020-27619",
        "CVE-2021-3177",
        "CVE-2021-3426",
        "CVE-2021-3733",
        "CVE-2021-3737",
        "CVE-2021-23336",
        "CVE-2021-28861",
        "CVE-2021-29921",
        "CVE-2022-0391",
        "CVE-2022-37454",
        "CVE-2022-37454",
        "CVE-2022-42919",
        "CVE-2022-42919",
        "CVE-2022-45061",
        "CVE-2022-45061",
        "CVE-2023-24329",
        "CVE-2023-24329",
        "CVE-2023-27043",
        "CVE-2023-27043",
    ],
}


def update_from_cve_database():
    for product, cve_ids in historical_cve_ids.items():
        for cve_id in cve_ids:
            update_from_cve(product=product, cve_id=cve_id)


def update_from_cve(*, product: str, cve_id: str):
    """
    We use the CVE list on GitHub which is synchronized from the CVE
    database without needing a CVE Services account for API access.
    """
    CVE, year, id = cve_id.split("-")
    assert CVE == "CVE", cve_id
    id_prefix = id[:-3] + "xxx"

    # Fetch the CVE JSON from the GitHub mirror.
    resp = http.request(
        "GET",
        f"https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/{year}/{id_prefix}/{cve_id}.json",
    )
    if resp.status == 404:
        return
    assert resp.status == 200, resp.status
    cve_json = resp.json()
    cve_cna = cve_json["containers"]["cna"]
    cve_meta = cve_json["cveMetadata"]

    details = None
    if "descriptions" in cve_cna:
        assert cve_cna["descriptions"][0]["lang"] == "en"
        details = cve_cna["descriptions"][0]["value"]

    cwe_ids = []
    for problem_type in cve_cna.get("problemTypes", []):
        cwe_ids.extend(problem_type.get("cwdId", []))

    update_osv_record(
        product=product,
        cve_id=cve_id,
        published=f"{cve_meta['datePublished']}Z",
        modified=f"{cve_meta['dateUpdated']}Z",
        details=details,
        cwe_ids=cwe_ids,
    )


def update_from_python_security():
    """
    Enriches additional information into the OSV format that is
    missing from the CVE Records like fixed commits and version ranges.
    """
    resp = http.request(
        "GET",
        "https://raw.githubusercontent.com/vstinner/python-security/main/vulnerabilities.yaml",
    )
    data = yaml.load(resp.data, Loader=yaml.SafeLoader)

    for entry in data:
        # Entries can either be a single CVE or a list of CVEs.
        if "cve" in entry and entry["cve"]:
            if isinstance(entry["cve"], str):
                cve_ids = [entry["cve"]]
            else:
                assert isinstance(entry["cve"], list)
                cve_ids = entry["cve"]
        else:
            cve_ids = []

        # The 'fixed-in' field is a mapping of versions to commits.
        # The commit data can be used to figure out exact git tags
        # that the fix landed in.
        affected_ranges_git = []

        # Mapping a minor version to the latest tag/commit SHA
        fixes_per_minor: dict[tuple[int, ...], tuple[tuple[int, ...], str]] = {}

        # Figure out all the places where a fix happened
        # and narrow it down to the ones we will report in OSV.
        for fixed_in in entry.get("fixed-in", []):
            for ver, commit_sha in fixed_in.items():
                # Sometimes fixes came in multiple commits for a single 'minor' version.
                # We should count the latest released version as the actual "fixed" version.
                for tag in commit_sha_to_tags(commit_sha):
                    tag_tuple = tuple(
                        map(
                            int,
                            re.match(r"^([0-9]+)\.([0-9]+)\.([0-9]+)", tag).groups(),
                        )
                    )
                    major_minor = tag_tuple[:2]

                    if (
                        major_minor not in fixes_per_minor
                        or tag_tuple > fixes_per_minor[major_minor][0]
                    ):
                        fixes_per_minor[major_minor] = (tag_tuple, commit_sha)

        # Once we figure out the per-minor version we
        # can publish the collated information.
        for _, commit_sha in fixes_per_minor.values():
            affected_ranges_git.append(("fixed", commit_sha))

        # Links and References
        references = []
        bpo = None
        if "bpo" in entry:
            bpo = int(entry["bpo"])
            references.append(("REPORT", f"https://bugs.python.org/issue{bpo}"))
        if "gh" in entry:
            references.append(
                (
                    "REPORT",
                    f"https://github.com/python/cpython/issues/{int(entry['gh'])}",
                )
            )
        if "links" in entry:
            for link in entry["links"]:
                if isinstance(link, dict) and len(link) == 1:
                    link = list(link.values())[0]
                if not link.startswith("http"):
                    match = re.search(r"(https?://[^<>\s]+)", link)
                    if not match:
                        continue
                    link = match.group(1)
                references.append(("WEB", link))

        # If we don't have any CVE IDs we can try looking up by BPO (bugs.python.org ID)
        osv_id = None
        if not cve_ids and bpo is not None:

            def has_bpo(osv):
                refs = osv.get("references", [])
                return {
                    "type": "REPORT",
                    "url": f"https://bugs.python.org/issue{bpo}",
                } in refs

            osv_id = get_osv_id(product="python", condition=has_bpo)

        for cve_id in cve_ids or (None,):
            update_osv_record(
                product="python",
                osv_id=osv_id,
                cve_id=cve_id,
                summary=entry["name"],
                details=entry["description"],
                affected_ranges_git=affected_ranges_git,
                references=references,
            )


_COMMIT_SHA_TO_TAGS: dict[str, set[str]] = {}


def commit_sha_to_tags(commit_sha: str) -> list[str]:
    """Uses vstinner/python-security's list of commit->tags mapping at commit_tags.txt"""

    global _COMMIT_SHA_TO_TAGS
    if not _COMMIT_SHA_TO_TAGS:
        resp = http.request(
            "GET",
            "https://raw.githubusercontent.com/vstinner/python-security/main/commit_tags.txt",
        )
        assert resp.status == 200
        current_sha = None
        for line in resp.data.decode().split("\n"):
            if not line.startswith(" "):
                current_sha = line
                _COMMIT_SHA_TO_TAGS[current_sha] = set()
            else:
                _COMMIT_SHA_TO_TAGS[current_sha].add(line.strip())

    return natsort(_COMMIT_SHA_TO_TAGS.get(commit_sha, []))


if __name__ == "__main__":
    # Fetch data first from the CVE Record...
    update_from_cve_database()

    # ... then enrich the data with vstinner/python-security
    update_from_python_security()
