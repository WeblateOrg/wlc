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
"""Weblate API client library."""

import json
import logging
from copy import copy
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import urlencode, urlparse

import dateutil.parser  # type: ignore
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

log = logging.getLogger("wlc")

__version__ = "1.13"

URL = "https://weblate.org/"
DEVEL_URL = "https://github.com/WeblateOrg/wlc"
API_URL = "http://127.0.0.1:8000/api/"
USER_AGENT = f"wlc/{__version__}"
LOCALHOST_NETLOC = "127.0.0.1"
TIMESTAMPS = {"last_change"}


class WeblateException(Exception):
    """Generic error."""

    def __init__(self, message: Optional[str] = None):
        super().__init__(message or self.__doc__)


class WeblateThrottlingError(WeblateException):
    """Throttling on the server."""


class WeblatePermissionError(WeblateException):
    """You don't have permission to access this object."""


class WeblateDeniedError(WeblateException):
    """Access denied, API key is wrong or missing."""


class Weblate:
    """Weblate API wrapper object."""

    def __init__(
        self,
        key="",
        url=API_URL,
        config=None,
        retries=0,
        status_forcelist=None,
        method_whitelist=None,
        backoff_factor=0,
        timeout=30,
    ):
        """Create the object, storing key, API url and requests retry args."""
        self.session = requests.Session()
        if config is not None:
            self.url, self.key = config.get_url_key()
            (
                self.retries,
                self.status_forcelist,
                self.method_whitelist,
                self.backoff_factor,
                self.timeout,
            ) = config.get_request_options()
        else:
            self.key = key
            self.url = url
            self.retries = retries
            self.status_forcelist = status_forcelist
            self.timeout = timeout
            self.method_whitelist = method_whitelist or [
                "HEAD",
                "GET",
                "PUT",
                "PATCH",
                "DELETE",
                "OPTIONS",
                "TRACE",
            ]
            self.backoff_factor = backoff_factor

        self.retries = Retry(
            total=self.retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=self.status_forcelist,
            allowed_methods=self.method_whitelist,
            raise_on_status=False,
        )
        self.adapter = HTTPAdapter(pool_connections=1, max_retries=retries)

        if not self.url.endswith("/"):
            self.url += "/"

    @staticmethod
    def permission_error_message(error):
        """Get detail from serialized DRF PermissionDenied exception."""
        try:
            return error.response.json()["detail"]
        except (json.JSONDecodeError, KeyError):
            return None

    def process_error(self, error):
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
                raise WeblatePermissionError(self.permission_error_message(error))

            if status_code == 401:
                raise WeblateDeniedError()

            reason = error.response.reason
            try:
                error_string = str(error.response.json())
            except Exception:
                error_string = ""
            raise WeblateException(f"HTTP error {status_code}: {reason} {error_string}")

    def raw_request(self, method, path, data=None, files=None, params=None):
        """Construct request object and returns raw content."""
        response = self.invoke_request(method, path, data, files, params=params)

        return response.content

    def request(self, method, path, data=None, files=None, params=None):
        """Construct request object and returns json response."""
        response = self.invoke_request(method, path, data, files, params=params)

        try:
            return response.json()
        except ValueError:
            raise WeblateException("Server returned invalid JSON")

    def invoke_request(self, method, path, data=None, files=None, params=None):
        """Construct request object."""
        if not path.startswith("http"):
            path = f"{self.url}{path}"
        headers = {"user-agent": USER_AGENT, "Accept": "application/json"}
        if self.key:
            headers["Authorization"] = f"Token {self.key}"
        verify_ssl = self._should_verify_ssl(path)
        kwargs = {
            "headers": headers,
            "verify": verify_ssl,
            "files": files,
        }

        # Disable insecure warnings for localhost
        if not verify_ssl:
            logging.captureWarnings(True)
        if params:
            kwargs["params"] = params
        if files:
            # mulitpart/form upload
            kwargs["data"] = data
        else:
            # JSON params to handle complex structures
            kwargs["json"] = data
        try:
            self.session.mount(f"{urlparse(path).scheme}://", self.adapter)
            kwargs["timeout"] = self.timeout
            log_kwargs = copy(kwargs)
            del log_kwargs["files"]
            log.debug(json.dumps([method, path, log_kwargs], indent=True))
            response = self.session.request(method, path, **kwargs)
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            self.process_error(error)
            raise
        return response

    def post(self, path, files=None, params=None, **kwargs):
        """Perform POST request on the API."""
        return self.request("post", path, data=kwargs, files=files, params=params)

    def _post_factory(self, prefix, path, kwargs):
        """Wrapper for posting objects."""
        return self.post("/".join((prefix, path, "")), **kwargs)

    def get(self, path, params=None):
        """Perform GET request on the API."""
        return self.request("get", path, params=params)

    def list_factory(self, path, parser, params=None):
        """Listing object wrapper."""
        while path is not None:
            data = self.get(path, params=params)
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
        try:
            int(path)
            return self.get_unit(path)
        except ValueError:
            pass
        if len(parts) == 3:
            return self.get_translation(path)
        if len(parts) == 2:
            return self.get_component(path)
        if len(parts) == 1:
            return self.get_project(path)
        raise ValueError(f"Not supported path: {path}")

    def get_project(self, path):
        """Return project of given path."""
        return self._get_factory("projects", path, Project)

    def get_component(self, path):
        """Return component of given path."""
        return self._get_factory("components", path, Component)

    def get_translation(self, path):
        """Return translation of given path."""
        return self._get_factory("translations", path, Translation)

    def get_unit(self, path):
        """Return unit of given path."""
        return self._get_factory("units", path, Unit)

    def list_projects(self, path="projects/"):
        """List projects in the instance."""
        return self.list_factory(path, Project)

    def list_components(self, path="components/"):
        """List components in the instance."""
        return self.list_factory(path, Component)

    def list_changes(self, path="changes/"):
        """List changes in the instance."""
        return self.list_factory(path, Change)

    def list_units(self, path, params=None):
        """List units in the instance."""
        return self.list_factory(path, Unit, params=params)

    def list_translations(self, path="translations/"):
        """List translations in the instance."""
        return self.list_factory(path, Translation)

    def list_languages(self):
        """List languages in the instance."""
        return self.list_factory("languages/", Language)

    def add_source_string(
        self, project, component, msgid, msgstr, source_language=None
    ):
        """Adds a source string to a monolingual base file."""
        if not source_language:
            component_obj = self.get_component(f"{project}/{component}")
            source_language = component_obj["source_language"]["code"]
        if not isinstance(msgstr, list):
            msgstr = [msgstr]
        path = f"{project}/{component}/{source_language}/units"
        payload = {"key": msgid, "value": msgstr}
        return self._post_factory("translations", path, payload)

    def create_project(
        self, name, slug, website, source_language_name=None, source_language_code=None
    ):
        """Create a new project in the instance."""
        data = {
            "name": name,
            "slug": slug,
            "web": website,
        }
        if source_language_name and source_language_code:
            data["source_language"] = {
                "name": source_language_name,
                "code": source_language_code,
            }

        return self.post("projects/", **data)

    def create_component(self, project, **kwargs):
        """Create a new component for project in the instance."""
        files = {}
        for fileattr in ("docfile", "zipfile"):
            if fileattr in kwargs:
                files[fileattr] = kwargs.pop(fileattr)

        required_keys = ["name", "slug", "file_format", "filemask", "repo"]
        for key in required_keys:
            if key not in kwargs:
                raise WeblateException(f"{key} is required.")

        return self.post(f"projects/{project}/components/", files=files, **kwargs)

    def create_language(self, code, name, direction="ltr", plural=None):
        """Create a new language."""
        plural = plural if plural else {"number": 2, "formula": "n != 1"}
        data = {"code": code, "name": name, "direction": direction, "plural": plural}
        return self.post("languages/", **data)

    @staticmethod
    def _should_verify_ssl(path):
        """Cheks if it should verify ssl certificates."""
        url = urlparse(path)
        is_localhost = url.netloc.startswith(LOCALHOST_NETLOC)
        return url.scheme == "https" and (not is_localhost)


