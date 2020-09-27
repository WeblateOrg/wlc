<!-- markdownlint-disable -->

<a href="https://weblate.org/"><img alt="Weblate" src="https://s.weblate.org/cdn/Logo-Darktext-borders.png" height="80px" /></a>

**Weblate is a copylefted libre software web-based continuous localization system,
used by over 1150 libre projects and companies in more than 115 countries.**

<!-- markdownlint-restore -->

# Official Docker container for wlc

[![Website](https://img.shields.io/badge/website-weblate.org-blue.svg)](https://weblate.org/)
[![Translation status](https://hosted.weblate.org/widgets/weblate/-/svg-badge.svg)](https://hosted.weblate.org/engage/weblate/?utm_source=widget)
[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/552/badge)](https://bestpractices.coreinfrastructure.org/projects/552)
[![Docker Layers](https://images.microbadger.com/badges/image/weblate/wlc.svg)](https://microbadger.com/images/weblate/wlc)
[![Documenation](https://readthedocs.org/projects/weblate/badge/)](https://docs.weblate.org/en/latest/wlc.html)

## Docker hub tags

You can use following tags on Docker hub:

| Tag name | Description                                                                       | Use case                                        |
| -------- | --------------------------------------------------------------------------------- | ----------------------------------------------- |
| `latest` | wlc stable release, matches latest tagged release                                 | Rolling updates in a production environment     |
| `edge`   | wlc development                                                                   | Staging environment                             |
| version  | wlc stable release, see [weblate/wlc](https://hub.docker.com/r/weblate/wlc/tags/) | Well defined deploy in a production environment |

Every image is tested by our CI before it gets published, so even the `bleeding` version should be quite safe to use.

## Documentation

Detailed documentation is available in Weblate documentation:

<https://docs.weblate.org/en/latest/wlc.html#docker-wlc>
