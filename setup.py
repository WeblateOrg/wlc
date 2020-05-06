#!/usr/bin/env python3
#
# Copyright © 2012 - 2020 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate Client <https://github.com/WeblateOrg/wlc>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Setup file for easy installation."""

from setuptools import setup

VERSION = None
with open("wlc/__init__.py") as handle:
    for line in handle.readlines():
        if line.startswith("__version__"):
            VERSION = line.split("=")[1].strip().strip('"')
            break

with open("README.rst") as handle:
    LONG_DESCRIPTION = handle.read()

with open("requirements.txt") as handle:
    REQUIRES = handle.read().split()

setup(
    name="wlc",
    version=VERSION,
    author="Michal Čihař",
    author_email="michal@cihar.com",
    description=(
        "A command line utility for Weblate, "
        "translation tool with tight version control integration"
    ),
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/x-rst",
    license="GPLv3+",
    keywords="i18n l10n gettext git mercurial translate",
    url="https://weblate.org/",
    download_url="https://github.com/WeblateOrg/wlc",
    project_urls={
        "Issue Tracker": "https://github.com/WeblateOrg/wlc/issues",
        "Documentation": "https://docs.weblate.org/",
        "Source Code": "https://github.com/WeblateOrg/wlc",
        "Twitter": "https://twitter.com/WeblateOrg",
    },
    platforms=["any"],
    packages=["wlc"],
    package_dir={"wlc": "wlc"},
    install_requires=REQUIRES,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Internationalization",
        "Topic :: Software Development :: Localization",
        "Topic :: Utilities",
    ],
    entry_points={"console_scripts": ["wlc = wlc.main:main"]},
    python_requires=">=3.6",
)
