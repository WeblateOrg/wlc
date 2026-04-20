# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Weblate HTTP client."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .const import API_URL, LOCALHOST_ADDRESSES, USER_AGENT
from .exceptions import (
    WeblateDeniedError,
    WeblateException,
    WeblatePermissionError,
    WeblateThrottlingError,
)
from .http_debug import log_failure_debug, log_request_debug, log_response_debug
from .models import Category, Change, Component, Language, Project, Translation, Unit

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Mapping


class Weblate:
    """Weblate API wrapper object."""

    def __init__(
        self,
        key: str = "",
        url: str = API_URL,
        config=None,
        retries: int = 0,
        status_forcelist: Collection[int] | None = None,
        allowed_methods: Collection[str] | None = None,
        backoff_factor: float = 0,
        timeout: int = 300,
    ) -> None:
        """Create the object, storing key, API url and requests retry args."""
        self.session = requests.Session()
        if config is not None:
            self.url, self.key = config.get_url_key()
            (
                self.retry_total,
                self.status_forcelist,
                self.allowed_methods,
                self.backoff_factor,
                self.timeout,
            ) = config.get_request_options()
        else:
            self.key = key
            self.url = url
            self.retry_total = retries
            self.status_forcelist = status_forcelist
            self.timeout = timeout
            self.allowed_methods = allowed_methods or [
                "HEAD",
                "GET",
                "PUT",
                "PATCH",
                "DELETE",
                "OPTIONS",
                "TRACE",
            ]
            self.backoff_factor = backoff_factor

        retry_config = Retry(
            total=self.retry_total,
            backoff_factor=self.backoff_factor,
            status_forcelist=self.status_forcelist,
            allowed_methods=self.allowed_methods,
            raise_on_status=False,
        )
        self.adapter = HTTPAdapter(pool_connections=1, max_retries=retry_config)

        if not self.url.endswith("/"):
            self.url += "/"
        self.api_origin = self.get_origin(urlparse(self.url))

    @staticmethod
    def get_effective_port(url) -> int | None:
        """Return explicit port or the default for the URL scheme."""
        try:
            if url.port is not None:
                return url.port
        except ValueError as error:
            raise WeblateException("Server returned an invalid URL.") from error
        if url.scheme == "https":
            return 443
        if url.scheme == "http":
            return 80
        return None

    @classmethod
    def get_origin(cls, url) -> tuple[str, str | None, int | None]:
        """Return normalized origin tuple for a parsed URL."""
        return (url.scheme, url.hostname, cls.get_effective_port(url))

    def normalize_request_url(self, path: str) -> str:
        """Resolve a request path and reject cross-origin targets."""
        url = urlparse(urljoin(self.url, path))
        if self.get_origin(url) != self.api_origin:
            raise WeblateException(
                "Server returned a URL outside the configured API origin."
            )
        return url.geturl()

    @staticmethod
    def permission_error_message(error):
        """Get detail from serialized DRF PermissionDenied exception."""
        try:
            response_json = error.response.json()
        except json.JSONDecodeError:
            return None

        # Since Weblate 5.10
        if "errors" in response_json:
            return ", ".join(error["detail"] for error in response_json["errors"])

        # Weblate before 5.10
        if "detail" in response_json:
            return response_json["detail"]

        return None

    def process_error(self, error) -> None:
        """Raise WeblateException for known HTTP errors."""
        if isinstance(error, requests.HTTPError):
            status_code = error.response.status_code

            match status_code:
                case _ if 300 <= status_code < 400:
                    raise WeblateException(
                        "Server responded with an unexpected HTTP redirect. "
                        "Please check your configuration."
                    ) from error
                case 429:
                    headers = error.response.headers
                    raise WeblateThrottlingError(
                        headers.get("X-RateLimit-Limit", "unknown"),
                        headers.get("Retry-After", "unknown"),
                    ) from error
                case 404:
                    raise WeblateException(
                        "Object not found on the server "
                        "(maybe operation is not supported on the server)"
                    ) from error
                case 403:
                    raise WeblatePermissionError(
                        self.permission_error_message(error)
                    ) from error
                case 401:
                    raise WeblateDeniedError from error
                case _:
                    reason = error.response.reason
                    try:
                        error_string = str(error.response.json())
                    # pylint: disable-next=broad-exception-caught
                    except Exception:  # noqa: BLE001
                        error_string = ""
                    raise WeblateException(
                        f"HTTP error {status_code}: {reason} {error_string}"
                    ) from error

    def raw_request(
        self,
        method: str,
        path: str,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> bytes:
        """Construct request object and returns raw content."""
        response = self.invoke_request(
            method, path, data=data, files=files, params=params
        )

        return response.content

    def request(
        self,
        method: str,
        path: str,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> dict:
        """Construct request object and returns json response."""
        response = self.invoke_request(
            method, path, data=data, files=files, params=params
        )

        try:
            return response.json()
        except ValueError as error:
            raise WeblateException("Server returned invalid JSON") from error

    def invoke_request(
        self,
        method: str,
        path: str,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Response:
        """Construct request object."""
        try:
            path = self.normalize_request_url(path)
        except WeblateException as error:
            log_failure_debug(method, path, error)
            raise
        headers = {"user-agent": USER_AGENT, "Accept": "application/json"}
        if self.key:
            headers["Authorization"] = f"Token {self.key}"
        verify_ssl = self.should_verify_ssl(path)

        # Disable insecure warnings for localhost
        if not verify_ssl:
            logging.captureWarnings(True)
        json_data: Mapping[str, Any] | None
        if files:
            # multipart/form upload
            json_data = None
        else:
            # JSON params to handle complex structures
            json_data = data
            data = None
        log_request_debug(
            method,
            path,
            headers,
            params=params,
            json_data=json_data,
            data=data,
            files=files,
        )
        try:
            self.session.mount(f"{urlparse(path).scheme}://", self.adapter)
            response = self.session.request(
                method,
                path,
                headers=headers,
                params=params,
                json=json_data,
                data=data,
                verify=verify_ssl,
                files=files,
                allow_redirects=False,
                timeout=self.timeout,
            )
            log_response_debug(response)
            response.raise_for_status()
            if 300 <= response.status_code < 400:
                raise requests.HTTPError("Server redirected", response=response)
        except requests.exceptions.RequestException as error:
            log_failure_debug(method, path, error)
            self.process_error(error)
            raise
        return response

    def post(self, path, files=None, params=None, **kwargs):
        """Perform POST request on the API."""
        return self.request("post", path, data=kwargs, files=files, params=params)

    def _post_factory(self, prefix, path, kwargs):
        """Wrapper for posting objects."""
        return self.post(f"{prefix}/{path}/", **kwargs)

    def get(self, path, params=None):
        """Perform GET request on the API."""
        return self.request("get", path, params=params)

    def list_factory(
        self,
        path: str,
        parser: Any,
        params: Mapping[str, Any] | None = None,
    ) -> Iterator[Any]:
        """Listing object wrapper."""
        while path is not None:
            data = self.get(path, params=params)
            if isinstance(data, list):
                for item in data:
                    yield parser(weblate=self, **item)
                break
            for item in data["results"]:
                yield parser(weblate=self, **item)

            path = data["next"]

    def _get_factory(self, prefix, path, parser):
        """Wrapper for getting objects."""
        data = self.get(f"{prefix}/{path}/")
        return parser(weblate=self, **data)

    def get_object(self, path):
        """
        Return object based on path.

        Operates on (project, component or translation objects.
        """
        parts = path.strip("/").split("/")
        try:
            int(path)
            return self.get_unit(path)
        except ValueError:
            pass
        match len(parts):
            case 3:
                return self.get_translation(path)
            case 2:
                return self.get_component(path)
            case 1:
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

    def list_categories(self, path="categories/"):
        """List categories in the instance."""
        return self.list_factory(path, Category)

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
        plural = plural or {"number": 2, "formula": "n != 1"}
        data = {"code": code, "name": name, "direction": direction, "plural": plural}
        return self.post("languages/", **data)

    @staticmethod
    def should_verify_ssl(path: str) -> bool:
        """Checks if it should verify ssl certificates."""
        url = urlparse(path)
        return url.hostname not in LOCALHOST_ADDRESSES
