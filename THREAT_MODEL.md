# wlc threat model

## Purpose and scope

wlc is a command-line and Python client for the Weblate REST API. It resolves
an endpoint and optional API key, sends read or state-changing requests,
transfers translation files, and renders responses. This model covers those
runtime behaviors in the installed CLI, Python library, and published Docker
image.

The model is shipped with source distributions and wheels, starting with wlc
2.2.0. Assess a release against its accompanying model; the development version
may describe different behavior.

## Trust boundaries

The main data flow is local configuration and caller instructions → effective
endpoint and credentials → HTTP requests → server responses → Python values,
CLI output, or downloaded files.

- **Local caller and environment:** CLI arguments, Python arguments, environment
  variables, user configuration, explicit configuration, upload inputs, and
  user-selected output paths are trusted instructions. The operating system,
  runtime, installed package, and these trusted sources are assumed intact.
- **Checked-out repository:** Automatic discovery loads user configuration and
  then the nearest project configuration in the current directory or a parent.
  Project configuration is intentionally trusted to select the endpoint,
  repository defaults, request parameters, and a matching URL-scoped key. It
  cannot acquire an unrelated unscoped CLI/environment key or weaken transport
  security. Running inside a repository can change the selected server without
  a warning or confirmation, for both read-only and state-changing commands.
- **Selected server:** The server is the intended recipient of authentication,
  requested operations, and uploaded content. Its responses, including URLs,
  object fields, error messages, and downloaded bytes, remain untrusted. The
  server may be malicious or compromised; selecting it does not make its
  content truthful or safe.
- **Network and transport configuration:** Network attackers are relevant to
  HTTPS protection. Proxy and CA-bundle settings are trusted local input for
  every destination, including loopback. They can change the traffic path and
  certificate trust; wlc does not override them or implement certificate pinning.
- **Output consumers:** The CLI provides the context-specific protections below.
  Python callers and programs consuming files or redirected streams must
  validate and escape data for their own use.

An explicit `--config` loads only the named file and disables user and project
configuration discovery; CLI/environment overrides still apply. Direct
construction of `Weblate` does not discover project configuration. Python
callers opt into configuration resolution by passing a `WeblateConfig`.

See the [configuration documentation][configuration-docs] and
[configuration implementation](wlc/config.py) for resolution rules.

## Security guarantees

### Configuration and credentials

- When project discovery supplies the otherwise-effective URL, a CLI or
  environment key must be paired with a URL from the same source: `--key` with
  `--url`, or `WLC_KEY` with `WLC_URL`. Repository-selected destinations cannot
  silently receive these unscoped secrets.
- Automatically discovered project configuration cannot enable authenticated
  insecure HTTP, disable TLS verification, or supply insecure origin entries.
  Transport exceptions require a CLI/environment setting paired with its own
  URL, or a matching origin in trusted user or explicit configuration. An
  unscoped CLI/environment exception cannot be combined with a project URL.
- Authentication comes only from configured API-key sources. Automatic
  `.netrc`/`NETRC` authentication is disabled, URL-embedded credentials are
  rejected, and keys containing carriage returns or line feeds are rejected
  before HTTP request construction.

These rules protect credential sources and transport policy while preserving
repository-driven endpoint selection. A key supplied by a repository for its
own endpoint is intentionally sent there.

Coverage: [configuration tests](tests/test_config.py) and
[client tests](tests/test_wlc.py).

### Network requests

- Requests through `Weblate`, including response-derived navigation and file
  transfers, remain on the configured API origin. Origin means scheme,
  normalized host, and effective port, normalized using the HTTP transport's
  URL parser.
- Client-constructed object paths remain inside the selected API collection.
  Identifiers supplied by CLI users, project defaults, or Python object methods
  must be relative paths without URL or traversal syntax.
- HTTP redirects are not followed automatically, and redirect responses are
  not accepted as successful API responses.
- API keys are not sent over non-loopback cleartext HTTP without an explicit
  trusted opt-in. HTTPS verifies certificates by default, including for
  loopback; verification exceptions are scoped to the selected origin.

HTTPS relies on Requests, its dependencies, and the selected CA bundle. Trusted
insecure-HTTP or TLS-verification exceptions deliberately weaken the protection
for that destination. Public API requests without an API key are permitted;
server authentication and authorization determine which operations succeed.

Implementation and coverage: [HTTP client](wlc/client.py),
[URL tests](tests/test_urls.py), [HTTP policy tests](tests/test_insecure_http.py),
and [TLS policy tests](tests/test_insecure_ssl.py).

### Filesystem writes

- Server-derived project and component archive names are sanitized so they
  cannot escape the user-selected download directory.
- CLI download writes refuse destination symlinks, non-regular files, and
  multiply linked files, and check destination replacement against races.
  These protections require the containing directory to remain under trusted
  local control.

An explicit regular output file may be overwritten, and sanitized automatic
names may collide. Callers must choose and protect output directories; entry
checks cannot secure an attacker-controlled directory namespace. Downloaded
content itself is not scanned for malicious data.

