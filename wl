#!/usr/bin/env python3

# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Simple wrapper to execute wlc command-line."""

import sys

import wlc.main

sys.exit(wlc.main.main())
