#
# Copyright © 2012–2022 Michal Čihař <michal@cihar.com>
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
"""Weblate API library, configuration."""

import os.path
from configparser import NoOptionError, RawConfigParser

from xdg.BaseDirectory import load_config_paths

import wlc

__all__ = ["NoOptionError", "WeblateConfig"]


class WeblateConfig(RawConfigParser):
    """Configuration parser wrapper with defaults."""

    def __init__(self, section="weblate"):
        """Construct WeblateConfig object."""
        super().__init__(delimiters=("=",))
        self.section = section
        self.set_defaults()

    def set_defaults(self):
        """Set default values."""
        self.add_section("keys")
        self.add_section(self.section)
        self.set(self.section, "key", "")
        self.set(self.section, "url", wlc.API_URL)
        self.set(self.section, "retries", 0)
        self.set(self.section, "timeout", 30)
        self.set(self.section, "status_forcelist", None)
        self.set(
            self.section, "method_whitelist", "HEAD\nTRACE\nDELETE\nOPTIONS\nPUT\nGET"
        )
        self.set(self.section, "backoff_factor", 0)

    @staticmethod
    def find_configs():
        # Handle Windows specifically
        if "APPDATA" in os.environ:
            win_path = os.path.join(os.environ["APPDATA"], "weblate.ini")
            if os.path.exists(win_path):
                yield win_path

        # Generic XDG paths
        yield from load_config_paths("weblate")
        yield from load_config_paths("weblate.ini")

    def load(self, path=None):
        """Load configuration from XDG paths."""
        if path is None:
            path = list(self.find_configs())
        self.read(path)

        # Try reading from current dir
        cwd = os.path.abspath(".")
        prev = None
        while cwd != prev:
            for name in (".weblate", ".weblate.ini", "weblate.ini"):
                conf_name = os.path.join(cwd, name)
                if os.path.exists(conf_name):
                    self.read(conf_name)
                    break
            prev = cwd
            cwd = os.path.dirname(cwd)

    def get_url_key(self):
        """Get API URL and key."""
        url = self.get(self.section, "url")
        key = self.get(self.section, "key")
        if not key:
            try:
                key = self.get("keys", url)
            except NoOptionError:
                key = ""
        return url, key

    def get_request_options(self):
        retries = int(self.get(self.section, "retries"))
        timeout = int(self.get(self.section, "timeout"))
        status_forcelist = self.get(self.section, "status_forcelist")
        if status_forcelist is not None:
            status_forcelist = [int(option) for option in status_forcelist.split(",")]
        method_whitelist = self.get(self.section, "method_whitelist").split(",")
        backoff_factor = float(self.get(self.section, "backoff_factor"))
        return retries, status_forcelist, method_whitelist, backoff_factor, timeout
