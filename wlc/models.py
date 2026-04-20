# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Weblate API models."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlencode

from .base import LazyObject, RepoMixin, RepoObjectMixin

if TYPE_CHECKING:
    import builtins
    from collections.abc import Iterator


class Language(LazyObject):
    """Language object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "url",
        "web_url",
        "code",
        "name",
        "direction",
        "plural",
        "aliases",
        "statistics_url",
        "id",
    )
    OPTIONALS: ClassVar[set[str]] = {"plural", "aliases", "statistics_url", "id"}
    ID: ClassVar[str] = "code"


class LanguageStats(LazyObject):
    """Language object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "total",
        "code",
        "translated_words",
        "language",
        "translated",
        "translated_percent",
        "total_words",
        "words_percent",
    )
    ID: ClassVar[str] = "code"


class ProjectRepository(RepoMixin, LazyObject):
    """Repository object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "url",
        "needs_commit",
        "needs_merge",
        "needs_push",
    )

    def _get_repo_url(self) -> str:
        """Return repository url."""
        return self._data["url"]


class Repository(ProjectRepository):
    """Repository object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "url",
        "needs_commit",
        "needs_merge",
        "needs_push",
        "status",
        "merge_failure",
        "remote_commit",
    )


class Project(RepoObjectMixin, LazyObject):
    """Project object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "url",
        "web_url",
        "name",
        "slug",
        "web",
        "source_language",
        "id",
        "components_list_url",
        "repository_url",
        "statistics_url",
        "categories_url",
        "changes_list_url",
        "languages_url",
    )
    OPTIONALS: ClassVar[set[str]] = {
        "source_language",
        "id",
        "components_list_url",
        "repository_url",
        "statistics_url",
        "categories_url",
        "changes_list_url",
        "languages_url",
    }
    ID: ClassVar[str] = "slug"
    MAPPINGS: ClassVar[dict[str, Any]] = {"source_language": Language}
    REPOSITORY_CLASS = ProjectRepository

    def list(self) -> Iterator[Component]:
        """List components in the project."""
        return self.weblate.list_components(self._get_stored("components_list_url"))

    def statistics(self) -> Statistics:
        """Return statistics for translation."""
        data = self.weblate.get(self._get_stored("statistics_url"))
        return Statistics(weblate=self.weblate, **data)

    def languages(self) -> builtins.list[LanguageStats]:
        """Return language statistics for the project."""
        return list(
            self.weblate.list_factory(self._get_stored("languages_url"), LanguageStats)
        )

    def changes(self) -> Iterator[Change]:
        """List changes in the project."""
        return self.weblate.list_changes(self._get_stored("changes_list_url"))

    def categories(self) -> Iterator[Category]:
        """List categories in the project."""
        return self.weblate.list_categories(self._get_stored("categories_url"))

    def delete(self) -> None:
        self.weblate.raw_request("delete", self._url)

    def create_component(self, **kwargs: Any) -> dict[str, Any]:
        return self.weblate.create_component(self.slug, **kwargs)

    def full_slug(self) -> str:
        return self.slug


class Category(LazyObject):
    """Category object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "category",
        "name",
        "project",
        "slug",
        "url",
        "id",
        "statistics_url",
    )
    OPTIONALS: ClassVar[set[str]] = {"id", "statistics_url"}
    MAPPINGS: ClassVar[dict[str, Any]] = {"project": Project}

    def full_slug(self) -> str:
        current = self
        slugs = [self.project.slug, self.slug]
        while current.category:
            current = current.category
            slugs.insert(1, current.slug)
        return "/".join(slugs)


Category.MAPPINGS["category"] = Category


