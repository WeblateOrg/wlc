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

from io import StringIO, BytesIO
import httpretty
import json
import sys
import os

import wlc
from wlc.main import main
from wlc.config import WeblateConfig
from .test_base import APITest

TEST_CONFIG = os.path.join(os.path.dirname(__file__), 'test_data', 'wlc')
TEST_SECTION = os.path.join(os.path.dirname(__file__), 'test_data', 'section')


def execute(args, settings=None, stdout=None, expected=0):
    """Execute command and return output."""
    if settings is None:
        settings = ()
    elif not settings:
        settings = None
    output = StringIO()
    backup = sys.stdout
    backup_err = sys.stderr
    try:
        sys.stdout = output
        sys.stderr = output
        if stdout:
            stdout = output
        result = main(args=args, settings=settings, stdout=stdout)
        assert result == expected
    finally:
        sys.stdout = backup
        sys.stderr = backup_err
    return output.getvalue()


class TestSettings(APITest):

    """Test settings handling."""

    def test_commandline(self):
        """Configuration using commandline."""
        output = execute(['--url', 'https://example.net/', 'list-projects'])
        self.assertIn('Hello', output)

    def test_stdout(self):
        """Configuration using params."""
        output = execute(['list-projects'], stdout=True)
        self.assertIn('Hello', output)

    def test_settings(self):
        """Configuration using settings param."""
        output = execute(
            ['list-projects'],
            settings=(('weblate', 'url', 'https://example.net/'),)
        )
        self.assertIn('Hello', output)

    def test_config(self):
        """Configuration using custom config file."""
        output = execute(['--config', TEST_CONFIG, 'list-projects'], settings=False)
        self.assertIn('Hello', output)

    def test_config_section(self):
        """Configuration using custom config file section."""
        output = execute(
            [
                '--config', TEST_SECTION,
                '--config-section', 'custom',
                'list-projects'
            ],
            settings=False
        )
        self.assertIn('Hello', output)

    def test_config_cwd(self):
        """Test loading settings from current dir"""
        current = os.path.abspath('.')
        try:
            os.chdir(os.path.join(os.path.dirname(__file__), 'test_data'))
            output = execute(['show'], settings=False)
            self.assertIn('Weblate', output)
        finally:
            os.chdir(current)

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


class TestOutput(APITest):

    """Test output formatting."""

    def test_version_text(self):
        """Test version printing."""
        output = execute(['--format', 'text', 'version'])
        self.assertIn('version: {0}'.format(wlc.__version__), output)

    def test_version_json(self):
        """Test version printing."""
        output = execute(['--format', 'json', 'version'])
        values = json.loads(output)
        self.assertEqual({'version': wlc.__version__}, values)

    def test_version_csv(self):
        """Test version printing."""
        output = execute(['--format', 'csv', 'version'])
        self.assertIn('version,{0}'.format(wlc.__version__), output)

    def test_version_html(self):
        """Test version printing."""
        output = execute(['--format', 'html', 'version'])
        self.assertIn(wlc.__version__, output)

    def test_projects_text(self):
        """Test projects printing."""
        output = execute(['--format', 'text', 'list-projects'])
        self.assertIn('name: {0}'.format('Hello'), output)

    def test_projects_json(self):
        """Test projects printing."""
        output = execute(['--format', 'json', 'list-projects'])
        values = json.loads(output)
        self.assertEqual(2, len(values))

    def test_projects_csv(self):
        """Test projects printing."""
        output = execute(['--format', 'csv', 'list-projects'])
        self.assertIn('Hello', output)

    def test_projects_html(self):
        """Test projects printing."""
        output = execute(['--format', 'html', 'list-projects'])
        self.assertIn('Hello', output)


class TestCommands(APITest):
    def test_version_bare(self):
        """Test version printing."""
        output = execute(['version', '--bare'])
        self.assertEqual('{0}\n'.format(wlc.__version__), output)

    def test_ls(self):
        """Project listing."""
        output = execute(['ls'])
        self.assertIn('Hello', output)
        output = execute(['ls', 'hello'])
        self.assertIn('Weblate', output)

    def test_list_languages(self):
        """Language listing."""
        output = execute(
            [
                'list-languages'
            ],
        )
        self.assertIn('Turkish', output)

    def test_list_projects(self):
        """Project listing."""
        output = execute(
            [
                'list-projects'
            ],
        )
        self.assertIn('Hello', output)

    def test_list_components(self):
        """Project listing."""
        output = execute(
            [
                'list-components'
            ],
        )
        self.assertIn('/hello/weblate', output)

    def test_list_translations(self):
        """Project listing."""
        output = execute(
            [
                'list-translations'
            ],
        )
        self.assertIn('/hello/weblate/cs/', output)

    def test_show(self):
        """Project show."""
        output = execute(['show', 'hello'])
        self.assertIn('Hello', output)

        output = execute(['show', 'hello/weblate'])
        self.assertIn('Weblate', output)

        output = execute(['show', 'hello/weblate/cs'])
        self.assertIn('/hello/weblate/cs/', output)

    def test_commit(self):
        """Project commit."""
        output = execute(['commit', 'hello'])
        self.assertEqual('', output)

        output = execute(['commit', 'hello/weblate'])
        self.assertEqual('', output)

        output = execute(['commit', 'hello/weblate/cs'])
        self.assertEqual('', output)

    def test_push(self):
        """Project push."""
        msg = (
            'Error: Failed to push changes!\n'
            'Push is disabled for Hello/Weblate.\n'
        )
        output = execute(['push', 'hello'], expected=1)
        self.assertEqual(msg, output)

        output = execute(['push', 'hello/weblate'], expected=1)
        self.assertEqual(msg, output)

        output = execute(['push', 'hello/weblate/cs'], expected=1)
        self.assertEqual(msg, output)

    def test_pull(self):
        """Project pull."""
        output = execute(['pull', 'hello'])
        self.assertEqual('', output)

        output = execute(['pull', 'hello/weblate'])
        self.assertEqual('', output)

        output = execute(['pull', 'hello/weblate/cs'])
        self.assertEqual('', output)

    def test_repo(self):
        """Project repo."""
        output = execute(['repo', 'hello'])
        self.assertIn('needs_commit', output)

        output = execute(['repo', 'hello/weblate'])
        self.assertIn('needs_commit', output)

        output = execute(['repo', 'hello/weblate/cs'])
        self.assertIn('needs_commit', output)

    def test_stats(self):
        """Project stats."""
        output = execute(['stats', 'hello'], expected=1)
        self.assertIn('Not supported', output)

        output = execute(['stats', 'hello/weblate'])
        self.assertIn('failing_percent', output)

        output = execute(['stats', 'hello/weblate/cs'])
        self.assertIn('failing_percent', output)
