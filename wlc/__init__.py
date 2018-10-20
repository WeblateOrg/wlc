# -*- coding: utf-8 -*-
#
# Copyright © 2016 - 2017 Michal Čihař <michal@cihar.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Weblate API client library."""

from urllib.parse import urlencode, urlparse
import requests
from requests import HTTPError

__version__ = '0.10'

URL = 'https://weblate.org/'
DEVEL_URL = 'https://github.com/WeblateOrg/wlc'
API_URL = 'http://127.0.0.1:8000/api/'
USER_AGENT = 'wlc/{0}'.format(__version__)
LOCALHOST_NETLOC = '127.0.0.1'

class WeblateException(Exception):

    """Generic error."""


class Weblate(object):

    """Weblate API wrapper object."""

    def __init__(self, key='', url=API_URL, config=None):
        """Create the object, storing key and API url."""
        if config is not None:
            self.url, self.key = config.get_url_key()
        else:
            self.key = key
            self.url = url

    @staticmethod
    def process_error(error):
        """Raise WeblateException for known HTTP errors."""
        if type(error) is HTTPError:
            status_code = error.response.status_code

            if status_code == 429:
                raise WeblateException(
                    'Throttling on the server'
                )
            elif status_code == 404:
                raise WeblateException(
                    'Object not found on the server '
                    '(maybe operation is not supported on the server)'
                )
            elif status_code == 403:
                raise WeblateException(
                    'You don\'t have permission to access this object'
                )

            reason = error.response.reason
            raise WeblateException(
                'HTTP error {0}: {1}'.format(status_code, reason)
            )

    def raw_request(self, method, path, params=None, files=None):
        """Construct request object and returns raw content."""
        r = self.invoke_request(method, path, params, files)

        return r.content

    def request(self, method, path, params=None, files=None):
        """Construct request object and returns json response."""
        r = self.invoke_request(method, path, params, files)

        try:
            result = r.json()
        except ValueError:
            raise WeblateException(
                'Server returned invalid JSON'
            )

        return result

    def invoke_request(self, method, path, params=None, files=None):
        """Construct request object."""
        if not path.startswith('http'):
            path = '{0}{1}'.format(self.url, path)
        headers = {'user-agent': USER_AGENT, 'Accept': 'application/json'}
        if self.key:
            headers['Authorization'] = 'Token {}'.format(self.key)
        verify_ssl = self._should_verify_ssl(path)
        try:
            r = requests.request(
                method,
                path,
                headers=headers,
                data=params,
                verify=verify_ssl,
                files=files
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as error:
            self.process_error(error)
            raise
        return r

    def post(self, path, **kwargs):
        """Perform POST request on the API."""
        return self.request('post', path, kwargs)

    def get(self, path):
        """Perform GET request on the API."""
        return self.request('get', path)

    def list_factory(self, path, parser):
        """Wrapper for listing objects."""
        while path is not None:
            data = self.get(path)
            for item in data['results']:
                yield parser(weblate=self, **item)

            path = data['next']

    def _get_factory(self, prefix, path, parser):
        """Wrapper for getting objects."""
        data = self.get('/'.join((prefix, path, '')))
        return parser(weblate=self, **data)

    def get_object(self, path):
        """Return object based on path.

        Operates on (project, component or translation objects.
        """
        parts = path.strip('/').split('/')
        if len(parts) == 3:
            return self.get_translation(path)
        elif len(parts) == 2:
            return self.get_component(path)
        elif len(parts) == 1:
            return self.get_project(path)
        raise ValueError('Not supported path: {0}'.format(path))

    def get_project(self, path):
        """Return project of given path."""
        return self._get_factory('projects', path, Project)

    def get_component(self, path):
        """Return component of given path."""
        return self._get_factory('components', path, Component)

    def get_translation(self, path):
        """Return translation of given path."""
        return self._get_factory('translations', path, Translation)

    def list_projects(self, path='projects/'):
        """List projects in the instance."""
        return self.list_factory(path, Project)

    def list_components(self, path='components/'):
        """List components in the instance."""
        return self.list_factory(path, Component)

    def list_changes(self, path='changes/'):
        """List components in the instance."""
        return self.list_factory(path, Change)

    def list_translations(self, path='translations/'):
        """List translations in the instance."""
        return self.list_factory(path, Translation)

    def list_languages(self):
        """List languages in the instance."""
        return self.list_factory('languages/', Language)

    def _should_verify_ssl(self, path):
        """Cheks if it should verify ssl certificates."""
        url = urlparse(path)
        is_localhost = url.netloc.startswith(LOCALHOST_NETLOC)
        verify_ssl = url.scheme == 'https' and (not is_localhost)
        return verify_ssl

class LazyObject(dict):

    """Object which supports deferred loading."""

    _params = ()
    _mappings = {}
    _url = None
    weblate = None
    _loaded = False
    _data = None
    _attribs = None
    _id = 'url'

    def __init__(self, weblate, url, **kwargs):
        """Construct object for given Weblate instance."""
        super(LazyObject, self).__init__()
        self.weblate = weblate
        self._url = url
        self._data = {}
        self._attribs = {}
        self._load_params(**kwargs)
        self._load_params(url=url)

    def _load_params(self, **kwargs):
        for param in self._params:
            if param in kwargs:
                value = kwargs[param]
                if value is not None and param in self._mappings:
                    if isinstance(value, str):
                        self._data[param] = self._mappings[param](
                            self.weblate, url=value
                        )
                    else:
                        self._data[param] = self._mappings[param](
                            self.weblate, **value
                        )
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
        if name not in self._params:
            raise AttributeError(name)
        if name not in self._data:
            self.refresh()
        return self._data[name]

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __len__(self):
        return len(self._params)

    def keys(self):
        """Return list of attributes."""
        return self._params

    def items(self):
        """Iterator over attributes."""
        for key in self._params:
            yield key, self.__getattr__(key)

    def to_value(self):
        """Return identifier for the object."""
        self.ensure_loaded(self._id)
        return self.__getattr__(self._id)


class Language(LazyObject):

    """Language object."""

    _params = (
        'url', 'web_url',
        'code', 'name', 'nplurals', 'pluralequation', 'direction',
    )
    _id = 'code'


class LanguageStats(LazyObject):

    """Language object."""

    _params = (
        'total', 'code', 'translated_words', 'language', 'translated',
        'translated_percent', 'total_words', 'words_percent',
    )
    _id = 'code'


class RepoMixin(object):

    """Repository mixin providing generic repository wide operations."""

    def _get_repo_url(self):
        self.ensure_loaded('repository_url')
        return self._attribs['repository_url']

    def commit(self):
        """Commit Weblate changes."""
        return self.weblate.post(
            self._get_repo_url(),
            operation='commit'
        )

    def push(self):
        """Push Weblate changes upstream."""
        return self.weblate.post(
            self._get_repo_url(),
            operation='push'
        )

    def pull(self):
        """Pull upstream changes into Weblate."""
        return self.weblate.post(
            self._get_repo_url(),
            operation='pull'
        )

    def reset(self):
        """Reset Weblate repository to upstream."""
        return self.weblate.post(
            self._get_repo_url(),
            operation='reset'
        )

    def cleanup(self):
        """Cleanup Weblate repository from untracked files."""
        return self.weblate.post(
            self._get_repo_url(),
            operation='cleanup'
        )


class ProjectRepository(LazyObject, RepoMixin):

    """Repository object."""

    _params = ('url', 'needs_commit', 'needs_merge', 'needs_push')

    def _get_repo_url(self):
        """Return repository url."""
        return self._data['url']


class Repository(ProjectRepository):

    """Repository object."""

    _params = (
        'url', 'needs_commit', 'needs_merge', 'needs_push',
        'status', 'merge_failure', 'remote_commit',
    )


class RepoObjectMixin(RepoMixin):

    """Repository mixin."""

    _repository_class = ProjectRepository

    def repository(self):
        """Return repository object."""
        data = self.weblate.get(
            self._get_repo_url()
        )
        return self._repository_class(weblate=self.weblate, **data)


class Project(LazyObject, RepoObjectMixin):

    """Project object."""

    _params = (
        'url', 'web_url',
        'name', 'slug', 'web', 'source_language'
    )
    _id = 'slug'
    _mappings = {
        'source_language': Language,
    }

    def list(self):
        """List components in the project."""
        self.ensure_loaded('components_list_url')
        return self.weblate.list_components(
            self._attribs['components_list_url']
        )

    def statistics(self):
        """Return statistics for component."""
        self.ensure_loaded('statistics_url')
        url = self._attribs['statistics_url']
        return [
            LanguageStats(self.weblate, url, **item)
            for item in self.weblate.get(url)
        ]

    def changes(self):
        """List changes in the project."""
        self.ensure_loaded('changes_list_url')
        return self.weblate.list_changes(
            self._attribs['changes_list_url']
        )


class Component(LazyObject, RepoObjectMixin):

    """Component object."""

    _params = (
        'url', 'web_url',
        'name', 'slug', 'project', 'vcs', 'repo', 'git_export', 'branch',
        'filemask', 'template', 'new_base', 'file_format', 'license',
        'license_url',
    )
    _id = 'slug'
    _mappings = {
        'project': Project,
    }
    _repository_class = Repository

    def list(self):
        """List translations in the component."""
        self.ensure_loaded('translations_url')
        return self.weblate.list_translations(
            self._attribs['translations_url']
        )

    def statistics(self):
        """Return statistics for component."""
        self.ensure_loaded('statistics_url')
        return self.weblate.list_factory(
            self._attribs['statistics_url'], Statistics
        )

    def _get_lock_url(self):
        self.ensure_loaded('lock_url')
        return self._attribs['lock_url']

    def lock(self):
        """Lock component from translations."""
        return self.weblate.post(
            self._get_lock_url(),
            lock=1
        )

    def unlock(self):
        """Unlock component from translations."""
        return self.weblate.post(
            self._get_lock_url(),
            lock=0
        )

    def lock_status(self):
        """Return component lock status."""
        return self.weblate.get(
            self._get_lock_url(),
        )

    def changes(self):
        """List changes in the project."""
        self.ensure_loaded('changes_list_url')
        return self.weblate.list_changes(
            self._attribs['changes_list_url']
        )


class Translation(LazyObject, RepoObjectMixin):

    """Translation object."""

    _params = (
        'url', 'web_url',
        'language', 'component', 'translated', 'fuzzy', 'total',
        'translated_words', 'fuzzy_words', 'failing_checks_words',
        'total_words', 'failing_checks', 'have_suggestion', 'have_comment',
        'language_code', 'filename', 'revision', 'share_url', 'translate_url',
        'is_template', 'translated_percent', 'fuzzy_percent',
        'failing_checks_percent', 'last_change', 'last_author',
    )
    _id = 'language_code'
    _mappings = {
        'language': Language,
        'component': Component,
    }
    _repository_class = Repository

    def list(self):
        """API compatibility method, returns self."""
        self.ensure_loaded('last_author')
        return self

    def statistics(self):
        """Return statistics for translation."""
        self.ensure_loaded('statistics_url')
        data = self.weblate.get(self._attribs['statistics_url'])
        return Statistics(weblate=self.weblate, **data)

    def changes(self):
        """List changes in the project."""
        self.ensure_loaded('changes_list_url')
        return self.weblate.list_changes(
            self._attribs['changes_list_url']
        )

    def download(self, convert=None):
        """Download translation file from server."""
        self.ensure_loaded('file_url')
        url = self._attribs['file_url']
        if convert is not None:
            url = '{0}?{1}'.format(
                url,
                urlencode({'format': convert})
            )
        return self.weblate.raw_request('get', url)

    def upload(self, file, overwrite=None):
        """Download translation file from server."""
        self.ensure_loaded('file_url')
        url = self._attribs['file_url']
        files = {'file': file}
        params = None

        if overwrite:
            params = {'overwrite': 'yes'}

        return self.weblate.request('post', url, files=files, params=params)


class Statistics(LazyObject):

    """Statistics object."""

    _params = (
        'last_author', 'code', 'failing_percent', 'url', 'translated_percent',
        'total_words', 'failing', 'translated_words', 'url_translate',
        'fuzzy_percent', 'translated', 'fuzzy', 'total', 'last_change', 'name',
    )


class Change(LazyObject):

    """Change object."""

    _params = (
        'url', 'unit', 'translation', 'component',
        'timestamp', 'action_name', 'target',
    )
    _id = 'id'
    _mappings = {
        'translation': Translation,
        'component': Component,
    }
