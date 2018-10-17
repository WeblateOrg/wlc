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
"""Test the module."""
from .test_base import APITest

import io

from wlc import (
    Weblate, WeblateException, Project, Component, Translation,
    Change,
)


class WeblateErrorTest(APITest):

    """Testing error handling."""

    def test_nonexisting(self):
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, 'not found'):
            Weblate().get_object('nonexisting')

    def test_denied(self):
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, 'permission'):
            Weblate().get_object('denied')

    def test_throttled(self):
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, 'Throttling'):
            Weblate().get_object('throttled')

    def test_error(self):
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, '500'):
            Weblate().get_object('error')

    def test_oserror(self):
        """Test listing projects."""
        with self.assertRaises(IOError):
            Weblate().get_object('io')

    def test_invalid(self):
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, 'invalid JSON'):
            Weblate().get_object('invalid')

    def test_too_long(self):
        """Test listing projects."""
        with self.assertRaises(ValueError):
            Weblate().get_object('a/b/c/d')

    def test_invalid_attribute(self):
        """Test attributes getting."""
        obj = Weblate().get_object('hello')
        self.assertEqual(obj.name, 'Hello')
        self.assertEqual(getattr(obj, 'name'), 'Hello')
        with self.assertRaises(AttributeError):
            getattr(obj, 'invalid_attribute')


class WeblateTest(APITest):

    """Testing of Weblate class."""

    def test_languages(self):
        """Test listing projects."""
        self.assertEqual(
            len(list(Weblate().list_languages())),
            47,
        )

    def test_projects(self):
        """Test listing projects."""
        self.assertEqual(
            len(list(Weblate().list_projects())),
            2,
        )

    def test_components(self):
        """Test listing components."""
        self.assertEqual(
            len(list(Weblate().list_components())),
            2,
        )

    def test_translations(self):
        """Test listing translations."""
        self.assertEqual(
            len(list(Weblate().list_translations())),
            50,
        )

    def test_authentication(self):
        """Test authentication against server."""
        with self.assertRaisesRegex(WeblateException, 'permission'):
            obj = Weblate().get_object('acl')
        obj = Weblate(key='KEY').get_object('acl')
        self.assertEqual(obj.name, 'ACL')

    def test_ensure_loaded(self):
        """Test lazy loading of attributes."""
        obj = Weblate().get_object('hello')
        obj.ensure_loaded('missing')
        obj.ensure_loaded('missing')
        with self.assertRaises(AttributeError):
            getattr(obj, 'missing')


class ObjectTest(object):

    """Base class for objects testing."""

    _name = None
    _cls = None

    def get(self):
        """Return remote object."""
        return Weblate().get_object(self._name)

    def test_get(self):
        """Test getting project."""
        obj = self.get()
        self.assertIsInstance(obj, self._cls)
        self.check_object(obj)

    def check_object(self, obj):
        """Perform verification whether object is valid."""
        raise NotImplementedError()

    def test_refresh(self):
        """Object refreshing test."""
        obj = self.get()
        obj.refresh()
        self.assertIsInstance(obj, self._cls)
        self.check_object(obj)

    def check_list(self, obj):
        """Perform verification whether listing is valid."""
        raise NotImplementedError()

    def test_list(self):
        """Item listing test."""
        obj = self.get()
        self.check_list(
            obj.list()
        )

    def test_changes(self):
        """Item listing test."""
        obj = self.get()
        lst = list(obj.changes())
        self.assertEqual(
            len(lst),
            2
        )
        self.assertIsInstance(lst[0], Change)

    def test_repository(self):
        """Repository get test."""
        obj = self.get()
        repository = obj.repository()
        self.assertFalse(
            repository.needs_commit
        )

    def test_repository_commit(self):
        """Repository commit test."""
        obj = self.get()
        repository = obj.repository()
        self.assertEqual(
            repository.commit(),
            {'result': True}
        )

    def test_commit(self):
        """Direct commit test."""
        obj = self.get()
        self.assertEqual(
            obj.commit(),
            {'result': True}
        )

    def test_pull(self):
        """Direct pull test."""
        obj = self.get()
        self.assertEqual(
            obj.pull(),
            {'result': True}
        )

    def test_reset(self):
        """Direct reset test."""
        obj = self.get()
        self.assertEqual(
            obj.reset(),
            {'result': True}
        )

    def test_cleanup(self):
        """Direct cleanup test."""
        obj = self.get()
        self.assertEqual(
            obj.cleanup(),
            {'result': True}
        )

    def test_push(self):
        """Direct push test."""
        obj = self.get()
        self.assertEqual(
            obj.push(),
            {
                'result': False,
                'detail': 'Push is disabled for Hello/Weblate.',
            }
        )


class ProjectTest(ObjectTest, APITest):

    """Project object tests."""

    _name = 'hello'
    _cls = Project

    def check_object(self, obj):
        """Perform verification whether object is valid."""
        self.assertEqual(
            obj.name,
            'Hello',
        )

    def check_list(self, obj):
        """Perform verification whether listing is valid."""
        lst = list(obj)
        self.assertEqual(
            len(lst),
            2
        )
        self.assertIsInstance(lst[0], Component)

    def test_statistics(self):
        """Component statistics test."""
        obj = self.get()
        self.assertEqual(2, len(list(obj.statistics())))


class ComponentTest(ObjectTest, APITest):

    """Component object tests."""

    _name = 'hello/weblate'
    _cls = Component

    def check_object(self, obj):
        """Perform verification whether object is valid."""
        self.assertEqual(
            obj.name,
            'Weblate',
        )

    def check_list(self, obj):
        """Perform verification whether listing is valid."""
        lst = list(obj)
        self.assertEqual(
            len(lst),
            33
        )
        self.assertIsInstance(lst[0], Translation)

    def test_statistics(self):
        """Component statistics test."""
        obj = self.get()
        self.assertEqual(33, len(list(obj.statistics())))

    def test_lock_status(self):
        """Component lock status test."""
        obj = self.get()
        self.assertEqual(
            {'locked': False},
            obj.lock_status()
        )

    def test_lock(self):
        """Component lock test."""
        obj = self.get()
        self.assertEqual(
            {'locked': True},
            obj.lock()
        )

    def test_unlock(self):
        """Component unlock test."""
        obj = self.get()
        self.assertEqual(
            {'locked': False},
            obj.unlock()
        )


class TranslationTest(ObjectTest, APITest):

    """Translation object tests."""

    _name = 'hello/weblate/cs'
    _cls = Translation

    def check_object(self, obj):
        """Perform verification whether object is valid."""
        self.assertEqual(
            obj.language.code,
            'cs',
        )

    def check_list(self, obj):
        """Perform verification whether listing is valid."""
        self.assertIsInstance(obj, Translation)

    def test_statistics(self):
        """Translation statistics test."""
        obj = self.get()
        data = obj.statistics()
        self.assertEqual(
            data.name,
            'Czech',
        )

    def test_download(self):
        """Test verbatim file download."""
        obj = self.get()
        content = obj.download()
        self.assertIn(
            b'Plural-Forms:',
            content
        )

    def test_download_csv(self):
        """Test dowload of file converted to CSV."""
        obj = self.get()
        content = obj.download('csv')
        self.assertIn(
            b'"location"',
            content
        )

    def test_upload(self):
        """Test file upload."""
        obj = self.get()
        file = io.StringIO("test upload data")

        obj.upload(file)
