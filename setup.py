#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright © 2016 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate Client <https://github.com/nijel/wlc>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Setup file for easy installation."""
from setuptools import setup
import os

VERSION = __import__('wlc').__version__

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    LONG_DESCRIPTION = readme.read()

REQUIRES = open('requirements.txt').read().split()

setup(
    name='wlc',
    version=VERSION,
    author='Michal Čihař',
    author_email='michal@cihar.com',
    description=(
        'A command line utility for Weblate, '
        'translation tool with tight version control integration'
    ),
    license='GPLv3+',
    keywords='i18n l10n gettext git mercurial translate',
    url='https://weblate.org/',
    download_url='https://pypi.python.org/pypi/wlc',
    bugtrack_url='https://github.com/nijel/wlc/issues',
    platforms=['any'],
    packages=[
        'wlc',
    ],
    package_dir={'wlc': 'wlc'},
    long_description=LONG_DESCRIPTION,
    install_requires=REQUIRES,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Topic :: Software Development :: Internationalization',
        'Topic :: Software Development :: Localization',
        'Topic :: Utilities',
        'License :: OSI Approved :: '
        'GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],

    entry_points={
        'console_scripts': ['wlc = wlc.main:main']
    },
)
