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
from .test_base import APITest

from wlc import (
    Weblate, WeblateException, Project, Component, Translation
)


class WeblateErrorTest(APITest):
    """Testing error handling"""

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

    def test_invalid(self):
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, 'invalid JSON'):
            Weblate().get_object('invalid')


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


class ObjectTest(object):
    _name = None
    _cls = None

    def get(self):
        return Weblate().get_object(self._name)

    def test_get(self):
        """Test getting project."""
        obj = self.get()
        self.assertIsInstance(obj, self._cls)
        self.check_object(obj)

    def check_object(self, obj):
        raise NotImplementedError()

    def test_refresh(self):
        obj = self.get()
        obj.refresh()
        self.assertIsInstance(obj, self._cls)
        self.check_object(obj)

    def check_list(self, obj):
        raise NotImplementedError()

    def test_list(self):
        obj = self.get()
        self.check_list(
            obj.list()
        )

    def test_repository(self):
        obj = self.get()
        repository = obj.repository()
        self.assertFalse(
            repository.needs_commit
        )

    def test_repository_commit(self):
        obj = self.get()
        repository = obj.repository()
        self.assertEqual(
            repository.commit(),
            {'result': True}
        )

    def test_commit(self):
        obj = self.get()
        self.assertEqual(
            obj.commit(),
            {'result': True}
        )

    def test_pull(self):
        obj = self.get()
        self.assertEqual(
            obj.pull(),
            {'result': True}
        )

    def test_push(self):
        obj = self.get()
        self.assertEqual(
            obj.push(),
            {
                'result': False,
                'detail': 'Push is disabled for Hello/Weblate.',
            }
        )


class ProjectTest(ObjectTest, APITest):
    _name = 'hello'
    _cls = Project

    def check_object(self, obj):
        self.assertEqual(
            obj.name,
            'Hello',
        )

    def check_list(self, obj):
        lst = list(obj)
        self.assertEqual(
            len(lst),
            2
        )
        self.assertIsInstance(lst[0], Component)


class ComponentTest(ObjectTest, APITest):
    _name = 'hello/weblate'
    _cls = Component

    def check_object(self, obj):
        self.assertEqual(
            obj.name,
            'Weblate',
        )

    def check_list(self, obj):
        lst = list(obj)
        self.assertEqual(
            len(lst),
            33
        )
        self.assertIsInstance(lst[0], Translation)

    def test_statistics(self):
        obj = self.get()
        self.assertEqual(33, len(list(obj.statistics())))


class TranslationTest(ObjectTest, APITest):
    _name = 'hello/weblate/cs'
    _cls = Translation

    def check_object(self, obj):
        self.assertEqual(
            obj.language.code,
            'cs',
        )

    def check_list(self, obj):
        self.assertIsInstance(obj, Translation)

    def test_statistics(self):
        obj = self.get()
        data = obj.statistics()
        self.assertEqual(
            data.name,
            'Czech',
        )
