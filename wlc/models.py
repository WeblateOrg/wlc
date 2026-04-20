# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Weblate API models."""

from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import urlencode

from .base import LazyObject, RepoMixin, RepoObjectMixin


class Language(LazyObject):
    """Language object."""

    PARAMS: ClassVar[tuple[str, ...]] = ("url", "web_url", "code", "name", "direction")
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

    def _get_repo_url(self):
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
    )
    OPTIONALS: ClassVar[set[str]] = {"source_language"}
    ID: ClassVar[str] = "slug"
    MAPPINGS: ClassVar[dict[str, Any]] = {"source_language": Language}
    REPOSITORY_CLASS = ProjectRepository

    def list(self):
        """List components in the project."""
        self.ensure_loaded("components_list_url")
        return self.weblate.list_components(self._attribs["components_list_url"])

    def statistics(self):
        """Return statistics for translation."""
        self.ensure_loaded("statistics_url")
        data = self.weblate.get(self._attribs["statistics_url"])
        return Statistics(weblate=self.weblate, **data)

    def languages(self):
        """Return language statistics for component."""
        self.ensure_loaded("languages_url")
        url = self._attribs["languages_url"]
        return [LanguageStats(self.weblate, **item) for item in self.weblate.get(url)]

    def changes(self):
        """List changes in the project."""
        self.ensure_loaded("changes_list_url")
        return self.weblate.list_changes(self._attribs["changes_list_url"])

    def categories(self):
        """List categories in the project."""
        self.ensure_loaded("categories_url")
        return self.weblate.list_categories(self._attribs["categories_url"])

    def delete(self) -> None:
        self.weblate.raw_request("delete", self._url)

    def create_component(self, **kwargs):
        return self.weblate.create_component(self.slug, **kwargs)

    def full_slug(self):
        return self.slug


class Category(LazyObject):
    """Category object."""

    PARAMS: ClassVar[tuple[str, ...]] = ("category", "name", "project", "slug", "url")
    MAPPINGS: ClassVar[dict[str, Any]] = {"project": Project}

    def full_slug(self):
        current = self
        slugs = [self.project.slug, self.slug]
        while current.category:
            current = current.category
            slugs.insert(1, current.slug)
        return "/".join(slugs)


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
    )
    OPTIONALS: ClassVar[set[str]] = {
        "source_language",
        "is_glossary",
        "category",
        "linked_component",
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

    def list(self):
        """List translations in the component."""
        self.ensure_loaded("translations_url")
        return self.weblate.list_translations(self._attribs["translations_url"])

    def add_translation(self, language):
        """Creates a new translation in the component."""
        self.ensure_loaded("translations_url")
        return self.weblate.post(
            path=self._attribs["translations_url"], language_code=language
        )

    def statistics(self):
        """Return statistics for component."""
        self.ensure_loaded("statistics_url")
        return self.weblate.list_factory(
            self._attribs["statistics_url"], TranslationStatistics
        )

    def _get_lock_url(self):
        self.ensure_loaded("lock_url")
        return self._attribs["lock_url"]

    def lock(self):
        """Lock component from translations."""
        return self.weblate.post(self._get_lock_url(), lock=1)

    def unlock(self):
        """Unlock component from translations."""
        return self.weblate.post(self._get_lock_url(), lock=0)

    def lock_status(self):
        """Return component lock status."""
        return self.weblate.get(self._get_lock_url())

    def changes(self):
        """List changes in the project."""
        self.ensure_loaded("changes_list_url")
        return self.weblate.list_changes(self._attribs["changes_list_url"])

    def delete(self) -> None:
        self.weblate.raw_request("delete", self._url)

    def add_source_string(self, msgid, msgstr):
        """Adds a source string to a monolingual base file."""
        return self.weblate.add_source_string(
            project=self.project.slug,
            component=self.slug,
            msgid=msgid,
            msgstr=msgstr,
            source_language=self.source_language["code"],
        )

    def download(self, convert=None):
        """Download translation file from server."""
        self.ensure_loaded("repository_url")
        url = self._get_repo_url().replace("repository", "file")
        if convert is not None:
            url = f"{url}?{urlencode({'format': convert})}"
        return self.weblate.raw_request("get", url)

    def patch(self, **kwargs):
        return self.weblate.raw_request("patch", self._url, data=kwargs)


class Translation(RepoObjectMixin, LazyObject):
    """Translation object."""

    PARAMS: ClassVar[tuple[str, ...]] = (
        "url",
        "web_url",
        "language",
        "component",
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
        "translated_percent",
        "fuzzy_percent",
        "failing_checks_percent",
        "last_change",
        "last_author",
    )
    ID: ClassVar[str] = "language_code"
    MAPPINGS: ClassVar[dict[str, Any]] = {"language": Language, "component": Component}
    REPOSITORY_CLASS = Repository

    def list(self):
        """API compatibility method, returns self."""
        self.ensure_loaded("last_author")
        return self

    def statistics(self):
        """Return statistics for translation."""
        self.ensure_loaded("statistics_url")
        data = self.weblate.get(self._attribs["statistics_url"])
        return TranslationStatistics(weblate=self.weblate, **data)

    def changes(self):
        """List changes in the translation."""
        self.ensure_loaded("changes_list_url")
        return self.weblate.list_changes(self._attribs["changes_list_url"])

    def download(self, convert=None):
        """Download translation file from server."""
        self.ensure_loaded("file_url")
        url = self._attribs["file_url"]
        if convert is not None:
            url = f"{url}?{urlencode({'format': convert})}"
        return self.weblate.raw_request("get", url)

    # pylint: disable-next=redefined-builtin
    def upload(self, file, overwrite=None, format=None, **kwargs):  # noqa: A002
        """Updoad a translation file to server."""
        self.ensure_loaded("file_url")
        url = self._attribs["file_url"]
        files = {"file": (f"file.{format}", file)} if format else {"file": file}
        if overwrite:
            kwargs["conflicts"] = "replace-translated"

        return self.weblate.request("post", url, files=files, data=kwargs)

    def delete(self) -> None:
        self.weblate.raw_request("delete", self._url)

    def units(self, **kwargs):
        """List units in the translation."""
        self.ensure_loaded("units_list_url")
        return self.weblate.list_units(self._attribs["units_list_url"], params=kwargs)


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
        "timestamp",
        "action_name",
        "target",
    )
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
        "location",
        "note",
        "num_words",
        "position",
        "previous_source",
        "priority",
        "source",
        "source_unit",
        "state",
        "target",
        "translated",
        "translation",
        "url",
        "web_url",
    )
    ID: ClassVar[str] = "id"
    MAPPINGS: ClassVar[dict[str, Any]] = {"translation": Translation}

    def list(self):
        """API compatibility method, returns self."""
        self.ensure_loaded("id")
        return self

    def patch(self, **kwargs):
        return self.weblate.raw_request("patch", self._url, data=kwargs)

    def put(self, **kwargs):
        return self.weblate.raw_request("put", self._url, data=kwargs)

    def delete(self):
        return self.weblate.raw_request("delete", self._url)
