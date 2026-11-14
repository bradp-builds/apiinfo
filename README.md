# apiinfo

A small Bash HTTP API exploration utility. Inspect an endpoint's HTTP behavior,
JSON structure and actual response data, then decide what to investigate next.

```bash
./apiinfo https://example.com/api/users
./apiinfo --verbose https://example.com/wp-json
./apiinfo --no-color --timeout 10 https://example.com/api/users
```

Requires Bash 4.0+, curl 7.75+ (for JSON transfer metadata), jq 1.6+, and standard
GNU/Linux utilities. Developed for Ubuntu/WSL. No Python runtime is needed to
use the tool. Run directly from a checkout, or copy `apiinfo` into your PATH.

## What it reports

1. Requested/effective URL and GET redirects.
2. GET, HEAD and OPTIONS status codes.
3. HTTP version, downloaded size, total transfer time and selected headers.
4. JSON root type, fields and nested structure with array counts; HTML metadata
   and advertised API links when present.
5. A bounded JSON or text preview.
6. Observations to guide manual investigation.

JSON arrays show sampled elements, not a schema inferred for all elements.
Structure and preview show up to three elements per array normally and twenty
with `--verbose`. Both have depth, breadth and output limits. Verbose mode
expands these limits and adds selected metadata headers. Preview omission
markers mean the displayed JSON is a representative excerpt, not the original
response. JSON validity requires exactly one JSON value, including scalar values.
Incomplete transfers are never diagnosed as invalid JSON.

Unsupported HEAD or OPTIONS methods are normal observations. HTTP error statuses
are collected results, not transport failures. OPTIONS advertisements are not
independently verified. Name-based property hints are suggestions only.

## HTML and API discovery

For HTML responses (`text/html` or `application/xhtml+xml`), apiinfo inspects the
first 64 KiB for a page title, up to three generator declarations, and advertised
API links. Detection uses Bash and existing utilities; Python is still only a
test dependency. It supports common attribute order, quoting, case and multiline
variations and skips comments, scripts, styles and textareas.

Recognized links are API roots advertised with `rel="https://api.w.org/"` and
alternate JSON representations (`rel="alternate"` with `application/json` or an
`application/*+json` type). The WordPress relation is one supported convention;
apiinfo does not assume all APIs use it. Equivalent links in the final GET
HTTP `Link` headers are inspected even for non-HTML responses. HEAD and OPTIONS
remain method/metadata checks and are not used for API discovery.
At most ten distinct discovered links are displayed across GET HTML and headers.
Exact target matches with the same discovery kind are shown once, retaining the
first source. Relative and absolute references are not normalized for comparison;
distinct query strings also remain distinct even when their displayed values are hidden.

Links are advertised hints, not verified endpoints, and are never fetched.
Relative references are displayed as written; resolution against the page URL
or an HTML `<base>` is left to the user. Generator values are self-reported.
Missing metadata does not establish that a site has no API.

This is best-effort extraction, not a complete HTML parser. Malformed markup,
unusual encodings, complex Link syntax, metadata outside the scan limit, and
JavaScript-generated metadata can be missed. Common named entities and decimal
quote entities are decoded; arbitrary numeric/named HTML entities are not.
Titles and generator values are limited to 500 bytes; displayed link paths to
2,000 bytes. Metadata found in an incomplete response is also only a partial view.

## Request policy and privacy

Use only on endpoints you are authorized to examine. Even GET requests can have
side effects. This tool sends GET, HEAD and OPTIONS; it does not crawl, fuzz, or
send mutation requests. A normal run sends three requests. GET can follow three
redirect hops for a maximum of six requests total. HEAD and OPTIONS target the
last accepted GET URL and do not follow redirects.

Redirects follow only the same scheme, hostname and effective port. Cross-origin
redirects and HTTPS-to-HTTP downgrades stop automatically. There is currently no
cross-origin override. TLS verification stays enabled. Connection timeout is five
seconds and each request has a fifteen-second total timeout by default. A run
with redirects can therefore take longer than fifteen seconds.

Bodies are limited to 1 MiB using curl's size limit and a shell file-size limit.
Oversized transfers are incomplete; older curl versions may only detect the size
while downloading when the shell limit is reached. No automatic decompression is
requested. Temporary files are held in a private directory and removed on exit.
The tool ignores `.curlrc`; normal curl proxy environment variables still apply.
Every request sends `User-Agent: apiinfo/0.1.0`, using the script version.

Embedded URL credentials are rejected. Displayed URL query values and fragments
are hidden. Only selected response headers are printed; cookie and authentication
headers are excluded. Raw Link values are omitted; recognized discovery links
are displayed with URL credentials, queries and fragments hidden. Terminal control characters
are removed. **Body previews and other header values may still contain sensitive
data**: review output before sharing it. Query parameters are sent to the server
and, like other command-line arguments, may be visible in local process listings.

Colors are disabled for redirected output, `--no-color`, or a set `NO_COLOR`.
Exit statuses: `0` means collection completed (including HTTP 4xx/5xx), `1` means
at least one transfer failed or was incomplete, and `2` means usage/dependency
failure.

## Development

Tests require Python 3's standard library only; no virtual environment or pip
packages are needed. They start a temporary HTTP server bound to loopback on an
available port. No public endpoints are contacted.

```bash
bash -n apiinfo
shellcheck apiinfo
python3 -m unittest discover -s tests -v
```

Fixtures cover method handling, scalar/nested/invalid JSON, previews, header
privacy, redirect boundaries and budgets, HTTP errors, oversized responses,
timeouts, HTML metadata and Link-header discovery, and argument validation. GitHub Actions runs these checks on Ubuntu.

## License

Licensed under the [MIT License](LICENSE).