class LazyObject(dict):
    """Object which supports deferred loading."""

    PARAMS: Tuple[str, ...] = ()
    OPTIONALS: Set[str] = set()
    MAPPINGS: Dict[str, Any] = {}
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
        for key, value in kwargs.items():
            self._attribs[key] = value

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
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name)

    def setattrvalue(self, name, value):
        if name not in self.PARAMS:
            raise AttributeError(name)

        self._data[name] = value

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __len__(self):
        return len(list(self.keys()))

    def keys(self):
        """Return list of attributes."""
        # There is always at least url present
        if len(self._data) <= 1:
            self.refresh()
        for param in self.PARAMS:
            if param not in self.OPTIONALS or param in self._data:
                yield param

    def items(self):
        """Iterator over attributes."""
        for key in self.keys():
            yield key, self.__getattr__(key)

    def to_value(self):
        """Return identifier for the object."""
        self.ensure_loaded(self.ID)
        return self.__getattr__(self.ID)


class Language(LazyObject):
    """Language object."""

    PARAMS: Tuple[str, ...] = ("url", "web_url", "code", "name", "direction")
    ID = "code"


class LanguageStats(LazyObject):
    """Language object."""

    PARAMS: Tuple[str, ...] = (
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

    PARAMS: Tuple[str, ...] = ("url", "needs_commit", "needs_merge", "needs_push")

    def _get_repo_url(self):
        """Return repository url."""
        return self._data["url"]


class Repository(ProjectRepository):
    """Repository object."""

    PARAMS: Tuple[str, ...] = (
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

    PARAMS: Tuple[str, ...] = (
        "url",
        "web_url",
        "name",
        "slug",
        "web",
        "source_language",
    )
    OPTIONALS = {"source_language"}
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

    def create_component(self, **kwargs):
        return self.weblate.create_component(self.slug, **kwargs)


class Component(LazyObject, RepoObjectMixin):
    """Component object."""

    PARAMS: Tuple[str, ...] = (
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
        "source_language",
        "is_glossary",
    )
    OPTIONALS = {"source_language", "is_glossary"}
    ID = "slug"
    MAPPINGS = {"project": Project, "source_language": Language}
    REPOSITORY_CLASS = Repository

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

    def delete(self):
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
            url = "{}?{}".format(url, urlencode({"format": convert}))
        return self.weblate.raw_request("get", url)


class Translation(LazyObject, RepoObjectMixin):
    """Translation object."""

    PARAMS: Tuple[str, ...] = (
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
        """List changes in the translation."""
        self.ensure_loaded("changes_list_url")
        return self.weblate.list_changes(self._attribs["changes_list_url"])

    def download(self, convert=None):
        """Download translation file from server."""
        self.ensure_loaded("file_url")
        url = self._attribs["file_url"]
        if convert is not None:
            url = "{}?{}".format(url, urlencode({"format": convert}))
        return self.weblate.raw_request("get", url)

    def upload(self, file, overwrite=None, format=None, **kwargs):
        """Updoad a translation file to server."""
        self.ensure_loaded("file_url")
        url = self._attribs["file_url"]
        if format:
            files = {"file": (f"file.{format}", file)}
        else:
            files = {"file": file}
        if overwrite:
            kwargs["overwrite"] = "yes"

        return self.weblate.request("post", url, files=files, data=kwargs)

    def delete(self):
        self.weblate.raw_request("delete", self._url)

    def units(self, **kwargs):
        """List units in the translation."""
        self.ensure_loaded("units_list_url")
        return self.weblate.list_units(self._attribs["units_list_url"], params=kwargs)


class Statistics(LazyObject):
    """Statistics object."""

    PARAMS: Tuple[str, ...] = (
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

    PARAMS: Tuple[str, ...] = Statistics.PARAMS + ("code", "last_author")


class Change(LazyObject):
    """Change object."""

    PARAMS: Tuple[str, ...] = (
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


class Unit(LazyObject):
    """Unit object."""

    PARAMS: Tuple[str, ...] = (
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
    ID = "id"
    MAPPINGS = {"translation": Translation}

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
