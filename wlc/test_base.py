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
"""Test helpers."""
from unittest import TestCase

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
            filename = '--'.join(
                (self.filename, request.method, request.body.decode('ascii'))
            )
        elif '?' in request.path:
            filename = '?'.join(
                (self.filename, request.path.split('?', 1)[-1])
            )

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
        httpretty.register_uri(
            httpretty.POST,
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
        'components/hello/android',
        'translations/hello/weblate/cs',
        'projects/hello/repository',
        'components/hello/weblate/repository',
        'translations/hello/weblate/cs/repository',
        'components/hello/weblate/statistics',
        'translations/hello/weblate/cs/statistics',
        'projects/hello/components',
        'components/hello/weblate/translations',
        'languages',
    )
    for path in paths:
        register_uri(path)

    register_uri('projects', domain='https://example.net')
    register_error('projects/nonexisting', 404)
    register_error('projects/denied', 403)
    register_error('projects/throttled', 429)
    register_error('projects/error', 500)


class APITest(TestCase):
    def setUp(self):
        httpretty.enable()
        register_uris()

    def tearDown(self):
        httpretty.disable()
        httpretty.reset()
