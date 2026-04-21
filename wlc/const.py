# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Package constants."""

__version__ = "2.0.0"

URL = "https://weblate.org/"
DEVEL_URL = "https://github.com/WeblateOrg/wlc"
# Local development default (loopback only); intentionally HTTP.
API_URL = "http://127.0.0.1:8000/api/"
USER_AGENT = f"wlc/{__version__}"
LOCALHOST_ADDRESSES = {"127.0.0.1", "localhost", "::1", "[::1]"}

TIMESTAMPS = {"last_change"}
