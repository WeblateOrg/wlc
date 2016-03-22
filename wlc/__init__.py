# -*- coding: utf-8 -*-
#
# Copyright © 2016 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate Clinet <https://github.com/nijel/wlc>
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
"""Weblate API client library."""
from __future__ import unicode_literals

try:
    from urllib import urlencode, urlopen
except ImportError:
    from urllib.parse import urlencode
    from urllib.request import urlopen

import json

__version__ = 0.0

API_URL = 'http://127.0.0.1:8000/api/'
USER_AGENT = 'wlc/{0}'.format(__version__)


class Weblate(object):
    def __init__(self, user='', password='', url=API_URL, config=None):
        """Create the object, storing user and API password."""
        if config is not None:
            self.user = config.get(config.section, 'user')
            self.password = config.get(config.section, 'password')
            self.url = config.get(config.section, 'url')
        else:
            self.user = user
            self.password = password
            self.url = url

