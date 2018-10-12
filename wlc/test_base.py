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
"""Test helpers."""
import collections
import os
import re
from unittest import TestCase

import httpretty
from requests_toolbelt.multipart import decoder

DATA_TEST_BASE = os.path.join(os.path.dirname(__file__), 'test_data', 'api')


class ResponseHandler(object):
    """httpretty response handler."""

    def __init__(self, body, filename, auth=False):
        """Construct response handler object."""
        self.body = body
        self.filename = filename
        self.auth = auth

    def __call__(self, request, uri, headers):
        """Function call interface for httpretty."""
        if self.auth and request.headers['Authorization'] != 'Token KEY':
            return 403, headers, ''

        content = self.get_content(request)

        return 200, headers, content

    def get_content(self, request):
        """Return content for given request."""
        filename = self.get_filename(request)

        if filename is not None:
            with open(filename, 'rb') as handle:
                return handle.read()

        return self.body

    def get_filename(self, request):
        """Return filename for given request."""
        filename = None
        if request.method != 'GET':
            content_type = request.headers.get('content-type', None)

            if content_type is not None \
                    and content_type.startswith('multipart/form-data'):
                filename = self.get_multipart_filename(content_type, request)
            else:
                filename = '--'.join((
                    self.filename,
                    request.method,
                    request.body.decode('ascii')
                ))
        elif '?' in request.path:
            filename = '--'.join(
                (self.filename, request.method, request.path.split('?', 1)[-1])
            )
        return filename

    def get_multipart_filename(self, content_type, request):
        """Return filename for given multipart request."""
        body = request.body
        multipart_data = decoder.MultipartDecoder(body, content_type)
        multipart_dict = {}
        filename_array = [self.filename, request.method]
        for part in multipart_data.parts:
            content_disposition = part.headers.get(
                'Content-Disposition'.encode(),
                None
            )

            decoded_cd = content_disposition.decode("utf-8")
            multipart_name = self.get_multipart_name(decoded_cd)

            multipart_dict[multipart_name] = part.text.replace(' ', '-')

        ordered_dict = collections.OrderedDict(
            sorted(multipart_dict.items())
        )

        for key, value in ordered_dict.items():
            filename_array.append(key + '=' + value)
        filename = '--'.join(filename_array)

        return filename

    # simple implementation instead of one based on the rfc6266 parser,
    # as rfc6266 fails on python 3.7
    @staticmethod
    def get_multipart_name(content_disposition):
        """Return multipart name from content disposition."""
        m = re.search(
            'name\s*=\s*"(?P<name>[A-Za-z]+)"',
            content_disposition)

        name = m.group('name')

        return name


def register_uri(path, domain='http://127.0.0.1:8000/api', auth=False):
    """Simplified URL registration."""
    filename = os.path.join(DATA_TEST_BASE, path.replace('/', '-'))
    url = '/'.join((domain, path, ''))
    with open(filename, 'rb') as handle:
        httpretty.register_uri(
            httpretty.GET,
            url,
            body=ResponseHandler(handle.read(), filename, auth),
            content_type='application/json'
        )
        httpretty.register_uri(
            httpretty.POST,
            url,
            body=ResponseHandler(handle.read(), filename, auth),
            content_type='application/json'
        )


def raise_error(request, uri, headers):
    """Raise IOError."""
    # pylint: disable=W0613
    raise IOError('Some error')


def register_error(path, code, domain='http://127.0.0.1:8000/api', body=None):
    """Simplified URL error registration."""
    url = '/'.join((domain, path, ''))
    httpretty.register_uri(
        httpretty.GET,
        url,
        body=body,
        status=code
    )


def register_uris():
    """Register URIs for httpretty."""
    paths = (
        'changes',
        'projects', 'components', 'translations',
        'projects/hello',
        'projects/hello/changes',
        'projects/hello/components',
        'projects/hello/statistics',
        'projects/empty',
        'projects/empty/components',
        'projects/invalid',
        'components/hello/weblate',
        'components/hello/android',
        'translations/hello/weblate/cs',
        'projects/hello/repository',
        'components/hello/weblate/repository',
        'components/hello/weblate/changes',
        'translations/hello/weblate/cs/file',
        'translations/hello/weblate/cs/repository',
        'translations/hello/weblate/cs/changes',
        'components/hello/weblate/statistics',
        'translations/hello/weblate/cs/statistics',
        'components/hello/weblate/translations',
        'components/hello/weblate/lock',
        'languages',
    )
    for path in paths:
        register_uri(path)

    register_uri('projects/acl', auth=True)

    register_uri('projects', domain='https://example.net')
    register_error('projects/nonexisting', 404)
    register_error('projects/denied', 403)
    register_error('projects/throttled', 429)
    register_error('projects/error', 500)
    register_error('projects/io', 500, body=raise_error)


class APITest(TestCase):
    """Base class for API testing."""

    def setUp(self):
        """Enable httpretty and register urls."""
        httpretty.enable()
        register_uris()

    def tearDown(self):
        """Disable httpretty."""
        httpretty.disable()
        httpretty.reset()
