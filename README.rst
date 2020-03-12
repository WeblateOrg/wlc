.. image:: https://s.weblate.org/cdn/Logo-Darktext-borders.png
   :alt: Weblate
   :target: https://weblate.org/
   :height: 80px

**Weblate is a copylefted libre software web-based continuous localization system,
used by over 1150 libre projects and companies in more than 115 countries.**


wlc is a `Weblate`_ commandline client using `Weblate's REST API`_.

.. image:: https://img.shields.io/badge/website-weblate.org-blue.svg
    :alt: Website
    :target: https://weblate.org/

.. image:: https://hosted.weblate.org/widgets/weblate/-/svg-badge.svg
    :alt: Translation status
    :target: https://hosted.weblate.org/engage/weblate/?utm_source=widget

.. image:: https://bestpractices.coreinfrastructure.org/projects/552/badge
    :alt: CII Best Practices
    :target: https://bestpractices.coreinfrastructure.org/projects/552

.. image:: https://img.shields.io/pypi/v/wlc.svg
    :target: https://pypi.org/project/wlc/
    :alt: PyPI package

.. image:: https://readthedocs.org/projects/weblate/badge/
    :alt: Documentation
    :target: https://docs.weblate.org/en/latest/wlc.html

Installation
------------

Install using pip:

.. code-block:: sh

    pip3 install wlc

Sources are available at <https://github.com/WeblateOrg/wlc>.

Usage
-----

Please see `Weblate documentation`_ for more complete documentation.

Command line usage:

.. code-block:: sh

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

Configuration is stored in ``~/.config/weblate``:

.. code-block:: ini

    [weblate]
    url = https://hosted.weblate.org/api/

    [keys]
    https://hosted.weblate.org/api/ = APIKEY

.. _Weblate's REST API: https://docs.weblate.org/en/latest/api.html
.. _Weblate documentation: https://docs.weblate.org/en/latest/wlc.html
.. _Weblate: https://weblate.org/
