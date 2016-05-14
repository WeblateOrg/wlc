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
"""Weblate API library, configuration."""

import os.path

from configparser import RawConfigParser, NoOptionError

from xdg.BaseDirectory import load_config_paths

import wlc

__all__ = ['NoOptionError', 'WeblateConfig']


class WeblateConfig(RawConfigParser):

    """Configuration parser wrapper with defaults."""

    def __init__(self, section='weblate'):
        """Construct WeblateConfig object."""
        RawConfigParser.__init__(self, delimiters=('=',))
        self.section = section
        self.set_defaults()

    def set_defaults(self):
        """Set default values."""
        self.add_section('keys')
        self.add_section(self.section)
        self.set(self.section, 'key', '')
        self.set(self.section, 'url', wlc.API_URL)

    def load(self, path=None):
        """Load configuration from XDG paths."""
        if path is None:
            path = load_config_paths('weblate')
        self.read(path)

        # Try reading from current dir
        cwd = os.path.abspath('.')
        prev = None
        while cwd != prev:
            conf_name = os.path.join(cwd, '.weblate')
            if os.path.exists(conf_name):
                self.read(conf_name)
                break
            prev = cwd
            cwd = os.path.dirname(cwd)

    def get_url_key(self):
        """Returns API URL and key"""
        url = self.get(self.section, 'url')
        key = self.get(self.section, 'key')
        if not key:
            try:
                key = self.get('keys', url)
            except NoOptionError:
                key = ''
        return url, key
