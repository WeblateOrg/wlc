# -*- coding: utf-8 -*-
#
# Copyright © 2016 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate Client <https://github.com/nijel/wlc>
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
from __future__ import unicode_literals

from six.moves.urllib.request import Request, urlopen
from six.moves.urllib.parse import urlencode

import json

__version__ = '0.1'

URL = 'https://weblate.org/'
DEVEL_URL = 'https://github.com/nijel/wlc'
API_URL = 'http://127.0.0.1:8000/api/'
USER_AGENT = 'wlc/{0}'.format(__version__)


class WeblateException(Exception):
    """Generic error."""


class Weblate(object):
    def __init__(self, key='', url=API_URL, config=None):
        """Create the object, storing key and API url."""
        if config is not None:
            self.key = config.get(config.section, 'key')
            self.url = config.get(config.section, 'url')
        else:
            self.key = key
            self.url = url

    def request(self, path, params=None):
        """Constructs request object"""
        if not path.startswith('http'):
            path = '{0}{1}'.format(self.url, path)
        request = Request(path)
        request.add_header('User-Agent', USER_AGENT)
        request.add_header('Accept', 'application/json')
        if self.key:
            request.add_header(
                'Authorization',
                'Token %s' % self.key
            )

        handle = urlopen(request, params)
        content = handle.read()

        result = json.loads(content.decode('utf-8'))

        return result

    def post(self, path, **kwargs):
        """Perform POST request on the API."""
        params = urlencode(
            {key: val.encode('utf-8') for key, val in kwargs.items()}
        )
        return self.request(path, params)

    def get(self, path):
        """Perform GET request on the API."""
        return self.request(path)

    def _list_factory(self, path, parser):
        """Wrapper for listing objects"""
        data = self.get(path)
        # TODO: handle pagination
        return [
            parser(weblate=self, **item) for item in data['results']
        ]

    def list_projects(self):
        """Lists projects in the instance"""
        return self._list_factory('projects/', Project)

    def list_components(self):
        """Lists components in the instance"""
        return self._list_factory('components/', Component)

    def list_translations(self):
        """Lists translations in the instance"""
        return self._list_factory('translations/', Translation)

    def list_languages(self):
        """Lists languages in the instance"""
        return self._list_factory('languages/', Language)


class LazyObject(object):
    """Object which supports deferred loading"""
    _params = ()
    _mappings = {}
    _url = None
    _weblate = None
    _loaded = False
    _data = None
    _id = 'url'

    def __init__(self, weblate, url, **kwargs):
        self._weblate = weblate
        self._url = url
        self._data = {}
        self._load_params(**kwargs)
        self._load_params(url=url)

    def _load_params(self, **kwargs):
        for param in self._params:
            if param in kwargs:
                if param in self._mappings:
                    self._data[param] = self._mappings[param](
                        self._weblate, **kwargs[param]
                    )
                else:
                    self._data[param] = kwargs[param]

    def _lazy_load(self):
        if self._loaded:
            raise WeblateException('Failed to load')
        data = self._weblate.get(self._url)
        self._load_params(**data)
        self._loaded = True

    def __getattr__(self, name):
        if name not in self._params:
            raise AttributeError()
        if name not in self._data:
            self._lazy_load()
        return self._data[name]

    def keys(self):
        return self._params

    def items(self):
        for key in self._params:
            yield key, self.__getattr__(key)

    def to_value(self):
        return self.__getattr__(self._id)


class Language(LazyObject):
    """Language object"""
    _params = (
        'url', 'web_url',
        'code', 'name', 'nplurals', 'pluralequation', 'direction',
    )
    _id = 'code'


class Project(LazyObject):
    """Project object"""
    _params = (
        'url', 'web_url',
        'name', 'slug', 'web', 'source_language'
    )
    _id = 'slug'
    _mappings = {
        'source_language': Language,
    }


class Component(LazyObject):
    """Component object"""
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


class Translation(LazyObject):
    """Translation object"""
    _params = (
        'url', 'web_url',
        'language', 'component', 'translated', 'fuzzy', 'total',
        'translated_words', 'fuzzy_words', 'failing_checks_words',
        'total_words', 'failing_checks', 'have_suggestion', 'have_comment',
        'language_code', 'filename', 'revision', 'share_url', 'translate_url',
        'is_template', 'translated_percent', 'fuzzy_percent',
        'failing_checks_percent', 'last_change', 'last_author',
    )
    _id = 'slug'
    _mappings = {
        'language': Language,
        'component': Component,
    }
