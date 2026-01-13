# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Weblate API library, configuration."""

from __future__ import annotations

import os.path
from configparser import NoOptionError, RawConfigParser
from typing import TYPE_CHECKING, cast

from xdg.BaseDirectory import load_first_config

import wlc

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["NoOptionError", "WLCConfigurationError", "WeblateConfig"]


class WLCConfigurationError(Exception):
    """Error in the configuration file."""


class WeblateConfig(RawConfigParser):
    """Configuration parser wrapper with defaults."""

    def __init__(self, section: str = "weblate") -> None:
        """Construct WeblateConfig object."""
        super().__init__(delimiters=("=",))
        self.section: str = section
        self.cli_key: str | None = None
        self.cli_url: str | None = None
        self.set_defaults()

    def set_defaults(self) -> None:
        """Set default values."""
        self.add_section("keys")
        self.add_section(self.section)
        self.set(self.section, "url", wlc.API_URL)
        self.set(self.section, "retries", "0")
        self.set(self.section, "timeout", "300")
        self.set(self.section, "status_forcelist", None)
        self.set(
            self.section, "method_whitelist", "HEAD\nTRACE\nDELETE\nOPTIONS\nPUT\nGET"
        )
        self.set(self.section, "backoff_factor", "0")

    @staticmethod
    def find_config() -> str | None:
        # Handle Windows specifically
        for envname in ("APPDATA", "LOCALAPPDATA"):
            if path := os.environ.get(envname):
                win_path = os.path.join(path, "weblate.ini")
                if os.path.exists(win_path):
                    return win_path

        # Generic XDG paths
        for filename in ("weblate", "weblate.ini"):
            if config := load_first_config(filename):
                return config

        return None

    def load(self, path: Path | str | None = None) -> None:
        """Load configuration from XDG paths and current directory."""
        if path is None:
            path = self.find_config()
        if path:
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

        if self.has_option(self.section, "key"):
            raise WLCConfigurationError(
                "Using 'key' in settings is insecure, use [keys] section instead."
            )

    def get_url_key(self) -> tuple[str, str]:
        """Get API URL and key."""
        url = self.cli_url or cast("str", self.get(self.section, "url"))
        key = self.cli_key or cast("str", self.get("keys", url, fallback=""))
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
