<a href="https://weblate.org/"><img alt="Weblate" src="https://s.weblate.org/cdn/Logo-Darktext-borders.png" height="80px" /></a>

**Weblate is libre software web-based continuous localization system,
used by over 2500 libre projects and companies in more than 165 countries.**

# wlc

wlc is a [Weblate](https://weblate.org/) command-line client using [Weblate's REST API](https://docs.weblate.org/en/latest/api.html).

[![Website](https://img.shields.io/badge/website-weblate.org-blue.svg)](https://weblate.org/)
[![Translation status](https://hosted.weblate.org/widgets/weblate/-/svg-badge.svg)](https://hosted.weblate.org/engage/weblate/?utm_source=widget)
[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/552/badge)](https://bestpractices.coreinfrastructure.org/projects/552)
[![PyPI package](https://img.shields.io/pypi/v/wlc.svg)](https://pypi.org/project/wlc/)
[![Documentation](https://readthedocs.org/projects/weblate/badge/)](https://docs.weblate.org/en/latest/wlc.html)

## PIP Installation

Install using pip:

```console
pip3 install wlc
```

Sources are available at <https://github.com/WeblateOrg/wlc>.

## Usage

Please see [Weblate documentation](https://docs.weblate.org/en/latest/wlc.html) for more complete documentation.

Command-line usage:

```console
wlc list-projects
wlc list-components
wlc list-translations
wlc list-languages
wlc show
wlc ls
wlc commit
wlc push
wlc pull
wlc repo
wlc stats
wlc lock
wlc unlock
wlc lock-status
wlc download
wlc upload
```

Configuration is loaded from `--config` when provided. Otherwise `wlc` reads the
user configuration from XDG paths such as `~/.config/weblate` and then the
nearest project configuration file (`.weblate`, `.weblate.ini`, or
`weblate.ini`) from the current directory or its parents. The key/values
(`retries`, `timeout`, `allowed_methods`, `backoff_factor`,
`status_forcelist`) are closely coupled with the
[urllib3 parameters](https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html)
and allows the user to configure request parameters.

```ini
[weblate]
url = https://hosted.weblate.org/api/
retries = 3
allowed_methods = PUT,POST,GET
backoff_factor = 0.2
status_forcelist = 429,500,502,503,504
timeout = 30
allow_insecure_http = false

[keys]
https://hosted.weblate.org/api/ = APIKEY
```

## Environment variables

The API URL and key can also be configured using environment variables. This is
especially useful for CI workflows where `WLC_KEY` is injected as a secret:

- `WLC_URL` — API URL
- `WLC_KEY` — API key
- `WLC_ALLOW_INSECURE_HTTP` — set to `1`, `true`, `yes`, or `on` to allow
  API keys over non-local HTTP URLs

When the API URL comes from automatically discovered project configuration
(`.weblate`, `.weblate.ini`, or `weblate.ini` in the current directory or a
parent directory), unscoped secrets must pin the destination explicitly:
`WLC_KEY` requires `WLC_URL`, and `--key` requires `--url`. URL-scoped keys in
the `[keys]` section continue to work with project configuration.

The configuration precedence (highest to lowest) is:

1. Command-line arguments (`--url`, `--key`)
1. Environment variables (`WLC_URL`, `WLC_KEY`)
1. Configuration loaded from `--config`, or from XDG/user config plus the
   nearest project config when `--config` is not used

API keys are rejected over non-local `http://` URLs by default. Use HTTPS, a
loopback HTTP URL for local development, or explicitly opt in with
`--allow-insecure-http`, `WLC_ALLOW_INSECURE_HTTP`, or `allow_insecure_http`.
Automatically discovered project configuration cannot enable
`allow_insecure_http`; set it in user configuration or pass an explicit
`--config` file instead.

## Docker image

The image is published on [Docker Hub](https://hub.docker.com/r/weblate/wlc).

Building locally:

```console
docker build -t weblate/wlc .
```

Detailed documentation is available in [Weblate documentation](https://docs.weblate.org/en/latest/wlc.html#docker-wlc).

## Docker hub tags

You can use following tags on Docker hub:

| Tag name | Description                                                                       | Use case                                        |
| -------- | --------------------------------------------------------------------------------- | ----------------------------------------------- |
| `latest` | wlc stable release, matches latest tagged release                                 | Rolling updates in a production environment     |
| `edge`   | wlc development                                                                   | Staging environment                             |
| version  | wlc stable release, see [weblate/wlc](https://hub.docker.com/r/weblate/wlc/tags/) | Well defined deploy in a production environment |

Every image is tested by our CI before it gets published, so even the `bleeding` version should be quite safe to use.

## Contributing

Contributions are welcome! See [documentation](https://docs.weblate.org/en/latest/contributing/modules.html) for more information.
