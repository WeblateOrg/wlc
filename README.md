<a href="https://weblate.org/"><img alt="Weblate" src="https://s.weblate.org/cdn/Logo-Darktext-borders.png" height="80px" /></a>

**Weblate is a copylefted libre software web-based continuous localization system,
used by over 2500 libre projects and companies in more than 165 countries.**

# wlc

wlc is a [Weblate](https://weblate.org/) commandline client using [Weblate's REST API](https://docs.weblate.org/en/latest/api.html).

[![Website](https://img.shields.io/badge/website-weblate.org-blue.svg)](https://weblate.org/)
[![Translation status](https://hosted.weblate.org/widgets/weblate/-/svg-badge.svg)](https://hosted.weblate.org/engage/weblate/?utm_source=widget)
[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/552/badge)](https://bestpractices.coreinfrastructure.org/projects/552)
[![Docker Layers](https://images.microbadger.com/badges/image/weblate/wlc.svg)](https://microbadger.com/images/weblate/wlc)
[![PyPI package](https://img.shields.io/pypi/v/wlc.svg)](https://pypi.org/project/wlc/)
[![Documenation](https://readthedocs.org/projects/weblate/badge/)](https://docs.weblate.org/en/latest/wlc.html)

## PIP Installation

Install using pip:

    pip3 install wlc

Sources are available at <https://github.com/WeblateOrg/wlc>.

## Usage

Please see [Weblate documentation](https://docs.weblate.org/en/latest/wlc.html) for more complete documentation.

Command line usage:

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

Configuration is stored in `~/.config/weblate`. The key/values (`retries`,
`timeout`, `method_whitelist`, `backoff_factor`, `status_forcelist`) are closely
coupled with the [urllib3 parameters](https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html) and allows the user to configure request
parameters.

    [weblate]
    url = https://hosted.weblate.org/api/
    retries = 3
    method_whitelist = PUT,POST,GET
    backoff_factor = 0.2
    status_forcelist = 429,500,502,503,504
    timeout = 30

    [keys]
    https://hosted.weblate.org/api/ = APIKEY

## Docker image

The image is published on [Docker Hub](https://hub.docker.com/r/weblate/wlc).

Building locally:

    docker build -t weblate/wlc .

Detailed documentation is available in [Weblate documentation](https://docs.weblate.org/en/latest/wlc.html#docker-wlc).

## Docker hub tags

You can use following tags on Docker hub:

| Tag name | Description                                                                       | Use case                                        |
| -------- | --------------------------------------------------------------------------------- | ----------------------------------------------- |
| `latest` | wlc stable release, matches latest tagged release                                 | Rolling updates in a production environment     |
| `edge`   | wlc development                                                                   | Staging environment                             |
| version  | wlc stable release, see [weblate/wlc](https://hub.docker.com/r/weblate/wlc/tags/) | Well defined deploy in a production environment |

Every image is tested by our CI before it gets published, so even the `bleeding` version should be quite safe to use.
