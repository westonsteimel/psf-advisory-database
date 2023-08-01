# Python Software Foundation Advisory Database

This is a repository of vulnerability advisories for projects in scope for the prospective
[Python Software Foundation](https://python.org/psf/) CVE Numbering Authority (CNA). Advisories are also
published to the [`security-announce@python.org` mailing list](https://mail.python.org/mailman3/lists/security-announce.python.org/).

Advisories are published in the [OSV Format](https://ossf.github.io/osv-schema).
Identifiers are CVE IDs for the associated vulnerability. You can find all
advisories issued by the CNA under the [`advisories/` directory](https://github.com/psf/advisory-database/tree/main/advisories).
Sub-directories under `advisories/` denote the affected product (ie `python`).

## Contributing

Advisories in OSV format are generated from published CVE records. Updating an advisory requires updating the
upstream CVE record so must be done by either [creating an issue on GitHub](https://github.com/psf/advisory-database/issues/new)
or contacting the CNA operators at [`cna@python.org`](mailto:cna@python.org). Pull requests updating
advisories will be closed.

## Historical Advisories

Historical advisories have been converted into this format in the `historical-advisories/`
directory for easier consumption by automated tools. CVE IDs and metadata are sourced
from [vstinner/python-security](https://github.com/vstinner/python-security).
