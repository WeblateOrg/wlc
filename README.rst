wlc
===

`Weblate`_ commandline client using `Weblate's REST API`_.

.. image:: https://travis-ci.org/nijel/wlc.svg?branch=master
    :target: https://travis-ci.org/nijel/wlc
    :alt: Build Status

.. image:: https://landscape.io/github/nijel/wlc/master/landscape.svg?style=flat
    :target: https://landscape.io/github/nijel/wlc/master
    :alt: Code Health

.. image:: http://codecov.io/github/nijel/wlc/coverage.svg?branch=master
    :target: http://codecov.io/github/nijel/wlc?branch=master
    :alt: Code coverage

.. image:: https://img.shields.io/pypi/dm/wlc.svg
    :target: https://pypi.python.org/pypi/wlc
    :alt: PyPI package

.. image:: https://hosted.weblate.org/widgets/weblate/-/svg-badge.svg
    :alt: Translation status
    :target: https://hosted.weblate.org/engage/weblate/?utm_source=widget

.. image:: https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat
    :alt: Documentation
    :target: https://docs.weblate.org/en/latest/wlc.html

Installation
------------

Install using pip:

.. code-block:: sh

    pip3 install wlc

Sources are available at <https://github.com/nijel/wlc>.

Usage
-----

Please see `Weblate documentation`_ for more complete documentation.

Command line usage:

.. code-block:: sh

    wlc list-projects
    wlc list-subprojects
    wlc list-translations
    wlc show
    wlc ls
    wlc commit
    wlc push
    wlc repo
    wlc stats

Configuration is stored in ``~/.config/weblate``:

.. code-block:: ini

    [weblate]
    url = https://hosted.weblate.org/api/

    [keys]
    https://hosted.weblate.org/api/ = APIKEY

.. _Weblate's REST API: https://docs.weblate.org/en/latest/api.html
.. _Weblate documentation: https://docs.weblate.org/en/latest/wlc.html
.. _Weblate: https://weblate.org/
