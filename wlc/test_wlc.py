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
"""Test the module."""
from unittest import TestCase

from wlc import Weblate, WeblateException
import httpretty
import os

DATA_TEST_BASE = os.path.join(os.path.dirname(__file__), 'test_data', 'api')


class ResponseHandler(object):
    def __init__(self, body, filename):
        self.body = body
        self.filename = filename

    def __call__(self, request, uri, headers):
        filename = None
        if request.method != 'GET':
            filename = '--'.join(self.filename, request.method)
        elif '?' in request.path:
            filename = '?'.join(self.filename, request.path.split('?', 1)[-1])

        if filename is not None:
            with open(filename, 'rb') as handle:
                return (200, headers, handle.read())
        return (200, headers, self.body)


def register_uri(path, domain='http://127.0.0.1:8000/api'):
    """Simplified URL registration"""
    filename = os.path.join(DATA_TEST_BASE, path.replace('/', '-'))
    url = '/'.join((domain, path, ''))
    with open(filename, 'rb') as handle:
        httpretty.register_uri(
            httpretty.GET,
            url,
            body=ResponseHandler(handle.read(), filename),
            content_type='application/json'
        )


def register_error(path, code, domain='http://127.0.0.1:8000/api'):
    """Simplified URL error registration"""
    url = '/'.join((domain, path, ''))
    httpretty.register_uri(
        httpretty.GET,
        url,
        status=code
    )


def register_uris():
    """Register URIs for httpretty."""
    paths = (
        'projects', 'components', 'translations',
        'projects/hello',
        'projects/invalid',
        'components/hello/weblate',
        'translations/hello/weblate/cs',
        'projects/hello/repository',
        'components/hello/weblate/repository',
        'translations/hello/weblate/cs/repository',
    )
    for path in paths:
        register_uri(path)

    register_uri('projects', domain='https://example.net')
    register_error('projects/nonexisting', 404)
    register_error('projects/denied', 403)
    register_error('projects/throttled', 429)
    register_error('projects/error', 500)


class WeblateErrorTest(TestCase):
    """Testing error handling"""

    @httpretty.activate
    def test_nonexisting(self):
        """Test listing projects."""
        register_uris()
        with self.assertRaisesRegex(WeblateException, 'not found'):
            Weblate().get_object('nonexisting')

    @httpretty.activate
    def test_denied(self):
        """Test listing projects."""
        register_uris()
        with self.assertRaisesRegex(WeblateException, 'permission'):
            Weblate().get_object('denied')

    @httpretty.activate
    def test_throttled(self):
        """Test listing projects."""
        register_uris()
        with self.assertRaisesRegex(WeblateException, 'Throttling'):
            Weblate().get_object('throttled')

    @httpretty.activate
    def test_error(self):
        """Test listing projects."""
        register_uris()
        with self.assertRaisesRegex(WeblateException, '500'):
            Weblate().get_object('error')

    @httpretty.activate
    def test_invalid(self):
        """Test listing projects."""
        register_uris()
        with self.assertRaisesRegex(WeblateException, 'invalid JSON'):
            Weblate().get_object('invalid')


class WeblateTest(TestCase):

    """Testing of Weblate class."""

    @httpretty.activate
    def test_projects(self):
        """Test listing projects."""
        register_uris()
        self.assertEqual(
            len(Weblate().list_projects()),
            2,
        )

    @httpretty.activate
    def test_components(self):
        """Test listing components."""
        register_uris()
        self.assertEqual(
            len(Weblate().list_components()),
            2,
        )

    @httpretty.activate
    def test_translations(self):
        """Test listing translations."""
        register_uris()
        self.assertEqual(
            len(Weblate().list_translations()),
            20,
        )

    @httpretty.activate
    def test_project(self):
        """Test getting project."""
        register_uris()
        project = Weblate().get_object('hello')
        self.assertEqual(
            project.name,
            'Hello',
        )
        repository = project.repository()
        self.assertFalse(
            repository.needs_commit
        )

    @httpretty.activate
    def test_component(self):
        """Test getting component."""
        register_uris()
        component = Weblate().get_object('hello/weblate')
        self.assertEqual(
            component.name,
            'Weblate',
        )
        repository = component.repository()
        self.assertFalse(
            repository.needs_commit
        )

    @httpretty.activate
    def test_translation(self):
        """Test getting translation."""
        register_uris()
        translation = Weblate().get_object('hello/weblate/cs')
        self.assertEqual(
            translation.language.code,
            'cs',
        )
        repository = translation.repository()
        self.assertFalse(
            repository.needs_commit
        )
