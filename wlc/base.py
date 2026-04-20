# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared Weblate model infrastructure."""

from __future__ import annotations

from copy import copy
from typing import Any, ClassVar

import dateutil.parser

from .const import TIMESTAMPS


class LazyObject(dict):
    """Object which supports deferred loading."""

    PARAMS: ClassVar[tuple[str, ...]] = ()
    OPTIONALS: ClassVar[set[str]] = set()
    NULLS: ClassVar[set[str]] = set()
    MAPPINGS: ClassVar[dict[str, Any]] = {}
    ID: ClassVar[str] = "url"

    def __init__(self, weblate, url, **kwargs) -> None:
        """Construct object for given Weblate instance."""
        super().__init__()

        self.weblate = weblate
        self._url = url
        self._data: dict[str, Any] = {}
        self._loaded = False
        self._attribs: dict[str, Any] = {}
        self._load_params(**kwargs)
        self._load_params(url=url)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LazyObject):
            return (
                self.weblate == other.weblate
                and self._url == other._url
                and self._data == other._data
                and self._loaded == other._loaded
                and self._attribs == other._attribs
            )
        if isinstance(other, dict):
            return self._data == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return NotImplemented
        return not result

    __hash__ = None

    def get_data(self):
        return copy(self._data)

    def __str__(self) -> str:
        return str(self._data)

    def __repr__(self) -> str:
        return repr(self._data)

    def _load_params(self, **kwargs) -> None:
        for param in self.PARAMS:
            if param in kwargs:
                value = kwargs[param]
                if value is not None and param in self.MAPPINGS:
                    if isinstance(value, str):
                        self._data[param] = self.MAPPINGS[param](
                            self.weblate, url=value
                        )
                    else:
                        self._data[param] = self.MAPPINGS[param](self.weblate, **value)
                elif value is not None and param in TIMESTAMPS:
                    self._data[param] = dateutil.parser.parse(value)
                else:
                    self._data[param] = value
                del kwargs[param]
        for key, value in kwargs.items():
            self._attribs[key] = value

    def ensure_loaded(self, attrib: str) -> None:
        """Ensure attribute is loaded from remote."""
        if attrib in self._data or attrib in self._attribs:
            return
        if not self._loaded:
            self.refresh()

    def _get_stored(self, name: str) -> Any:
        """Return a value stored in object data or deferred attributes."""
        self.ensure_loaded(name)
        if name in self._data:
            return self._data[name]
        try:
            return self._attribs[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def refresh(self) -> None:
        """Read object again from remote."""
        data = self.weblate.get(self._url)
        self._load_params(**data)
        self._loaded = True

    def __getattr__(self, name: str) -> Any:
        if name not in self.PARAMS:
            raise AttributeError(name)
        if name not in self._data:
            self.refresh()
        try:
            return self._data[name]
        except KeyError as error:
            if name in self.NULLS:
                return None
            raise AttributeError(name) from error

    def setattrvalue(self, name: str, value: Any) -> None:
        if name not in self.PARAMS:
            raise AttributeError(name)

        self._data[name] = value

    def __getitem__(self, name: str) -> Any:
        return getattr(self, name)

    def __len__(self) -> int:
        return len(list(self.keys()))

    def keys(self):
        """Return list of attributes."""
        # There is always at least url present
        if len(self._data) <= 1:
            self.refresh()
        for param in self.PARAMS:
            if (
                param not in self.OPTIONALS
                or param in self._data
                or param in self.NULLS
            ):
                yield param

    def items(self):
        """Iterator over attributes."""
        for key in self.keys():
            yield key, getattr(self, key)

    def to_value(self) -> Any:
        """Return identifier for the object."""
        self.ensure_loaded(self.ID)
        return getattr(self, self.ID)


class RepoMixin(LazyObject):
    """Repository mixin providing generic repository wide operations."""

    def _get_repo_url(self) -> str:
        return self._get_stored("repository_url")

    def commit(self):
        """Commit Weblate changes."""
        return self.weblate.post(self._get_repo_url(), operation="commit")

    def push(self):
        """Push Weblate changes upstream."""
        return self.weblate.post(self._get_repo_url(), operation="push")

    def pull(self):
        """Pull upstream changes into Weblate."""
        return self.weblate.post(self._get_repo_url(), operation="pull")

    def reset(self):
        """Reset Weblate repository to upstream."""
        return self.weblate.post(self._get_repo_url(), operation="reset")

    def cleanup(self):
        """Cleanup Weblate repository from untracked files."""
        return self.weblate.post(self._get_repo_url(), operation="cleanup")


class RepoObjectMixin(RepoMixin):
    """Repository mixin."""

    REPOSITORY_CLASS = LazyObject

    def repository(self):
        """Return repository object."""
        data = self.weblate.get(self._get_repo_url())
        return self.REPOSITORY_CLASS(weblate=self.weblate, **data)