class Component(RepoObjectMixin, LazyObject):
    """Component object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "url",
        "web_url",
        "name",
        "slug",
        "project",
        "source_language",
        "vcs",
        "repo",
        "git_export",
        "branch",
        "filemask",
        "template",
        "new_base",
        "file_format",
        "license",
        "license_url",
        "agreement",
        "priority",
        "is_glossary",
        "category",
        "linked_component",
        "id",
        "repository_url",
        "translations_url",
        "statistics_url",
        "lock_url",
        "changes_list_url",
    )
    OPTIONALS: ClassVar[set[str]] = {
        "source_language",
        "is_glossary",
        "category",
        "linked_component",
        "id",
        "repository_url",
        "translations_url",
        "statistics_url",
        "lock_url",
        "changes_list_url",
    }
    NULLS: ClassVar[set[str]] = {"category"}
    ID: ClassVar[str] = "slug"
    MAPPINGS: ClassVar[dict[str, Any]] = {
        "category": Category,
        "project": Project,
        "source_language": Language,
    }
    REPOSITORY_CLASS = Repository

    def full_slug(self) -> str:
        if self.category:
            return f"{self.category.full_slug()}/{self.slug}"
        return f"{self.project.full_slug()}/{self.slug}"

    def list(self) -> Iterator[Translation]:
        """List translations in the component."""
        return self.weblate.list_translations(self._get_stored("translations_url"))

    def add_translation(self, language: str) -> dict[str, Any]:
        """Creates a new translation in the component."""
        return self.weblate.post(
            path=self._get_stored("translations_url"), language_code=language
        )

    def statistics(self) -> Iterator[TranslationStatistics]:
        """Return statistics for component."""
        return self.weblate.list_factory(
            self._get_stored("statistics_url"), TranslationStatistics
        )

    def _get_lock_url(self) -> str:
        return self._get_stored("lock_url")

    def lock(self) -> dict[str, Any]:
        """Lock component from translations."""
        return self.weblate.post(self._get_lock_url(), lock=1)

    def unlock(self) -> dict[str, Any]:
        """Unlock component from translations."""
        return self.weblate.post(self._get_lock_url(), lock=0)

    def lock_status(self) -> dict[str, Any]:
        """Return component lock status."""
        return self.weblate.get(self._get_lock_url())

    def changes(self) -> Iterator[Change]:
        """List changes in the component."""
        return self.weblate.list_changes(self._get_stored("changes_list_url"))

    def delete(self) -> None:
        self.weblate.raw_request("delete", self._url)

    def add_source_string(
        self, msgid: str, msgstr: str | builtins.list[str]
    ) -> dict[str, Any]:
        """Adds a source string to a monolingual base file."""
        return self.weblate.add_source_string(
            project=self.project.slug,
            component=self.slug,
            msgid=msgid,
            msgstr=msgstr,
            source_language=self.source_language["code"],
        )

    def download(self, convert: str | None = None) -> bytes:
        """Download translation file from server."""
        self.ensure_loaded("repository_url")
        url = self._get_repo_url().replace("repository", "file")
        if convert is not None:
            url = f"{url}?{urlencode({'format': convert})}"
        return self.weblate.raw_request("get", url)

    def patch(self, **kwargs: Any) -> bytes:
        return self.weblate.raw_request("patch", self._url, data=kwargs)


class Translation(RepoObjectMixin, LazyObject):
    """Translation object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "url",
        "web_url",
        "language",
        "component",
        "id",
        "translated",
        "fuzzy",
        "total",
        "translated_words",
        "fuzzy_words",
        "failing_checks_words",
        "total_words",
        "failing_checks",
        "have_suggestion",
        "have_comment",
        "language_code",
        "filename",
        "revision",
        "share_url",
        "translate_url",
        "is_template",
        "is_source",
        "translated_percent",
        "fuzzy_percent",
        "failing_checks_percent",
        "last_change",
        "last_author",
        "repository_url",
        "file_url",
        "statistics_url",
        "changes_list_url",
        "units_list_url",
        "announcements_url",
    )
    OPTIONALS: ClassVar[set[str]] = {
        "id",
        "is_source",
        "repository_url",
        "file_url",
        "statistics_url",
        "changes_list_url",
        "units_list_url",
        "announcements_url",
    }
    ID: ClassVar[str] = "language_code"
    MAPPINGS: ClassVar[dict[str, Any]] = {"language": Language, "component": Component}
    REPOSITORY_CLASS = Repository

    def list(self) -> Translation:
        """API compatibility method, returns self."""
        self.ensure_loaded("last_author")
        return self

    def statistics(self) -> TranslationStatistics:
        """Return statistics for translation."""
        data = self.weblate.get(self._get_stored("statistics_url"))
        return TranslationStatistics(weblate=self.weblate, **data)

    def changes(self) -> Iterator[Change]:
        """List changes in the translation."""
        return self.weblate.list_changes(self._get_stored("changes_list_url"))

    def download(self, convert: str | None = None) -> bytes:
        """Download translation file from server."""
        url = self._get_stored("file_url")
        if convert is not None:
            url = f"{url}?{urlencode({'format': convert})}"
        return self.weblate.raw_request("get", url)

    # pylint: disable-next=redefined-builtin
    def upload(
        self,
        file: Any,
        overwrite: bool | None = None,
        # pylint: disable-next=redefined-builtin
        format: str | None = None,  # noqa: A002
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Upload a translation file to server."""
        url = self._get_stored("file_url")
        files = {"file": (f"file.{format}", file)} if format else {"file": file}
        if overwrite:
            kwargs["conflicts"] = "replace-translated"

        return self.weblate.request("post", url, files=files, data=kwargs)

    def delete(self) -> None:
        self.weblate.raw_request("delete", self._url)

    def units(self, **kwargs: Any) -> Iterator[Unit]:
        """List units in the translation."""
        return self.weblate.list_units(
            self._get_stored("units_list_url"), params=kwargs
        )


class Statistics(LazyObject):
    """Statistics object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "failing_percent",
        "translated_percent",
        "total_words",
        "failing",
        "translated_words",
        "fuzzy_percent",
        "recent_changes",
        "translated",
        "fuzzy",
        "total",
        "last_change",
        "name",
        "url",
    )


