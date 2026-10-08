# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared Weblate model infrastructure."""

from __future__ import annotations

from collections import UserDict
from copy import copy
from typing import TYPE_CHECKING, Any, ClassVar, cast

import dateutil.parser

from .const import TIMESTAMPS

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from types import NotImplementedType

    from .client import Weblate

_MISSING = object()


class LazyObject(UserDict[str, Any]):
    """Mapping object that supports deferred loading from the Weblate API."""

    PARAMS: ClassVar[tuple[str, ...]] = ()
    OPTIONALS: ClassVar[set[str]] = set()
    NULLS: ClassVar[set[str]] = set()
    MAPPINGS: ClassVar[dict[str, type[LazyObject]]] = {}
    ID: ClassVar[str] = "url"

    def __init__(self, weblate: Weblate, url: str, **kwargs: object) -> None:
        """Construct object for given Weblate instance."""
        super().__init__()

        self.weblate = weblate
        self._url = url
        self._loaded = False
        self._attribs: dict[str, object] = {}
        self._load_params(**kwargs)
        self._load_params(url=url)

    def __eq__(self, other: object) -> bool:
        """Compare object state or loaded mapping data for equality."""
        if isinstance(other, LazyObject):
            return (
                self.weblate == other.weblate
                and self._url == other._url
                and self.data == other.data
                and self._loaded == other._loaded
                and self._attribs == other._attribs
            )
        if isinstance(other, UserDict):
            return self.data == other.data
        if isinstance(other, dict):
            return self.data == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        """Negate equality while preserving unsupported comparisons."""
        result = self.__eq__(other)
        if result is NotImplemented:
            return NotImplemented
        return not result

    __hash__ = None  # type: ignore[assignment]

    def get_data(self) -> dict[str, Any]:
        """Return a copy of the currently loaded object data."""
        return copy(self.data)

    def __str__(self) -> str:
        """Return the string form of the currently loaded data."""
        return str(self.data)

    def __repr__(self) -> str:
        """Return the representation of the currently loaded data."""
        return repr(self.data)

    def _load_params(self, **kwargs: object) -> None:
        for param in self.PARAMS:
            if param in kwargs:
                value = kwargs[param]
                if value is not None and param in self.MAPPINGS:
                    if isinstance(value, str):
                        self.data[param] = self.MAPPINGS[param](self.weblate, url=value)
                    else:
                        # The mapped model defines the nested JSON fields,
                        # including its constructor URL when present.
                        self.data[param] = self.MAPPINGS[param](
                            self.weblate, **cast("Mapping[str, Any]", value)
                        )
                elif value is not None and param in TIMESTAMPS:
                    self.data[param] = dateutil.parser.parse(cast("str", value))
                else:
                    self.data[param] = value
                del kwargs[param]
        for key, value in kwargs.items():
            self._attribs[key] = value

    def ensure_loaded(self, attrib: str) -> None:
        """Ensure attribute is loaded from remote."""
        if attrib in self.data or attrib in self._attribs:
            return
        if not self._loaded:
            self.refresh()

    def _get_stored(self, name: str) -> object:
        """Return a value stored in object data or deferred attributes."""
        self.ensure_loaded(name)
        if name in self.data:
            return self.data[name]
        try:
            return self._attribs[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def _get_stored_url(self, name: str) -> str:
        """Return a stored URL field whose API schema specifies a string."""
        return cast("str", self._get_stored(name))

    def refresh(self) -> None:
        """Read object again from remote."""
        data = cast("dict[str, Any]", self.weblate.get(self._url))
        self._load_params(**data)
        self._loaded = True

    # API fields have heterogeneous types determined by the concrete model.
    def __getattr__(self, name: str) -> Any:  # ruff: ignore[any-type]
        """Load and return a declared API attribute."""
        if name not in self.PARAMS:
            raise AttributeError(name)
        if name not in self.data:
            self.refresh()
        try:
            return self.data[name]
        except KeyError as error:
            if name in self.NULLS:
                return None
            raise AttributeError(name) from error

    def setattrvalue(self, name: str, value: object) -> None:
        """Set a loaded API attribute value."""
        if name not in self.PARAMS:
            raise AttributeError(name)

        self.data[name] = value

    # Match the heterogeneous dynamic attributes returned by __getattr__.
    def __getitem__(self, key: str) -> Any:  # ruff: ignore[any-type]
        """Return an API attribute by key, loading it when needed."""
        return getattr(self, key)

    # Preserve dynamic field types, as __getitem__ does, for mapping lookups.
    def get(self, key: object, default: object = None) -> Any:  # ruff: ignore[any-type]
        """Return a loaded field or the default without fetching missing fields."""
        return self.data.get(cast("str", key), default)

    def pop(self, key: str, default: object = _MISSING) -> Any:  # ruff: ignore[any-type]
        """Remove a loaded field without fetching missing fields."""
        if default is _MISSING:
            return self.data.pop(key)
        return self.data.pop(key, default)

    def setdefault(self, key: str, default: object = None) -> Any:  # ruff: ignore[any-type]
        """Set a local default for an unloaded field without fetching it."""
        return self.data.setdefault(key, default)

    def popitem(self) -> tuple[str, object]:
        """Remove a loaded field and its value without fetching missing fields."""
        return self.data.popitem()

    def clear(self) -> None:
        """Remove all loaded fields without fetching missing fields."""
        self.data.clear()

    # These operators return plain dicts; UserDict's annotations require UserDict.
    # pylint: disable-next=line-too-long
    def __or__(self, other: object) -> dict[str, object] | NotImplementedType:  # type: ignore[override]  # ty: ignore[invalid-method-override]
        """Merge loaded data with another mapping, preferring its values."""
        if isinstance(other, UserDict):
            other = other.data
        if isinstance(other, dict):
            return self.data | other
        return NotImplemented

    # pylint: disable-next=line-too-long
    def __ror__(self, other: object) -> dict[str, object] | NotImplementedType:  # type: ignore[override]  # ty: ignore[invalid-method-override]
        """Merge another mapping with loaded data, preferring loaded values."""
        if isinstance(other, UserDict):
            other = other.data
        if isinstance(other, dict):
            return other | self.data
        return NotImplemented

    def __len__(self) -> int:
        """Return the number of exposed API attributes."""
        return len(list(self.keys()))

    # The public API historically returns iterators instead of mapping views.
    def keys(self) -> Iterator[str]:  # type: ignore[override]  # ty: ignore[invalid-method-override]
        """Return list of attributes."""
        # There is always at least url present
        if len(self.data) <= 1:
            self.refresh()
        for param in self.PARAMS:
            if param not in self.OPTIONALS or param in self.data or param in self.NULLS:
                yield param

    def items(self) -> Iterator[tuple[str, object]]:  # type: ignore[override]  # ty: ignore[invalid-method-override]
        """Iterate over attribute names and values."""
        for key in self.keys():
            yield key, getattr(self, key)

    def to_value(self) -> str | int:
        """Return identifier for the object."""
        self.ensure_loaded(self.ID)
        return getattr(self, self.ID)


class RepoMixin(LazyObject):
    """Repository mixin providing generic repository wide operations."""

    def _get_repo_url(self) -> str:
        return self._get_stored_url("repository_url")

    def commit(self) -> dict[str, Any]:
        """Commit Weblate changes."""
        return self.weblate.post(self._get_repo_url(), operation="commit")

    def push(self) -> dict[str, Any]:
        """Push Weblate changes upstream."""
        return self.weblate.post(self._get_repo_url(), operation="push")

    def pull(self) -> dict[str, Any]:
        """Pull upstream changes into Weblate."""
        return self.weblate.post(self._get_repo_url(), operation="pull")

    def reset(self) -> dict[str, Any]:
        """Reset Weblate repository to upstream."""
        return self.weblate.post(self._get_repo_url(), operation="reset")

    def cleanup(self) -> dict[str, Any]:
        """Cleanup Weblate repository from untracked files."""
        return self.weblate.post(self._get_repo_url(), operation="cleanup")


class RepoObjectMixin(RepoMixin):
    """Repository mixin."""

    REPOSITORY_CLASS: ClassVar[type[LazyObject]] = LazyObject

    def repository(self) -> LazyObject:
        """Return repository object."""
        data = cast("dict[str, Any]", self.weblate.get(self._get_repo_url()))
        return self.REPOSITORY_CLASS(weblate=self.weblate, **data)
