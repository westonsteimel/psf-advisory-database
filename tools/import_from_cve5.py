import urllib3
from osv_utils import update_osv_record

http = urllib3.PoolManager()

historical_cve_ids = {
    "python": [
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
    ]
}


def fetch_cve5_json(cve_id: str):
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
    assert resp.status == 200, resp.status
    cve_json = resp.json()
    cve_cna = cve_json["containers"]["cna"]
    cve_meta = cve_json["cveMetadata"]
    kwargs = {
        "published": cve_meta["datePublished"],
        "modified": cve_meta["dateUpdated"],
    }

    if "descriptions" in cve_cna:
        assert cve_cna["descriptions"][0]["lang"] == "en"
        kwargs["details"] = cve_cna["descriptions"][0]["value"]

    cwe_ids = []
    for problem_type in cve_cna.get("problemTypes", []):
        cwe_ids.extend(problem_type.get("cwdId", []))
    kwargs["cwe_ids"] = cwe_ids

    return kwargs


def main():
    for product, cve_ids in historical_cve_ids.items():
        for cve_id in cve_ids:
            kwargs = fetch_cve5_json(cve_id)
            update_osv_record(product=product, cve_id=cve_id, **kwargs)


if __name__ == "__main__":
    main()
