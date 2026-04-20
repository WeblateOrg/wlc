# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Weblate API client library."""

from .client import Weblate
from .const import (
    API_URL,
    DEVEL_URL,
    LOCALHOST_ADDRESSES,
    TIMESTAMPS,
    URL,
    USER_AGENT,
    __version__,
)
from .exceptions import (
    WeblateDeniedError,
    WeblateException,
    WeblatePermissionError,
    WeblateThrottlingError,
)
from .models import (
    Category,
    Change,
    Component,
    Language,
    LanguageStats,
    Project,
    ProjectRepository,
    Repository,
    Statistics,
    Translation,
    TranslationStatistics,
    Unit,
)

__all__ = [
    "API_URL",
    "DEVEL_URL",
    "LOCALHOST_ADDRESSES",
    "TIMESTAMPS",
    "URL",
    "USER_AGENT",
    "Category",
    "Change",
    "Component",
    "Language",
    "LanguageStats",
    "Project",
    "ProjectRepository",
    "Repository",
    "Statistics",
    "Translation",
    "TranslationStatistics",
    "Unit",
    "Weblate",
    "WeblateDeniedError",
    "WeblateException",
    "WeblatePermissionError",
    "WeblateThrottlingError",
    "__version__",
]
