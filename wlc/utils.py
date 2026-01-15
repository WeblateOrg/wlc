# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Utility helpers."""

from __future__ import annotations

import re

# This matches Django's SlugField validation minus dash which is
# excluded by Weblate's validate_slug
NON_SLUG_RE = re.compile(r"[^a-zA-Z0-9_]")


def sanitize_slug(slug: str) -> str:
    """Sanitize slug for safe use as a filename component."""
    return NON_SLUG_RE.sub("-", slug)
