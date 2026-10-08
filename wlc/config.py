# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Weblate API library, configuration."""

from __future__ import annotations

import os
from configparser import NoOptionError, RawConfigParser
from io import StringIO
from pathlib import Path
from typing import Literal, TypeAlias, cast

from urllib3.exceptions import LocationParseError
from urllib3.util import parse_url
from xdg.BaseDirectory import load_first_config

from .const import API_URL

__all__ = ["NoOptionError", "WLCConfigurationError", "WeblateConfig"]

RequestOptions: TypeAlias = tuple[int, list[int] | None, list[str], float, int]
URLSource: TypeAlias = Literal["default", "cli", "env", "explicit", "user", "project"]
KeySource: TypeAlias = Literal["none", "cli", "env", "keys"]
Origin: TypeAlias = tuple[str, str, int]

INSECURE_HTTP_SECTION = "insecure_http"
INSECURE_SSL_SECTION = "insecure_ssl"
INSECURE_ENV_VALUES = {"1", "true", "yes", "on"}


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
        self.cli_allow_insecure_ssl = False
        self._config_url_source: URLSource = "default"
        self.set_defaults()

    def set_defaults(self) -> None:
        """Set default values."""
        self.add_section("keys")
        self.add_section(INSECURE_HTTP_SECTION)
        self.add_section(INSECURE_SSL_SECTION)
        self.add_section(self.section)
        self.set(self.section, "url", API_URL)
        self.set(self.section, "retries", "0")
        self.set(self.section, "timeout", "300")
        self.set(self.section, "status_forcelist", None)
        self.set(self.section, "allowed_methods", "HEAD\nDELETE\nOPTIONS\nPUT\nGET")
        self.set(self.section, "backoff_factor", "0")

    @staticmethod
    def find_config() -> Path | None:
        """Return the first user configuration file as a Path, or None."""
        # Handle Windows specifically
        for envname in ("APPDATA", "LOCALAPPDATA"):
            if path := os.environ.get(envname):
                win_path = Path(path) / "weblate.ini"
                if win_path.exists():
                    return win_path

        # Generic XDG paths
        for filename in ("weblate", "weblate.ini"):
            if config := load_first_config(filename):
                return Path(config)

        return None

    @staticmethod
    def find_project_config() -> Path | None:
        """Return the nearest project configuration file as a Path, or None."""
        cwd = Path.cwd()
        prev = None
        while cwd != prev:
            for name in (".weblate", ".weblate.ini", "weblate.ini"):
                conf_name = cwd / name
                if conf_name.is_file():
                    return conf_name
            prev = cwd
            cwd = cwd.parent

        return None

    def _read_config(self, path: Path | str, url_source: URLSource) -> list[str]:
        """Read configuration and remember whether it supplied the API URL."""
        parser = RawConfigParser(delimiters=("=",))
        loaded = parser.read(path)
        if not loaded:
            return loaded

        if url_source == "project":
            parser.remove_section(INSECURE_HTTP_SECTION)
            parser.remove_section(INSECURE_SSL_SECTION)
            for option in ("allow_insecure_http", "allow_insecure_ssl"):
                parser.remove_option(parser.default_section, option)
            if parser.has_section(self.section):
                for option in ("allow_insecure_http", "allow_insecure_ssl"):
                    parser.remove_option(self.section, option)
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
                msg = f"Could not read configuration file: {Path(path).absolute()}"
                raise WLCConfigurationError(msg)
        else:
            if config := self.find_config():
                self._read_config(config, "user")
            if config := self.find_project_config():
                self._read_config(config, "project")

        if self.has_option(self.section, "key"):
            msg = "Using 'key' in settings is insecure, use [keys] section instead."
            raise WLCConfigurationError(msg)
        self._validate_insecure_configuration()

    @staticmethod
    def _environment_enabled(name: str) -> bool:
        """Return whether an enable-only environment option is set."""
        return os.environ.get(name, "").lower() in INSECURE_ENV_VALUES

    @staticmethod
    def _normalize_origin(
        value: str, expected_scheme: str, *, allow_auth: bool = False
    ) -> Origin:
        """Normalize a configured URL to scheme, host, and effective port."""
        section = (
            INSECURE_SSL_SECTION
            if expected_scheme == "https"
            else INSECURE_HTTP_SECTION
        )
        try:
            url = parse_url(value)
            explicit_port = url.port
        except (LocationParseError, ValueError) as error:
            msg = f"Invalid origin in [{section}]: {value}"
            raise WLCConfigurationError(msg) from error
        if (
            url.scheme != expected_scheme
            or url.host is None
            or (url.auth is not None and not allow_auth)
        ):
            msg = f"Invalid origin in [{section}]: {value}"
            raise WLCConfigurationError(msg)
        port = (
            explicit_port
            if explicit_port is not None
            else (443 if expected_scheme == "https" else 80)
        )
        return expected_scheme, url.host.strip("[]").lower(), port

    @classmethod
    def _parse_boolean(cls, section: str, option: str, value: str | None) -> bool:
        """Parse a boolean security setting and fail closed on invalid values."""
        normalized = "" if value is None else value.lower()
        if normalized not in cls.BOOLEAN_STATES:
            msg = f"Invalid boolean value for [{section}] {option}: {value}"
            raise WLCConfigurationError(msg)
        return cls.BOOLEAN_STATES[normalized]

    def _validate_legacy_insecure_option(self, option: str, section: str) -> None:
        """Reject enabled global insecure settings in trusted configuration."""
        if not self.has_option(self.section, option):
            return
        value = self.get(self.section, option, raw=True)
        if self._parse_boolean(self.section, option, value):
            msg = (
                f"Global '{option}' is not supported; configure the trusted origin "
                f"in [{section}] instead."
            )
            raise WLCConfigurationError(msg)

    def _direct_section_items(self, section: str) -> dict[str, str | None]:
        """Return section-local entries without ConfigParser DEFAULT inheritance."""
        sections = cast("dict[str, dict[str, str | None]]", vars(self)["_sections"])
        return sections.get(section, {})

    def _validate_insecure_section(self, section: str, scheme: str) -> None:
        """Validate all entries in an origin-scoped insecure section."""
        for option, value in self._direct_section_items(section).items():
            self._normalize_origin(option, scheme)
            self._parse_boolean(section, option, value)

    def _validate_insecure_configuration(self) -> None:
        """Validate trusted origin-scoped transport exceptions."""
        self._validate_legacy_insecure_option(
            "allow_insecure_http", INSECURE_HTTP_SECTION
        )
        self._validate_legacy_insecure_option(
            "allow_insecure_ssl", INSECURE_SSL_SECTION
        )
        self._validate_insecure_section(INSECURE_HTTP_SECTION, "http")
        self._validate_insecure_section(INSECURE_SSL_SECTION, "https")

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
            self._validate_project_overrides(key_source)

        return url, url_source, key, key_source

    def _validate_project_overrides(self, key_source: KeySource) -> None:
        """Require unscoped secrets and security flags to pin project URLs."""
        if key_source == "cli":
            msg = "Using --key with project configuration requires --url."
            raise WLCConfigurationError(msg)
        if key_source == "env":
            msg = "Using WLC_KEY with project configuration requires WLC_URL."
            raise WLCConfigurationError(msg)
        for cli_enabled, option in (
            (self.cli_allow_insecure_http, "--allow-insecure-http"),
            (self.cli_allow_insecure_ssl, "--allow-insecure-ssl"),
        ):
            if cli_enabled:
                msg = f"Using {option} with project configuration requires --url."
                raise WLCConfigurationError(msg)
        for env_enabled, option in (
            (
                self._environment_enabled("WLC_ALLOW_INSECURE_HTTP"),
                "WLC_ALLOW_INSECURE_HTTP",
            ),
            (
                self._environment_enabled("WLC_ALLOW_INSECURE_SSL"),
                "WLC_ALLOW_INSECURE_SSL",
            ),
        ):
            if env_enabled:
                msg = f"Using {option} with project configuration requires WLC_URL."
                raise WLCConfigurationError(msg)

    def validate_url_key(self) -> None:
        """
        Validate URL and key source combination.

        When the API URL comes from automatically discovered project
        configuration, unscoped keys must pin the destination explicitly:
        ``WLC_KEY`` requires ``WLC_URL``, and a command-line key requires a
        command-line URL.
        """
        self._validate_insecure_configuration()
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

        The insecure HTTP opt-in is enable-only. Persistent configuration is
        scoped to the selected network origin.
        """
        return self._get_allow_insecure(
            INSECURE_HTTP_SECTION,
            "http",
            cli_enabled=self.cli_allow_insecure_http,
            env_name="WLC_ALLOW_INSECURE_HTTP",
        )

    def get_allow_insecure_ssl(self) -> bool:
        """Return whether TLS verification is disabled for the selected origin."""
        return self._get_allow_insecure(
            INSECURE_SSL_SECTION,
            "https",
            cli_enabled=self.cli_allow_insecure_ssl,
            env_name="WLC_ALLOW_INSECURE_SSL",
        )

    def _get_allow_insecure(
        self,
        section: str,
        scheme: str,
        *,
        cli_enabled: bool,
        env_name: str,
    ) -> bool:
        """Resolve an enable-only insecure transport option."""
        self._validate_insecure_configuration()
        url, _url_source, _key, _key_source = self._get_url_key_sources()
        if cli_enabled or self._environment_enabled(env_name):
            return True

        try:
            selected_origin = self._normalize_origin(url, scheme, allow_auth=True)
        except WLCConfigurationError:
            return False

        for option, value in self._direct_section_items(section).items():
            if self._normalize_origin(
                option, scheme
            ) == selected_origin and self._parse_boolean(section, option, value):
                return True
        return False
