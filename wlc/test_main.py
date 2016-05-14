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
"""Test command line interface."""

from unittest import TestCase
from io import StringIO, BytesIO
import httpretty
import json
import sys
import os

import wlc
from wlc.main import main
from wlc.config import WeblateConfig
from wlc.test_wlc import register_uris

TEST_CONFIG = os.path.join(os.path.dirname(__file__), 'test_data', 'wlc')
TEST_SECTION = os.path.join(os.path.dirname(__file__), 'test_data', 'section')


def execute(args, binary=False, settings=None, stdout=None):
    """Execute command and return output."""
    if settings is None:
        settings = ()
    elif not settings:
        settings = None
    if binary and sys.version_info < (3, 0):
        output = BytesIO()
    else:
        output = StringIO()
    backup = sys.stdout
    try:
        sys.stdout = output
        if stdout:
            stdout = output
        main(args=args, settings=settings, stdout=stdout)
    finally:
        sys.stdout = backup
    return output.getvalue()


class TestSettings(TestCase):

    """Test settings handling."""

    @httpretty.activate
    def test_commandline(self):
        """Configuration using commandline."""
        register_uris()
        output = execute(['--url', 'https://example.net/', 'list-projects'])
        self.assertIn('Hello', output)

    @httpretty.activate
    def test_stdout(self):
        """Configuration using params."""
        register_uris()
        output = execute(['list-projects'], stdout=True)
        self.assertIn('Hello', output)

    @httpretty.activate
    def test_settings(self):
        """Configuration using settings param."""
        register_uris()
        output = execute(
            ['list-projects'],
            settings=(('weblate', 'url', 'https://example.net/'),)
        )
        self.assertIn('Hello', output)

    @httpretty.activate
    def test_config(self):
        """Configuration using custom config file."""
        register_uris()
        output = execute(['--config', TEST_CONFIG, 'list-projects'], settings=False)
        self.assertIn('Hello', output)

    @httpretty.activate
    def test_config_section(self):
        """Configuration using custom config file section."""
        register_uris()
        output = execute(
            [
                '--config', TEST_SECTION,
                '--config-section', 'custom',
                'list-projects'
            ],
            settings=False
        )
        self.assertIn('Hello', output)

    def test_parsing(self):
        """Test config file parsing."""
        config = WeblateConfig()
        self.assertEqual(config.get('weblate', 'url'), wlc.API_URL)
        config.load()
        config.load(TEST_CONFIG)
        self.assertEqual(config.get('weblate', 'url'), 'https://example.net/')

    def test_argv(self):
        """Test sys.argv processing."""
        backup = sys.argv
        try:
            sys.argv = ['wlc', 'version']
            output = execute(None)
            self.assertIn('version: {0}'.format(wlc.__version__), output)
        finally:
            sys.argv = backup


class TestOutput(TestCase):

    """Test output formatting."""

    def test_version_text(self):
        """Test version printing."""
        output = execute(['--format', 'text', 'version'])
        self.assertIn('version: {0}'.format(wlc.__version__), output)

    def test_version_json(self):
        """Test version printing."""
        output = execute(['--format', 'json', 'version'], True)
        values = json.loads(output)
        self.assertEqual({'version': wlc.__version__}, values)

    def test_version_csv(self):
        """Test version printing."""
        output = execute(['--format', 'csv', 'version'], True)
        self.assertIn('version,{0}'.format(wlc.__version__), output)

    def test_version_html(self):
        """Test version printing."""
        output = execute(['--format', 'html', 'version'])
        self.assertIn(wlc.__version__, output)

    @httpretty.activate
    def test_projects_text(self):
        """Test projects printing."""
        register_uris()
        output = execute(['--format', 'text', 'list-projects'])
        self.assertIn('name: {0}'.format('Hello'), output)

    @httpretty.activate
    def test_projects_json(self):
        """Test projects printing."""
        register_uris()
        output = execute(['--format', 'json', 'list-projects'], True)
        values = json.loads(output)
        self.assertEqual(2, len(values))

    @httpretty.activate
    def test_projects_csv(self):
        """Test projects printing."""
        register_uris()
        output = execute(['--format', 'csv', 'list-projects'], True)
        self.assertIn('Hello', output)

    @httpretty.activate
    def test_projects_html(self):
        """Test projects printing."""
        register_uris()
        output = execute(['--format', 'html', 'list-projects'])
        self.assertIn('Hello', output)


class TestCommands(TestCase):
    @httpretty.activate
    def test_ls(self):
        """Project listing."""
        register_uris()
        output = execute(
            [
                'ls'
            ],
        )
        self.assertIn('Hello', output)

    @httpretty.activate
    def test_list_projects(self):
        """Project listing."""
        register_uris()
        output = execute(
            [
                'list-projects'
            ],
        )
        self.assertIn('Hello', output)

    @httpretty.activate
    def test_list_components(self):
        """Project listing."""
        register_uris()
        output = execute(
            [
                'list-components'
            ],
        )
        self.assertIn('/hello/weblate', output)

    @httpretty.activate
    def test_list_translations(self):
        """Project listing."""
        register_uris()
        output = execute(
            [
                'list-translations'
            ],
        )
        self.assertIn('/hello/weblate/cs/', output)