Coverage: [download tests](tests/test_download.py).

### Output and diagnostics

- Supported CLI rendering and handled diagnostics escape terminal controls and
  the supported Unicode bidi and invisible controls on interactive streams.
  This includes structured text/CSV values and diagnostics from malformed
  server data. It does not promise protection against all Unicode confusables
  or misleading text.
- HTML rendering escapes keys and values. CSV rendering neutralizes formula
  prefixes, including those hidden behind leading whitespace. CSV protection
  applies to cells produced by wlc, without guaranteeing every spreadsheet's
  behavior or protection after downstream transformations.
- Raw downloaded translation bytes are refused when standard output is an
  interactive terminal.
- wlc's debug helpers redact sensitive outgoing request headers and omit request
  bodies and uploaded contents. This is not general log sanitization: URLs,
  request parameter values, response content, and reason phrases may appear,
  and debug output does not receive the supported renderers' terminal-safety
  guarantee. Do not put secrets in request parameters.

Handled CLI errors also mask exact configured authorization values and
credentials as defense in depth. This does not provide confidentiality against
the selected server, which already receives the key and can return arbitrary
content, including transformed or partial secrets. Successful output and Python
results can likewise contain server-provided secrets. A failure of exact-value
masking remains a functional regression worth fixing; disclosure from a
separate protected source must be assessed against its own boundary.

Terminal escaping is conditional on an interactive stream. Redirected output is
a data interface, and consumers must escape it for its eventual context.
Python API consumers do not automatically receive CLI rendering, filename, or
binary-output safeguards when they render or store returned values themselves.

Implementation and coverage: [output implementation](wlc/output.py),
[debug helpers](wlc/http_debug.py), [output tests](tests/test_output.py),
[CLI tests](tests/test_main.py), and [error tests](tests/test_errors.py).

## Limitations and caller responsibilities

- **Local and deployment security:** wlc does not protect against a compromised
  local account, process, trusted configuration, runtime, or certificate store.
  Operators must protect secrets, input/output paths, process arguments,
  environment variables, and logs. wlc does not provide secret storage,
  rotation, file-permission management, or downstream log retention controls.
  Container operators control mounts, credentials, working directory, network
  policy, and process identity; the image uses the same runtime boundaries as
  the installed CLI.
- **Repository and server selection:** Review project configuration before
  relying on its endpoint and defaults; use a trusted explicit `--config` to
  disable discovery. Do not commit valuable keys to project configuration.
  Choose a server appropriate for the data and operations sent to it. Server
  honesty, confidentiality, and authorization are outside wlc's guarantees.
- **Transport choices:** Prefer HTTPS and narrowly scoped exceptions. Review
  inherited proxy and CA-bundle settings, including for loopback traffic.
  Explicitly weakening transport can expose credentials and content or allow
  server impersonation.
- **Availability and retries:** There are no strict limits on response size,
  pagination, aggregate time, memory, disk use, or retry cost against a selected
  server. Timeouts and retries are operational controls. Retrying state-changing
  methods can repeat effects. Output can be partial after failure, including
  incomplete JSON or HTML; consumers must check the exit status.
- **Content and integrations:** Origin, filename, and output containment do not
  establish content trust. Validate downloaded translations before sensitive
  use. Embedding applications must validate returned values and preserve the
  client's request normalization when carrying credentials. Wrappers and
  downstream programs must secure their own invocation and rendering contexts.
- **Other projects and development infrastructure:** Independent server and
  dependency defects, build/release hygiene, and unofficial modifications are
  outside this runtime model. Defects in wlc's use of a dependency remain in
  scope. Distribution packaging must keep the version-matched model available.

## Maintenance and security reports

Review this model when security-sensitive behavior changes. Update it in the
same change when trust assumptions, boundaries, guarantees, supported surfaces,
or material limitations change, or a report exposes a missing boundary. This
includes changes to configuration or credentials, transport and URL handling,
local data access, output contexts, data lifetime or availability assumptions,
and container or distribution behavior that affects this model.

A fix restoring an existing guarantee does not by itself require a model edit.
Keep statements at the boundary level and integrate changes into the relevant
section. Payloads, implementation mechanics, regression cases, fix history,
and report-specific triage belong in tests, commits, or issue discussions.
Add detail here only when needed to define a guarantee or meaningful exception.
See [repository guidance](AGENTS.md) for contributor instructions.

Report security issues through the [Weblate security policy](SECURITY.md).
Evaluate demonstrated attacker control, data flow, and boundary impact against
the affected release's model. Intended endpoint selection or a deliberately
weakened trusted setting alone does not establish a boundary violation. A
practical improvement outside the guarantees can still be worthwhile, and an
uncovered security boundary may expose a model gap. Investigate such gaps and
update the model rather than treating omission as evidence of safety.

[configuration-docs]: https://docs.weblate.org/en/latest/wlc.html#configuration-files
