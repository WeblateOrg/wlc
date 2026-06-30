# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Weblate API library, configuration."""

from __future__ import annotations

import os.path
from configparser import NoOptionError, RawConfigParser
from io import StringIO
from typing import TYPE_CHECKING, Literal, TypeAlias, cast

from xdg.BaseDirectory import load_first_config

from .const import API_URL

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["NoOptionError", "WLCConfigurationError", "WeblateConfig"]

RequestOptions: TypeAlias = tuple[int, list[int] | None, list[str], float, int]
URLSource: TypeAlias = Literal["default", "cli", "env", "explicit", "user", "project"]
KeySource: TypeAlias = Literal["none", "cli", "env", "keys"]


class WLCConfigurationError(Exception):
    """Configuration could not be loaded or combines unsafe option sources."""


class WeblateConfig(RawConfigParser):
    """
    Configuration parser wrapper with defaults.

    :param section: Configuration section to use.

    The parser loads user configuration, optional project configuration, and
    command-line or environment overrides. API keys in project configuration are
    constrained so unscoped secrets can not be paired with a project-provided
    API URL.
    """

    def __init__(self, section: str = "weblate") -> None:
        """Construct WeblateConfig object."""
        super().__init__(delimiters=("=",))
        self.section: str = section
        self.cli_key: str | None = None
        self.cli_url: str | None = None
        self.cli_allow_insecure_http = False
        self._config_url_source: URLSource = "default"
        self.set_defaults()

    def set_defaults(self) -> None:
        """Set default values."""
        self.add_section("keys")
        self.add_section(self.section)
        self.set(self.section, "url", API_URL)
        self.set(self.section, "retries", "0")
        self.set(self.section, "timeout", "300")
        self.set(self.section, "status_forcelist", None)
        self.set(self.section, "allowed_methods", "HEAD\nDELETE\nOPTIONS\nPUT\nGET")
        self.set(self.section, "backoff_factor", "0")
        self.set(self.section, "allow_insecure_http", "false")

    @staticmethod
    def find_config() -> str | None:
        """Find the first user configuration file."""
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

    def _read_config(self, path: Path | str, url_source: URLSource) -> list[str]:
        """Read configuration and remember whether it supplied the API URL."""
        parser = RawConfigParser(delimiters=("=",))
        loaded = parser.read(path)
        if not loaded:
            return loaded

        if url_source == "project":
            parser.remove_option(parser.default_section, "allow_insecure_http")
            if parser.has_section(self.section):
                parser.remove_option(self.section, "allow_insecure_http")
        config_data = StringIO()
        parser.write(config_data)
        config_data.seek(0)
        self.read_file(config_data)
        if parser.has_option(self.section, "url"):
            self._config_url_source = url_source

        return loaded

    def load(self, path: Path | str | None = None) -> None:
        """
        Load configuration from an explicit path or discovered locations.

        When ``path`` is specified, only that file is loaded. Otherwise the user
        configuration is loaded first, followed by the nearest project
        configuration file from the current directory or its parents.
        """
        if path:
            loaded = self._read_config(path, "explicit")
            if not loaded:
                raise WLCConfigurationError(
                    f"Could not read configuration file: {os.path.abspath(path)}"
                )
        else:
            if config := self.find_config():
                self._read_config(config, "user")
            if config := self.find_project_config():
                self._read_config(config, "project")

        if self.has_option(self.section, "key"):
            raise WLCConfigurationError(
                "Using 'key' in settings is insecure, use [keys] section instead."
            )

    def _get_url_key_sources(self) -> tuple[str, URLSource, str, KeySource]:
        """Get API URL, key, and their sources."""
        if self.cli_url:
            url = self.cli_url
            url_source: URLSource = "cli"
        elif env_url := os.environ.get("WLC_URL", ""):
            url = env_url
            url_source = "env"
        else:
            url = cast("str", self.get(self.section, "url"))
            url_source = self._config_url_source

        if self.cli_key:
            key = self.cli_key
            key_source: KeySource = "cli"
        elif env_key := os.environ.get("WLC_KEY", ""):
            key = env_key
            key_source = "env"
        else:
            key = cast("str", self.get("keys", url, fallback=""))
            key_source = "keys" if key else "none"

        if url_source == "project":
            if key_source == "cli":
                raise WLCConfigurationError(
                    "Using --key with project configuration requires --url."
                )
            if key_source == "env":
                raise WLCConfigurationError(
                    "Using WLC_KEY with project configuration requires WLC_URL."
                )

        return url, url_source, key, key_source

    def validate_url_key(self) -> None:
        """
        Validate URL and key source combination.

        When the API URL comes from automatically discovered project
        configuration, unscoped keys must pin the destination explicitly:
        ``WLC_KEY`` requires ``WLC_URL``, and a command-line key requires a
        command-line URL.
        """
        self._get_url_key_sources()

    def get_url_key(self) -> tuple[str, str]:
        """Get the resolved API URL and API key."""
        url, _url_source, key, _key_source = self._get_url_key_sources()
        return url, key

    def get_request_options(self) -> RequestOptions:
        """Get request retry and timeout options."""
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

    def get_allow_insecure_http(self) -> bool:
        """
        Return whether authenticated non-local HTTP URLs are allowed.

        The insecure HTTP opt-in is enable-only: a command-line flag, a true
        ``WLC_ALLOW_INSECURE_HTTP`` value, or trusted configuration can enable
        it. False or unset command-line and environment sources do not disable a
        configuration opt-in. Automatically discovered project configuration can
        not enable it.
        """
        if self.cli_allow_insecure_http:
            return True
        if os.environ.get("WLC_ALLOW_INSECURE_HTTP", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return True
        return self.getboolean(self.section, "allow_insecure_http")
