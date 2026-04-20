# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Weblate API library, configuration."""

from __future__ import annotations

import os.path
from configparser import NoOptionError, RawConfigParser
from typing import TYPE_CHECKING, TypeAlias, cast

from xdg.BaseDirectory import load_first_config

from .const import API_URL

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["NoOptionError", "WLCConfigurationError", "WeblateConfig"]

RequestOptions: TypeAlias = tuple[int, list[int] | None, list[str], float, int]


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
        self.set(self.section, "url", API_URL)
        self.set(self.section, "retries", "0")
        self.set(self.section, "timeout", "300")
        self.set(self.section, "status_forcelist", None)
        self.set(
            self.section, "allowed_methods", "HEAD\nTRACE\nDELETE\nOPTIONS\nPUT\nGET"
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

    @staticmethod
    def find_project_config() -> str | None:
        """Find the nearest project configuration file."""
        cwd = os.path.abspath(".")
        prev = None
        while cwd != prev:
            for name in (".weblate", ".weblate.ini", "weblate.ini"):
                conf_name = os.path.join(cwd, name)
                if os.path.isfile(conf_name):
                    return conf_name
            prev = cwd
            cwd = os.path.dirname(cwd)

        return None

    def load(self, path: Path | str | None = None) -> None:
        """Load configuration from an explicit path or discovered locations."""
        if path:
            loaded = self.read(path)
            if not loaded:
                raise WLCConfigurationError(
                    f"Could not read configuration file: {os.path.abspath(path)}"
                )
        else:
            if config := self.find_config():
                self.read(config)
            if config := self.find_project_config():
                self.read(config)

        if self.has_option(self.section, "key"):
            raise WLCConfigurationError(
                "Using 'key' in settings is insecure, use [keys] section instead."
            )

    def get_url_key(self) -> tuple[str, str]:
        """Get API URL and key."""
        url = (
            self.cli_url
            or os.environ.get("WLC_URL", "")
            or cast("str", self.get(self.section, "url"))
        )
        key = (
            self.cli_key
            or os.environ.get("WLC_KEY", "")
            or cast("str", self.get("keys", url, fallback=""))
        )
        return url, key

    def get_request_options(self) -> RequestOptions:
        retries = int(self.get(self.section, "retries"))
        timeout = int(self.get(self.section, "timeout"))
        status_forcelist = self.get(self.section, "status_forcelist")
        if status_forcelist is not None:
            status_forcelist = [int(option) for option in status_forcelist.split(",")]
        allowed_methods = [
            method
            for chunk in self.get(self.section, "allowed_methods").split(",")
            for method in chunk.split()
        ]
        backoff_factor = float(self.get(self.section, "backoff_factor"))
        return retries, status_forcelist, allowed_methods, backoff_factor, timeout
