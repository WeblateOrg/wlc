#!/usr/bin/env python3

# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Setup file for easy installation."""

from setuptools import setup

with open("requirements.txt") as handle:
    REQUIRES = handle.read().split()

setup(install_requires=REQUIRES)
