# wlc threat model

Project: wlc (Weblate command-line client and Python API client)

Last reviewed for wlc 2.2.0 at base commit
`1e63ad96951734ba26ba240f1ccfa80be4a8c645`, including the accompanying
changes in this revision.

Date: 2026-09-01.

Status: Accepted, 2026-09-01.

Version binding: This model is versioned with wlc releases and included in
source distributions and wheels. It first applies to wlc 2.2.0 and does not
describe the previously published 2.1.1 artifacts. A report against wlc version
N is evaluated against the model published for version N, rather than against
the latest development branch. *(maintainer)*

Reporting cross-reference: Reports that violate a property in
[Security properties wlc provides](#security-properties-wlc-provides) should be
reported using the [Weblate security policy][security-policy]. Reports that
fall under [Out of scope](#out-of-scope) or
[Security properties wlc does not provide](#security-properties-wlc-does-not-provide)
can be closed by citing this document unless this model routes them to
`VALID-HARDENING`. *(maintainer)*

Provenance legend: `*(documented)*` means the claim is stated in wlc or Weblate
documentation; `*(maintainer)*` means it was stated by a maintainer during this
threat-model process; `*(inferred)*` means it was reasoned from the current
project shape and needs maintainer confirmation.

Provenance summary: 53 documented / 78 maintainer / 0 inferred claims.

wlc is a command-line utility and Python library for making requests to the
[Weblate REST API][api-docs]. It resolves an API endpoint and optional API key,
sends read or state-changing API requests, renders API responses, and transfers
translation files. *(documented)* (source: [README](README.md),
[client implementation](wlc/client.py), [CLI implementation](wlc/main.py))

## Scope and intended use

| Component family | Representative surface | Outside-process effects | Model status |
| --- | --- | --- | --- |
| Configuration resolution | Command-line arguments, environment variables, explicit configuration, user configuration, and automatically discovered project configuration | Selects the API endpoint, API key, default translation, and HTTP request policy | In scope. Project configuration is intentionally authoritative for repository-specific service selection, subject to the credential and transport boundaries below. *(documented)* (source: [configuration documentation][configuration-docs], [configuration implementation](wlc/config.py)) |
| Read and action commands | `list-*`, `show`, `stats`, `changes`, `commit`, `push`, `pull`, `delete`, `lock`, `unlock`, `reset`, and related commands | Sends HTTP requests and can change state on the selected Weblate server | In scope. The selected endpoint and the authenticated Weblate account define the target and permitted effects. *(documented)* (source: [client documentation][wlc-docs], [CLI implementation](wlc/main.py)) |
| File transfer and output | `download`, `upload`, standard input and output, text, JSON, CSV, and HTML rendering | Reads local input, writes local files or standard output, sends translations, and consumes server-provided data | In scope for origin confinement, server-derived filenames, safe download replacement, interactive-terminal safety, and format-specific output escaping. *(documented)* (source: [CLI implementation](wlc/main.py), [output implementation](wlc/output.py)) |
| Python API | `Weblate`, model objects, iterators, raw responses, and configuration objects | Makes network requests and returns server data to the embedding application | In scope for HTTP transport and origin confinement. The embedding application remains responsible for how returned values are rendered or stored. *(documented)* (source: [client implementation](wlc/client.py), [Python API documentation][python-api-docs]) |
| Docker image | Published `weblate/wlc` image | Runs the same CLI with mounted configuration, environment variables, input, and output | In scope under the same boundaries as the installed CLI. Container-runtime and mount policy are deployment responsibilities. *(documented)* (source: [Docker documentation][docker-docs], [Dockerfile](Dockerfile)) |
| Tests, completion scripts, build and release automation | Test fixtures, shell completion, packaging metadata, and GitHub workflows | Development and release effects | Out of scope for runtime security properties. Distribution packaging remains in scope for making the version-bound model available. *(maintainer)* |

The intended workflow includes cloning a source repository and running wlc from
inside it. The repository can contain `.weblate`, `.weblate.ini`, or
`weblate.ini` so that wlc automatically selects the correct Weblate server and
default translation without per-command configuration. *(documented)* (source:
[configuration documentation][configuration-docs])

The intended actors are a local user invoking the CLI, an application embedding
the Python client, the author of a selected explicit or user configuration, the
author of a checked-out repository and its project configuration, and the
configured Weblate API server. These actors have different responsibilities as
defined below. *(maintainer)*

## Out of scope

The following are explicit non-goals for this model:

- A compromised operating-system account, Python process, container runtime,
  shell, home directory, current working directory outside project-config
  interpretation, trusted configuration file, or certificate trust store. Such
  an actor can read credentials, replace code, alter command arguments, or
  intercept input and output. *(maintainer)*
- A malicious local operator or embedding application with authority to choose
  command-line arguments, environment variables, an explicit configuration,
  API parameters, input files, or output paths. These are trusted instructions
  to wlc. *(maintainer)*
- Security defects in Weblate server authorization or in third-party
  dependencies as independent projects. A defect in how wlc uses a dependency
  remains in scope. *(documented)* (source: [security policy](SECURITY.md))
- Correctness, honesty, availability, or confidentiality of the API server
  selected by trusted configuration or repository project configuration. wlc
  contains server responses as described below, but does not make an
  attacker-selected server trustworthy. *(maintainer)*
- Build and release hygiene, including workflow permissions, artifact signing,
  dependency freshness, registry security, and repository branch protection.
  These affect project operations but are not runtime claims in this model.
  *(maintainer)*
- Shell scripts, CI jobs, editor integrations, spreadsheet programs, browsers,
  or other programs that invoke wlc or consume redirected output. Their safe
  construction and interpretation are downstream responsibilities.
  *(maintainer)*
- Protection against denial of service by a selected API server through large
  responses, long pagination chains, slow responses within configured
  timeouts, or retry amplification. *(maintainer)*

## Trust boundaries and data flow

The primary flow is:

```text
trusted CLI user or Python caller
        |
        +-- CLI arguments / environment / explicit or user configuration
        |
checked-out repository -- project configuration
        |                         |
        +------ configuration resolution
                          |
                 effective URL, key, and request policy
                          |
                   HTTP(S) API requests <---- local upload/input
                          |
                 configured Weblate server
                          |
                untrusted response data and URLs
                          |
             models / CLI rendering / downloaded files
```

| Boundary | Trust transition |
| --- | --- |
| Local user or embedding application to wlc | Command arguments, explicit configuration, user configuration, environment variables, Python method arguments, local input, and user-selected output paths are trusted instructions. *(maintainer)* |
| Checked-out repository to configuration resolution | The nearest project configuration is trusted to select the API endpoint, default translation, request parameters, and a matching URL-scoped key. It is not trusted to enable insecure authenticated transport or to acquire an unscoped command-line or environment key without a destination supplied by the same source. *(maintainer)* |
| Configuration resolution to HTTP client | The effective URL defines the authorized destination. The effective key is sent only to that destination and only under the authenticated-transport rules in this model. Requests' automatic `netrc` authentication is disabled, and credentials embedded in URLs are rejected. *(documented)* (source: [configuration implementation](wlc/config.py), [client implementation](wlc/client.py)) |
| Local upload or command to selected API server | The server is an intended recipient of data explicitly supplied to upload commands and of API operations requested by the user or embedding application. *(maintainer)* |
| Selected API server to wlc | Response bodies, object fields, pagination links, download links, repository links, and refresh links are untrusted. wlc must contain their network destination, server-derived filesystem names, download destination entries, and interactive rendering as claimed below. *(documented)* (source: [URL tests](tests/test_urls.py), [download tests](tests/test_download.py), [CLI tests](tests/test_main.py)) |
| wlc to terminal, file, pipe, or embedding application | Interactive CLI output receives terminal-specific hardening. Files, redirected streams, and Python values are data interfaces whose consumers must apply context-appropriate validation. *(documented)* (source: [output implementation](wlc/output.py), [CLI implementation](wlc/main.py)) |

Project configuration is reachable only when wlc performs automatic discovery.
wlc loads user configuration first and then the nearest project configuration
found in the current directory or a parent. Supplying `--config` loads only
that explicit file and disables both user and project discovery. *(documented)*
(source: [configuration documentation][configuration-docs],
[configuration implementation](wlc/config.py))

All CLI commands use the resulting effective configuration. This consistency
is intentional: read-only and state-changing commands are not assigned
different project-configuration trust levels. *(maintainer)*

Direct construction of the Python `Weblate` client does not automatically
discover project configuration. A Python caller opts into configuration
resolution by constructing and passing a `WeblateConfig`. *(documented)*
(source: [client implementation](wlc/client.py),
[configuration implementation](wlc/config.py))

Requests' proxy and CA-bundle environment integration applies to every
destination, including literal loopback hostnames and addresses. These settings
are trusted local input and wlc does not override them. *(documented)* (source:
[client implementation](wlc/client.py), [client tests](tests/test_wlc.py))

## Environment assumptions

- The local operating system, Python runtime, installed wlc package, invocation
  mechanism, and sources classified as trusted above have not been
  compromised. *(maintainer)*
- HTTPS security relies on `requests`, `urllib3`, DNS and routing, and the CA
  bundle selected by Requests. Pip-installed Requests normally uses its
  dependency-provided CA bundle; `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`, session
  settings, or downstream packaging can select another bundle. wlc does not implement an
  independent PKI or certificate pinning mechanism. *(documented)* (source:
  [Requests TLS documentation][requests-tls],
  [client implementation](wlc/client.py), [project dependencies](pyproject.toml))
- TLS certificate verification is enabled for HTTPS by default, including
  literal loopback names and addresses. Trusted CLI, environment, user, or
  explicit configuration can disable verification under the scoping rules
  below. *(documented)* (source: [client implementation](wlc/client.py),
  [TLS tests](tests/test_insecure_ssl.py))
- Proxy and CA-bundle environment variables are trusted local configuration for
  every destination, including literal loopback destinations. *(documented)*
  (source: [Requests advanced usage][requests-advanced],
  [client tests](tests/test_wlc.py))
- Configuration and API-key files, environment variables, process arguments,
  input files, output paths, and redirected output are protected by the local
  operating system and deployment. wlc does not provide secret storage or file
  permission management. *(maintainer)*
- The Weblate API may allow unauthenticated read access. An absent API key does
  not by itself make a request invalid or unsafe. Server-side authentication
  and authorization determine which operations succeed. *(documented)*
  (source: [Weblate API documentation][api-docs])

The principal outside-process side effects are HTTP requests, server-side API
state changes, reading upload input, writing downloaded content or formatted
output, and diagnostic logging. Commands that perform these effects are
expected to do so against the effective endpoint without an additional trust
prompt. *(maintainer)*

## Build-time and configuration variants

- The installed CLI, module invocation, and Docker image use the same Python
  client and security boundaries. Container mounts, environment injection, and
  user identity are controlled by the container operator. *(documented)*
  (source: [Docker documentation][docker-docs], [CLI implementation](wlc/main.py))
- The version-matched threat model is shipped in the source archive and under
  `share/doc/wlc` in the wheel. The README links to the latest published copy
  for browsing outside a checkout. *(documented)* (source:
  [package metadata](pyproject.toml), [source manifest](MANIFEST.in),
  [README](README.md))
- With automatic discovery, user configuration is merged with the nearest
  project configuration. With `--config`, only the named file is loaded. CLI
  and environment URL/key values then apply at their documented precedence.
  *(documented)* (source: [configuration documentation][configuration-docs])
- A command-line flag or environment setting paired with its own URL, or a
  matching origin in trusted user or explicit configuration, can enable
  authenticated non-local HTTP or disable TLS verification. Automatically
  discovered project configuration cannot supply an insecure origin or combine
  its URL with an unscoped transport exception. *(documented)* (source:
  [configuration implementation](wlc/config.py),
  [configuration tests](tests/test_config.py),
  [HTTP tests](tests/test_insecure_http.py),
  [TLS tests](tests/test_insecure_ssl.py))
- Requests' proxy and CA-bundle environment integration remains enabled for all
  destinations. Automatic `netrc` authentication is disabled. *(documented)*
  (source: [client tests](tests/test_wlc.py))
- Retry count, retryable HTTP methods, status-code list, backoff factor, and
  timeout are configurable. Enabling retries for state-changing methods can
  repeat an operation and is an explicit operator choice. *(documented)*
  (source: [configuration documentation][configuration-docs],
  [client implementation](wlc/client.py))
- Text, JSON, CSV, and HTML outputs have different serialization properties.
  Terminal control escaping is conditional on an interactive stream; CSV
  formula neutralization and HTML escaping are format-specific.
  *(documented)* (source: [CLI implementation](wlc/main.py),
  [output tests](tests/test_main.py))

## Input assumptions

| Input surface | Classification and assumptions |
| --- | --- |
| CLI arguments and Python method arguments | Trusted instructions from the local user or embedding application. Values still receive parsing and protocol validation where required for claimed properties. *(maintainer)* |
| Environment, explicit configuration, and user configuration | Trusted for endpoint selection, credentials, request policy, origin-scoped transport exceptions, proxy selection, and CA-bundle selection. Their storage and injection are outside wlc's secret-management boundary. *(maintainer)* |
| Automatically discovered project configuration | Trusted for repository-specific endpoint selection, defaults, request policy, and URL-scoped keys. Not trusted for unscoped CLI/environment secrets, insecure HTTP or TLS origins, or unscoped transport exceptions. *(maintainer)* |
| API key | Confidential authentication material. A URL-scoped key is associated with the configured URL; a CLI or environment key is unscoped and must be paired with a URL from the same source when project discovery selected the otherwise-effective URL. Requests does not add credentials from `.netrc` or `NETRC`, and URL userinfo is not an accepted credential source. *(documented)* (source: [configuration documentation][configuration-docs], [configuration implementation](wlc/config.py), [client tests](tests/test_wlc.py), [URL tests](tests/test_urls.py)) |
| API response bodies and object fields | Untrusted server data. They may be false, malformed, very large, or hostile to downstream renderers. wlc claims only the parsing, origin, path, and output properties listed below. *(maintainer)* |
| Server-provided URLs | Untrusted navigation input. They must resolve to the normalized origin of the configured API root before wlc requests them. *(documented)* (source: [client implementation](wlc/client.py), [URL tests](tests/test_urls.py)) |
| Server-provided slugs used for automatic filenames | Untrusted filename components. wlc replaces characters outside its allowed slug subset before constructing the filename. *(documented)* (source: [filename helper](wlc/utils.py), [CLI implementation](wlc/main.py)) |
| Upload input and user-selected output path | Trusted user choices. Upload content is intentionally disclosed to the selected server; an explicit regular output file may be overwritten, but wlc refuses unsafe destination types and replacement races. *(maintainer)* |
| Standard output consumed by a pipe or file | A data interface, not necessarily a terminal. The consumer must choose the correct parser and rendering context. *(maintainer)* |

## Adversary model

The model considers these relevant adversaries:

- A malicious or compromised repository author can provide project
  configuration that selects an attacker-controlled API endpoint, changes
  repository defaults and request parameters, and supplies a key scoped to the
  selected URL. These capabilities are intentional. The author must not thereby
  acquire an unrelated unscoped CLI/environment key or enable authenticated
  cleartext transport. *(maintainer)*
- A malicious or compromised configured API server can return arbitrary JSON,
  bytes, object fields, error messages, pagination links, download links, and
  timing behavior. It can observe requests and upload data sent to it. It must
  not cause wlc to follow a response URL to another origin, escape an automatic
  download directory through a server-derived slug, or emit active control
  sequences to an interactive terminal through supported CLI renderers.
  *(maintainer)*
- An on-path network attacker is relevant when HTTPS is used. wlc relies on the
  CA bundle selected by Requests and refuses to send an API key over
  non-loopback HTTP unless a trusted source explicitly opts in. Configured
  proxies are trusted local routing for every destination. *(documented)*
  (source: [client implementation](wlc/client.py),
  [client tests](tests/test_wlc.py), [HTTP tests](tests/test_insecure_http.py))
- An unprivileged local observer may be able to inspect arguments, environment,
  configuration files, process memory, output, or local logs according to
  operating-system permissions. Preventing that access is not a wlc property,
  although wlc avoids automatic `netrc` authentication and putting
  authorization headers and request bodies in its own debug output.
  *(maintainer)*

An adversary is not assumed to control the trusted local user, embedding
application, explicit configuration, user configuration, installed client
code, Python runtime, or operating system. *(maintainer)*

## Security properties wlc provides

| Property | Conditions | Violation symptom | Severity | Provenance |
| --- | --- | --- | --- | --- |
| Server-provided request targets remain on the configured API origin after normalization by the parser used by the HTTP transport. | The request goes through the `Weblate` client. Origin means scheme, normalized host, and effective port. | Pagination, refresh, repository, upload, download, or another response-derived URL causes a request to a different origin. | High when credentials or user data are sent; otherwise Medium. | *(documented)* (source: [client implementation](wlc/client.py), [URL tests](tests/test_urls.py)) |
| HTTP redirects are not followed automatically. | The request goes through the `Weblate` client. | A 3xx response causes a follow-up request, or is accepted as a successful API response. | High when credentials or user data cross a boundary; otherwise Medium. | *(documented)* (source: [client implementation](wlc/client.py), [URL tests](tests/test_urls.py)) |
| API keys are not sent over non-loopback cleartext HTTP by default. | A key is present and no trusted source explicitly enabled insecure HTTP. The request goes through the `Weblate` client. | The client sends the key to a non-loopback `http://` destination. | High. | *(documented)* (source: [client implementation](wlc/client.py), [HTTP tests](tests/test_insecure_http.py)) |
| TLS certificates are verified by default and verification exceptions are scoped to the selected origin. | The destination is HTTPS and no trusted source supplied a matching origin or explicit transient exception under the configuration rules. | Verification is disabled for an unrelated origin, or without an explicit trusted opt-in. | High. | *(documented)* (source: [configuration implementation](wlc/config.py), [client implementation](wlc/client.py), [TLS tests](tests/test_insecure_ssl.py)) |
| Automatically discovered project configuration cannot enable authenticated insecure HTTP, disable TLS verification, or supply insecure origin entries. | The project file is discovered automatically rather than supplied as explicit configuration. | A project-only setting weakens HTTP or TLS transport, or a CLI/environment exception is accepted without a URL from the same source. | High. | *(documented)* (source: [configuration implementation](wlc/config.py), [configuration tests](tests/test_config.py)) |
| An unscoped CLI or environment key cannot be paired with a project-selected URL unless that same source also pins the URL. | Automatic project discovery supplied the otherwise-effective URL. | `--key` is accepted without `--url`, or `WLC_KEY` is accepted without `WLC_URL`. | High. | *(documented)* (source: [configuration implementation](wlc/config.py), [configuration tests](tests/test_config.py)) |
| Authentication is accepted only from configured API-key sources; Requests does not automatically add credentials from `.netrc` or the file named by `NETRC`, and credentials embedded in URLs are rejected. | The request goes through the `Weblate` client. | A repository-selected host causes Requests to add or replace authentication using a netrc file, or a URL containing userinfo produces an HTTP request. | High. | *(documented)* (source: [configuration documentation][configuration-docs], [client implementation](wlc/client.py), [client tests](tests/test_wlc.py), [URL tests](tests/test_urls.py)) |
| An explicit `--config` file prevents automatic user and project configuration discovery. | The CLI successfully reads the explicit file. CLI/environment overrides still apply normally. | Settings from a discovered user or project file affect the configuration. | Medium. | *(documented)* (source: [configuration implementation](wlc/config.py), [configuration tests](tests/test_config.py)) |
| wlc debug logging redacts authorization and proxy-authorization headers, scrubs their values from request-failure messages, and does not log request bodies or uploaded file contents. | Logging uses wlc's debug helpers. Parameter values can still be logged and must not be used for secrets. | A generated debug entry contains an API token, JSON/body values, or uploaded contents supplied only through the corresponding request fields. | High for credentials; otherwise Medium. | *(documented)* (source: [debug implementation](wlc/http_debug.py), [debug tests](tests/test_errors.py), [CLI debug tests](tests/test_main.py)) |
| Automatically generated component archive filenames cannot use server-provided slugs for path traversal. | wlc chooses the project/component download filename inside a user-selected directory. | A server-provided project or component slug writes outside that directory. | High. | *(documented)* (source: [filename helper](wlc/utils.py), [CLI implementation](wlc/main.py), [download tests](tests/test_download.py)) |
| Download writes do not follow destination symlinks or overwrite non-regular or multiply linked targets, and destination replacement is checked against races. | The CLI writes a downloaded translation or automatically named archive through its download helper. The containing directory remains under local-user control. | A preplanted or racing symlink, hard link, changed inode, or non-regular destination redirects downloaded bytes to another file or device. | High. | *(documented)* (source: [CLI implementation](wlc/main.py), [download tests](tests/test_download.py)) |
| Raw translation bytes are not written to an interactive terminal. | A translation download would use standard output and that stream reports itself as a TTY. | Binary translation data is emitted to the interactive terminal instead of being refused. | Medium. | *(documented)* (source: [CLI implementation](wlc/main.py), [CLI tests](tests/test_main.py)) |
| Supported CLI rendering contains common active-output payloads in their intended context. | Text and CSV values are converted to text before C0/C1 controls are escaped for a TTY, including structured values; HTML keys and values are HTML-escaped; CSV cells beginning with formula markers, including markers hidden behind leading whitespace, are neutralized. | Supported rendering emits an active terminal control sequence, unescaped HTML value, or active CSV formula under these conditions. | Medium. | *(documented)* (source: [output implementation](wlc/output.py), [CLI implementation](wlc/main.py), [output tests](tests/test_main.py)) |

## Security properties wlc does not provide

- Project configuration is not sandboxed or treated as untrusted for endpoint
  selection. Discovering a project file may silently change the effective API
  endpoint, default translation, request parameters, and URL-scoped key.
  This is the feature that lets a cloned repository select its Weblate server.
  *(maintainer)*
- wlc does not warn or ask for confirmation when project configuration changes
  the effective endpoint or credential. Read-only and state-changing commands
  deliberately use the same automatic configuration behavior. *(maintainer)*
- A configured API key authenticates the client to the server; it does not
  authenticate the server to the user or make the server's responses truthful.
  Server identity relies on the selected URL and, for HTTPS, normal TLS
  validation. *(maintainer)*
- wlc does not protect data deliberately uploaded or operations deliberately
  requested from the selected server. The server receives that data and may
  process an authenticated operation within the key's server-side permissions.
  *(maintainer)*
- Debug output is diagnostic data rather than a supported structured renderer.
  Header and request-body redaction does not imply terminal-control escaping or
  secrecy for request parameter values, URLs, response reason phrases, or error
  messages included in diagnostics. *(maintainer)*
- wlc does not enforce a response-size, pagination-count, aggregate-time,
  memory, disk-usage, or retry-cost limit against the selected server. The
  configured per-request timeout and retry policy are operational controls, not
  a general malicious-server availability guarantee. *(maintainer)*
- Downloaded translations and arbitrary API values are not scanned for
  malicious or misleading content. Filename and output containment do not imply
  content trust. *(maintainer)*
- Terminal escaping does not promise that redirected text or JSON is safe to
  reinterpret as shell, HTML, markup, source code, a terminal stream, or any
  other active format. Each downstream consumer must escape for its own
  context. *(maintainer)*
- CSV formula neutralization protects cells produced by wlc's CSV renderer. It
  does not guarantee safe behavior in every spreadsheet implementation or
  after a downstream transformation removes the neutralizing prefix.
  *(maintainer)*
- An explicit user-selected output file can be overwritten, and an explicit
  output directory can receive files whose sanitized names collide. The caller
  is responsible for choosing and protecting the containing directory. wlc's
  symlink, hard-link, destination-type, and race protections do not make an
  attacker-controlled parent directory safe. *(maintainer)*
- Direct Python API consumers do not automatically receive CLI terminal, CSV,
  HTML, filename, or binary-output safeguards when they render or store returned
  values themselves. *(documented)* (source: [client implementation](wlc/client.py),
  [CLI implementation](wlc/main.py))
- Enabling insecure HTTP or disabled TLS verification for an origin, or
  changing retries and retryable methods, changes the protection appropriate
  to that deployment. wlc does not conceal those requested tradeoffs.
  *(documented)* (source: [configuration documentation][configuration-docs])
- wlc does not override trusted proxy or CA-bundle environment settings for any
  destination, including loopback. A configured proxy becomes part of the
  transport path, and a configured CA bundle changes which certificates are
  trusted. *(documented)* (source:
  [Requests advanced usage][requests-advanced], [client tests](tests/test_wlc.py))
- wlc does not provide API-key storage, rotation, least-privilege policy,
  server-side authorization, repository review, container isolation, or
  operating-system access control. *(maintainer)*

These are property disclaimers, not claims that all behavior in these areas is
immune from improvement. A report that demonstrates a practical boundary
escape not already described can expose a model gap. *(maintainer)*

## Downstream responsibilities

- Review project configuration with the same care as other repository
  instructions. Running wlc inside a repository authorizes the nearest project
  configuration to select the API server and repository defaults. Use a trusted
  explicit `--config` when that behavior is not desired. *(maintainer)*
- In CI, pair `WLC_KEY` with `WLC_URL`; for CLI secrets, pair `--key` with
  `--url`. Pin both values to the intended service instead of allowing project
  discovery to choose a destination for an unscoped secret. *(documented)*
  (source: [configuration documentation][configuration-docs])
- Prefer HTTPS. Enable insecure authenticated HTTP only after accepting
  exposure to the network between the client and server. Disable TLS
  verification only for a narrowly scoped origin whose alternative trust is
  understood. *(documented)*
  (source: [configuration documentation][configuration-docs])
- Audit `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`,
  `REQUESTS_CA_BUNDLE`, and `CURL_CA_BUNDLE` in the execution environment.
  Proxy and CA-bundle settings are trusted for every destination, including
  loopback. *(documented)* (source: [Requests advanced usage][requests-advanced],
  [client tests](tests/test_wlc.py))
- Protect configuration files, environment variables, command history,
  process information, upload inputs, output destinations, and logs using
  local operating-system and CI controls. Avoid committing valuable API keys
  to repository project configuration. *(maintainer)*
- Treat the selected server as the recipient of uploads and commands and as the
  source of displayed and downloaded content. Validate downloaded translation
  data before using it in a sensitive build or publication pipeline.
  *(maintainer)*
- Select retryable methods conservatively. Retrying a state-changing operation
  can repeat an effect when the first response was lost. *(documented)*
  (source: [configuration documentation][configuration-docs])
- Treat redirected CLI output as data and escape it for its eventual consumer.
  Do not assume TTY-specific escaping occurred when output went to a file or
  pipe. *(maintainer)*
- Keep download parent directories under trusted local control. Destination
  entry checks prevent common link and replacement attacks but do not protect
  an attacker-controlled directory namespace. *(maintainer)*
- Python applications must validate model fields, raw bytes, filenames, paths,
  and rendered values for their own use and must not bypass `Weblate` request
  normalization when carrying credentials. *(maintainer)*
- Container operators must control mounts, injected credentials, working
  directory, network policy, and the identity under which wlc runs.
  *(maintainer)*

## Known misuse patterns

- Cloning an unreviewed repository, running wlc inside it, and assuming the
  global user endpoint will remain effective. Project endpoint selection is
  intentional; use explicit configuration when repository instructions are not
  trusted. *(maintainer)*
- Supplying `WLC_KEY` or `--key` while relying on automatic project discovery
  to choose its destination. Current wlc rejects this combination; pin the URL
  from the same source. *(documented)* (source:
  [configuration documentation][configuration-docs])
- Adding a broad origin to `[insecure_http]` or `[insecure_ssl]`, or using an
  unscoped CLI/environment transport exception, for convenience. This exposes
  credentials and traffic to observers or removes server authentication for
  the selected origin. *(documented)* (source:
  [configuration documentation][configuration-docs])
- Trusting inherited proxy or CA-bundle environment variables without checking
  where traffic is routed or which certificates are accepted. *(maintainer)*
- Adding a valuable API key to a version-controlled project `[keys]` section.
  URL scoping controls destination selection; it does not make a committed
  credential secret. *(maintainer)*
- Configuring retries for non-idempotent or state-changing methods without
  considering duplicate effects. *(maintainer)*
- Treating a downloaded translation, HTML output, CSV output, JSON output, or
  Python object as trusted merely because wlc contained its transport origin or
  filename. *(maintainer)*
- Passing a user-selected output path that names an existing valuable file, or
  running downloads in an attacker-controlled directory or one where sanitized
  filename collisions matter. *(maintainer)*

## Known non-findings

The following report patterns are already resolved by this model:

| Report pattern | Disposition and rationale |
| --- | --- |
| A checked-out repository's automatically discovered project configuration silently replaces the user API URL and supplies or replaces the matching `[keys]` entry. | `BY-DESIGN / property-disclaimed`. Repository-driven endpoint, default, request-policy, and URL-scoped-key selection is an intended workflow. No warning or opt-in is promised. Reopen as `VALID` only if the behavior also violates a claimed secret, transport, origin, path, or output property. *(maintainer)* |
| Commands, uploads, or downloads use the server selected by project configuration rather than the endpoint in global user configuration. | `BY-DESIGN / property-disclaimed`. All commands use the same effective configuration. The selected server is the intended recipient and response source. *(maintainer)* |
| An attacker-controlled selected server returns false project information or malicious translation content. | `OUT-OF-MODEL / trusted-input` for truthfulness and content trust. Response containment remains in scope, so a cross-origin request, automatic path escape, or active supported CLI output payload can still be `VALID`. *(maintainer)* |
| wlc refuses `WLC_KEY` without `WLC_URL`, or `--key` without `--url`, when project configuration selects the endpoint. | `KNOWN-NON-FINDING`. This is enforcement of the unscoped-secret destination property. *(documented)* (source: [configuration implementation](wlc/config.py)) |
| An unauthenticated command is accepted when no API key is configured. | `BY-DESIGN / property-disclaimed`. Public API access is determined by the selected Weblate server. *(documented)* (source: [Weblate API documentation][api-docs]) |
| An explicitly enabled insecure HTTP connection exposes its API key or contents, or explicitly disabled TLS verification permits interception. | `OUT-OF-MODEL / trusted-input`. The trusted caller deliberately removed the default transport protection for the selected destination. A project configuration bypassing the opt-in or origin restriction remains `VALID`. *(maintainer)* |
| A selected server exhausts memory, disk, time, or requests using large content, pagination, or retry behavior without escaping another boundary. | `BY-DESIGN / property-disclaimed` for strict resource bounds; targeted, low-cost hardening can be `VALID-HARDENING`. *(maintainer)* |
| A Python caller renders a returned server string in HTML, a terminal, or a filename without context-specific escaping. | `OUT-OF-MODEL / trusted-input`. The CLI hardening does not automatically apply to embedding applications. A bypass in a supported CLI renderer remains `VALID`. *(maintainer)* |

## Conditions that change this model

Review and update this model when any of these occur:

- Configuration discovery, precedence, project-config trust, credential
  scoping, or insecure-transport policy changes. *(maintainer)*
- A new credential source, authentication scheme, secret-storage mechanism,
  transport, redirect mode, proxy behavior, or certificate policy is added.
  *(maintainer)*
- Server-provided URLs can reach a new request path, or origin normalization no
  longer uses the parser used by the HTTP transport. *(maintainer)*
- A new command or Python API writes files, executes subprocesses, loads code,
  evaluates templates, renders a new active output format, or sends a new class
  of sensitive local data. *(maintainer)*
- Automatic configuration discovery is added to direct Python client
  construction, or read-only and state-changing commands gain different trust
  behavior. *(maintainer)*
- Streaming, parallel requests, caching, persistent queues, background work, or
  a new retry mechanism changes data lifetime or availability assumptions.
  *(maintainer)*
- The Docker image gains privileges, default mounts, bundled services, or
  behavior that differs materially from the installed CLI. *(maintainer)*
- Distribution packaging changes where the version-bound model is installed or
  stops shipping it in a supported release artifact. *(maintainer)*
- A vulnerability report shows that a stated property is false, exposes a
  missing boundary, or demonstrates that a disclaimed behavior should become a
  supported security property. *(maintainer)*
- Maintainers decide to treat repository project configuration as untrusted for
  endpoint selection or to require warnings or explicit opt-in. *(maintainer)*

## Triage dispositions

Use these closed dispositions when evaluating a report:

- `VALID`: The report violates a property claimed in
  [Security properties wlc provides](#security-properties-wlc-provides) under
  its stated conditions. *(maintainer)*
- `VALID-HARDENING`: The report does not violate a promised boundary, but a
  practical and proportionate change would reduce risk without contradicting
  the intended repository workflow or public interface. *(maintainer)*
- `OUT-OF-MODEL / trusted-input`: The behavior requires control of an input
  explicitly trusted by this model, such as the local caller or explicit user
  configuration. *(maintainer)*
- `OUT-OF-MODEL / adversary`: The claimed attacker is not included in the
  adversary model, such as an already-compromised local account controlling the
  running process. *(maintainer)*
- `OUT-OF-MODEL / unsupported`: The report concerns an unsupported integration,
  wrapper, renderer, or downstream consumer rather than wlc's documented
  surfaces. *(maintainer)*
- `OUT-OF-MODEL / non-default-build`: The report requires an unofficial build
  or downstream modification that changes the documented behavior.
  *(maintainer)*
- `BY-DESIGN / property-disclaimed`: The report demonstrates behavior expressly
  listed under
  [Security properties wlc does not provide](#security-properties-wlc-does-not-provide).
  *(maintainer)*
- `KNOWN-NON-FINDING`: The same report pattern and conditions are already
  resolved under [Known non-findings](#known-non-findings). *(maintainer)*
- `MODEL-GAP`: The report is security-relevant but this model neither promises
  nor disclaims the affected boundary. Maintainers must update the model and
  then assign a substantive disposition. *(maintainer)*

Triage must evaluate demonstrated data flow and boundary impact, not only the
report's vulnerability-class label. In particular, selecting an attacker-owned
endpoint is not credential exfiltration when the only credential sent is one
that project configuration supplied for that endpoint. *(maintainer)*

## Open questions

There are no open maintainer questions in this accepted revision and no
`*(inferred)*` claims. New uncertain claims must be marked `*(inferred)*` and
listed here until a maintainer accepts, rejects, or narrows them.

[api-docs]: https://docs.weblate.org/en/latest/api.html
[configuration-docs]: https://docs.weblate.org/en/latest/wlc.html#configuration-files
[docker-docs]: https://docs.weblate.org/en/latest/wlc.html#docker-wlc
[python-api-docs]: https://docs.weblate.org/en/latest/python.html#module-wlc
[requests-advanced]: https://requests.readthedocs.io/en/latest/user/advanced/
[requests-tls]: https://requests.readthedocs.io/en/latest/user/advanced/#ca-certificates
[security-policy]: https://docs.weblate.org/en/latest/security/issues.html
[wlc-docs]: https://docs.weblate.org/en/latest/wlc.html
