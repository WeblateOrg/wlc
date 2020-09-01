#
# Copyright © 2012 - 2020 Michal Čihař <michal@cihar.com>
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
"""Weblate API client library."""

from copy import copy
from urllib.parse import urlencode, urlparse

import dateutil.parser
import requests

__version__ = "1.7"

URL = "https://weblate.org/"
DEVEL_URL = "https://github.com/WeblateOrg/wlc"
API_URL = "http://127.0.0.1:8000/api/"
USER_AGENT = "wlc/{0}".format(__version__)
LOCALHOST_NETLOC = "127.0.0.1"
TIMESTAMPS = {"last_change"}


class WeblateException(Exception):
    """Generic error."""


class WeblateThrottlingError(WeblateException):
    def __init__(self):
        super().__init__("Throttling on the server")


class WeblatePermissionError(WeblateException):
    def __init__(self):
        super().__init__("You don't have permission to access this object")


class WeblateDeniedError(WeblateException):
    def __init__(self):
        super().__init__("Access denied, API key is wrong or missing")


class Weblate:
    """Weblate API wrapper object."""

    def __init__(self, key="", url=API_URL, config=None):
        """Create the object, storing key and API url."""
        if config is not None:
            self.url, self.key = config.get_url_key()
        else:
            self.key = key
            self.url = url
        if not self.url.endswith("/"):
            self.url += "/"

    @staticmethod
    def process_error(error):
        """Raise WeblateException for known HTTP errors."""
        if isinstance(error, requests.HTTPError):
            status_code = error.response.status_code

            if status_code == 429:
                raise WeblateThrottlingError()
            if status_code == 404:
                raise WeblateException(
                    "Object not found on the server "
                    "(maybe operation is not supported on the server)"
                )
            if status_code == 403:
                raise WeblatePermissionError()

            if status_code == 401:
                raise WeblateDeniedError()

            reason = error.response.reason
            raise WeblateException("HTTP error {0}: {1}".format(status_code, reason))

    def raw_request(self, method, path, params=None, files=None):
        """Construct request object and returns raw content."""
        response = self.invoke_request(method, path, params, files)

        return response.content

    def request(self, method, path, params=None, files=None):
        """Construct request object and returns json response."""
        response = self.invoke_request(method, path, params, files)

        try:
            return response.json()
        except ValueError:
            raise WeblateException("Server returned invalid JSON")

    def invoke_request(self, method, path, params=None, files=None):
        """Construct request object."""
        if not path.startswith("http"):
            path = "{0}{1}".format(self.url, path)
        headers = {"user-agent": USER_AGENT, "Accept": "application/json"}
        if self.key:
            headers["Authorization"] = "Token {}".format(self.key)
        verify_ssl = self._should_verify_ssl(path)
        if files:
            # mulitpart/form upload
            kwargs = {"data": params}
        else:
            # JSON params to handle complex structures
            kwargs = {"json": params}
        try:
            response = requests.request(
                method,
                path,
                headers=headers,
                verify=verify_ssl,
                files=files,
                **kwargs,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            self.process_error(error)
            raise
        return response

    def post(self, path, **kwargs):
        """Perform POST request on the API."""
        return self.request("post", path, kwargs)

    def get(self, path):
        """Perform GET request on the API."""
        return self.request("get", path)

    def list_factory(self, path, parser):
        """Listing object wrapper."""
        while path is not None:
            data = self.get(path)
            for item in data["results"]:
                yield parser(weblate=self, **item)

            path = data["next"]

    def _get_factory(self, prefix, path, parser):
        """Wrapper for getting objects."""
        data = self.get("/".join((prefix, path, "")))
        return parser(weblate=self, **data)

    def get_object(self, path):
        """Return object based on path.

        Operates on (project, component or translation objects.
        """
        parts = path.strip("/").split("/")
        if len(parts) == 3:
            return self.get_translation(path)
        if len(parts) == 2:
            return self.get_component(path)
        if len(parts) == 1:
            return self.get_project(path)
        raise ValueError("Not supported path: {0}".format(path))

    def get_project(self, path):
        """Return project of given path."""
        return self._get_factory("projects", path, Project)

    def get_component(self, path):
        """Return component of given path."""
        return self._get_factory("components", path, Component)

    def get_translation(self, path):
        """Return translation of given path."""
        return self._get_factory("translations", path, Translation)

    def list_projects(self, path="projects/"):
        """List projects in the instance."""
        return self.list_factory(path, Project)

    def list_components(self, path="components/"):
        """List components in the instance."""
        return self.list_factory(path, Component)

    def list_changes(self, path="changes/"):
        """List components in the instance."""
        return self.list_factory(path, Change)

    def list_translations(self, path="translations/"):
        """List translations in the instance."""
        return self.list_factory(path, Translation)

    def list_languages(self):
        """List languages in the instance."""
        return self.list_factory("languages/", Language)

    @staticmethod
    def _should_verify_ssl(path):
        """Cheks if it should verify ssl certificates."""
        url = urlparse(path)
        is_localhost = url.netloc.startswith(LOCALHOST_NETLOC)
        return url.scheme == "https" and (not is_localhost)


class LazyObject(dict):
    """Object which supports deferred loading."""

    PARAMS = ()
    MAPPINGS = {}
    ID = "url"

    def __init__(self, weblate, url, **kwargs):
        """Construct object for given Weblate instance."""
        super().__init__()
        self.weblate = weblate
        self._url = url
        self._data = {}
        self._loaded = False
        self._attribs = {}
        self._load_params(**kwargs)
        self._load_params(url=url)

    def get_data(self):
        return copy(self._data)

    def __str__(self):
        return str(self._data)

    def __repr__(self):
        return repr(self._data)

    def _load_params(self, **kwargs):
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
        for key in kwargs:
            self._attribs[key] = kwargs[key]

    def ensure_loaded(self, attrib):
        """Ensure attribute is loaded from remote."""
        if attrib in self._data or attrib in self._attribs:
            return
        if not self._loaded:
            self.refresh()

    def refresh(self):
        """Read object again from remote."""
        data = self.weblate.get(self._url)
        self._load_params(**data)
        self._loaded = True

    def __getattr__(self, name):
        if name not in self.PARAMS:
            raise AttributeError(name)
        if name not in self._data:
            self.refresh()
        return self._data[name]

    def setattrvalue(self, name, value):
        if name not in self.PARAMS:
            raise AttributeError(name)

        self._data[name] = value

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __len__(self):
        return len(self.PARAMS)

    def keys(self):
        """Return list of attributes."""
        return self.PARAMS

    def items(self):
        """Iterator over attributes."""
        for key in self.PARAMS:
            yield key, self.__getattr__(key)

    def to_value(self):
        """Return identifier for the object."""
        self.ensure_loaded(self.ID)
        return self.__getattr__(self.ID)


class Language(LazyObject):
    """Language object."""

    PARAMS = ("url", "web_url", "code", "name", "direction")
    ID = "code"


class LanguageStats(LazyObject):
    """Language object."""

    PARAMS = (
        "total",
        "code",
        "translated_words",
        "language",
        "translated",
        "translated_percent",
        "total_words",
        "words_percent",
    )
    ID = "code"


class RepoMixin:
    """Repository mixin providing generic repository wide operations."""

    def _get_repo_url(self):
        self.ensure_loaded("repository_url")
        return self._attribs["repository_url"]

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


class ProjectRepository(LazyObject, RepoMixin):
    """Repository object."""

    PARAMS = ("url", "needs_commit", "needs_merge", "needs_push")

    def _get_repo_url(self):
        """Return repository url."""
        return self._data["url"]


class Repository(ProjectRepository):
    """Repository object."""

    PARAMS = (
        "url",
        "needs_commit",
        "needs_merge",
        "needs_push",
        "status",
        "merge_failure",
        "remote_commit",
    )


class RepoObjectMixin(RepoMixin):
    """Repository mixin."""

    REPOSITORY_CLASS = ProjectRepository

    def repository(self):
        """Return repository object."""
        data = self.weblate.get(self._get_repo_url())
        return self.REPOSITORY_CLASS(weblate=self.weblate, **data)


class Project(LazyObject, RepoObjectMixin):
    """Project object."""

    PARAMS = ("url", "web_url", "name", "slug", "web", "source_language")
    ID = "slug"
    MAPPINGS = {"source_language": Language}

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
        return [
            LanguageStats(self.weblate, url, **item) for item in self.weblate.get(url)
        ]

    def changes(self):
        """List changes in the project."""
        self.ensure_loaded("changes_list_url")
        return self.weblate.list_changes(self._attribs["changes_list_url"])

    def delete(self):
        self.weblate.raw_request("delete", self._url)


class Component(LazyObject, RepoObjectMixin):
    """Component object."""

    PARAMS = (
        "url",
        "web_url",
        "name",
        "slug",
        "project",
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
    )
    ID = "slug"
    MAPPINGS = {"project": Project}
    REPOSITORY_CLASS = Repository

    def list(self):
        """List translations in the component."""
        self.ensure_loaded("translations_url")
        return self.weblate.list_translations(self._attribs["translations_url"])

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

    def delete(self):
        self.weblate.raw_request("delete", self._url)


class Translation(LazyObject, RepoObjectMixin):
    """Translation object."""

    PARAMS = (
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
    ID = "language_code"
    MAPPINGS = {"language": Language, "component": Component}
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
        """List changes in the project."""
        self.ensure_loaded("changes_list_url")
        return self.weblate.list_changes(self._attribs["changes_list_url"])

    def download(self, convert=None):
        """Download translation file from server."""
        self.ensure_loaded("file_url")
        url = self._attribs["file_url"]
        if convert is not None:
            url = "{0}?{1}".format(url, urlencode({"format": convert}))
        return self.weblate.raw_request("get", url)

    def upload(self, file, overwrite=None, **kwargs):
        """Download translation file from server."""
        self.ensure_loaded("file_url")
        url = self._attribs["file_url"]
        files = {"file": file}

        if overwrite:
            kwargs["overwrite"] = "yes"

        return self.weblate.request("post", url, files=files, params=kwargs)

    def delete(self):
        self.weblate.raw_request("delete", self._url)


class Statistics(LazyObject):
    """Statistics object."""

    PARAMS = (
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
    PARAMS = Statistics.PARAMS + ("code", "last_author")


class Change(LazyObject):
    """Change object."""

    PARAMS = (
        "url",
        "unit",
        "translation",
        "component",
        "timestamp",
        "action_name",
        "target",
    )
    ID = "id"
    MAPPINGS = {"translation": Translation, "component": Component}
