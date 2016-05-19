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

from wlc import Weblate, WeblateException


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

    def test_projects(self):
        """Test listing projects."""
        self.assertEqual(
            len(Weblate().list_projects()),
            2,
        )

    def test_components(self):
        """Test listing components."""
        self.assertEqual(
            len(Weblate().list_components()),
            2,
        )

    def test_translations(self):
        """Test listing translations."""
        self.assertEqual(
            len(Weblate().list_translations()),
            20,
        )


class ProjectTest(APITest):
    def test_project(self):
        """Test getting project."""
        project = Weblate().get_object('hello')
        self.assertEqual(
            project.name,
            'Hello',
        )
        repository = project.repository()
        self.assertFalse(
            repository.needs_commit
        )
        self.assertEqual(
            len(project.list()),
            2
        )


class ComponentTest(APITest):
    def test_component(self):
        """Test getting component."""
        component = Weblate().get_object('hello/weblate')
        self.assertEqual(
            component.name,
            'Weblate',
        )
        repository = component.repository()
        self.assertFalse(
            repository.needs_commit
        )
        self.assertEqual(
            len(component.list()),
            20 # TODO: Should return 33 with pagination
        )


class TranslationTest(APITest):
    def test_translation(self):
        """Test getting translation."""
        translation = Weblate().get_object('hello/weblate/cs')
        self.assertEqual(
            translation.language.code,
            'cs',
        )
        repository = translation.repository()
        self.assertFalse(
            repository.needs_commit
        )
        self.assertEqual(
            translation.list(),
            translation
        )