class TranslationStatistics(Statistics):
    """Translation statistics."""

    PARAMS: ClassVar[tuple[str, ...]] = (*Statistics.PARAMS, "code", "last_author")


class Change(LazyObject):
    """Change object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "url",
        "unit",
        "translation",
        "component",
        "id",
        "user",
        "author",
        "timestamp",
        "action",
        "action_name",
        "target",
        "old",
        "details",
    )
    OPTIONALS: ClassVar[set[str]] = {"old", "details"}
    ID: ClassVar[str] = "id"
    MAPPINGS: ClassVar[dict[str, Any]] = {
        "translation": Translation,
        "component": Component,
    }


class Unit(LazyObject):
    """Unit object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "approved",
        "content_hash",
        "context",
        "explanation",
        "extra_flags",
        "flags",
        "fuzzy",
        "has_comment",
        "has_failing_check",
        "has_suggestion",
        "id",
        "id_hash",
        "labels",
        "language_code",
        "location",
        "note",
        "num_words",
        "pending",
        "position",
        "previous_source",
        "priority",
        "source",
        "source_unit",
        "state",
        "target",
        "timestamp",
        "translated",
        "translation",
        "url",
        "web_url",
        "last_updated",
        "automatically_translated",
    )
    OPTIONALS: ClassVar[set[str]] = {
        "labels",
        "language_code",
        "pending",
        "timestamp",
        "last_updated",
        "automatically_translated",
    }
    ID: ClassVar[str] = "id"
    MAPPINGS: ClassVar[dict[str, Any]] = {"translation": Translation}

    def list(self) -> Unit:
        """API compatibility method, returns self."""
        self.ensure_loaded("id")
        return self

    def patch(self, **kwargs: Any) -> bytes:
        return self.weblate.raw_request("patch", self._url, data=kwargs)

    def put(self, **kwargs: Any) -> bytes:
        if "target" not in kwargs:
            target = self.target
            kwargs["target"] = (
                list(target) if isinstance(target, (list, tuple)) else target
            )
        if "labels" not in kwargs:
            with suppress(AttributeError):
                kwargs["labels"] = list(self.labels)
        return self.weblate.raw_request("put", self._url, data=kwargs)

    def delete(self) -> bytes:
        return self.weblate.raw_request("delete", self._url)
