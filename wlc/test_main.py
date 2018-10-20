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
"""Test command line interface."""

from io import StringIO, BytesIO, TextIOWrapper
import json
import sys
from tempfile import NamedTemporaryFile
import os

import wlc
from wlc.main import main
from wlc.config import WeblateConfig
from .test_base import APITest

TEST_CONFIG = os.path.join(os.path.dirname(__file__), 'test_data', 'wlc')
TEST_SECTION = os.path.join(os.path.dirname(__file__), 'test_data', 'section')


def execute(args, settings=None, stdout=None, stdin=None, expected=0):
    """Execute command and return output."""
    if settings is None:
        settings = ()
    elif not settings:
        settings = None
    output = StringIO()
    output.buffer = BytesIO()
    backup = sys.stdout
    backup_err = sys.stderr
    try:
        sys.stdout = output
        sys.stderr = output
        if stdout:
            stdout = output
        result = main(args=args, settings=settings, stdout=stdout, stdin=stdin)
        assert result == expected
    finally:
        sys.stdout = backup
        sys.stderr = backup_err
    result = output.buffer.getvalue()
    if not result:
        result = output.getvalue()
    return result


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

    def test_debug(self):
        """Debug mode."""
        output = execute(['--debug', 'list-projects'], stdout=True)
        self.assertIn('application/json', output)

    def test_settings(self):
        """Configuration using settings param."""
        output = execute(
            ['list-projects'],
            settings=(('weblate', 'url', 'https://example.net/'),)
        )
        self.assertIn('Hello', output)

    def test_config(self):
        """Configuration using custom config file."""
        output = execute(
            ['--config', TEST_CONFIG, 'list-projects'], settings=False
        )
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

    def test_config_key(self):
        """Configuration using custom config file section and key set."""
        output = execute(
            [
                '--config', TEST_CONFIG,
                '--config-section', 'withkey',
                'show', 'acl'
            ],
            settings=False
        )
        self.assertIn('ACL', output)

    def test_config_cwd(self):
        """Test loading settings from current dir."""
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

    """Individual command tests."""

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
        output = execute(['ls', 'empty'])
        self.assertEqual('', output)

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

    def test_reset(self):
        """Project reset."""
        output = execute(['reset', 'hello'])
        self.assertEqual('', output)

        output = execute(['reset', 'hello/weblate'])
        self.assertEqual('', output)

        output = execute(['reset', 'hello/weblate/cs'])
        self.assertEqual('', output)

    def test_cleanup(self):
        """Project cleanup."""
        output = execute(['cleanup', 'hello'])
        self.assertEqual('', output)

        output = execute(['cleanup', 'hello/weblate'])
        self.assertEqual('', output)

        output = execute(['cleanup', 'hello/weblate/cs'])
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
        output = execute(['stats', 'hello'])
        self.assertIn('translated_percent', output)

        output = execute(['stats', 'hello/weblate'])
        self.assertIn('failing_percent', output)

        output = execute(['stats', 'hello/weblate/cs'])
        self.assertIn('failing_percent', output)

    def test_locks(self):
        """Project locks."""
        output = execute(['lock-status', 'hello'], expected=1)
        self.assertIn('Not supported', output)

        output = execute(['lock-status', 'hello/weblate'])
        self.assertIn('locked', output)
        output = execute(['lock', 'hello/weblate'])
        self.assertEqual('', output)
        output = execute(['unlock', 'hello/weblate'])
        self.assertEqual('', output)

        output = execute(['lock-status', 'hello/weblate/cs'], expected=1)
        self.assertIn('Not supported', output)

    def test_changes(self):
        """Project changes."""
        output = execute(['changes', 'hello'])
        self.assertIn('action_name', output)

        output = execute(['changes', 'hello/weblate'])
        self.assertIn('action_name', output)

        output = execute(['changes', 'hello/weblate/cs'])
        self.assertIn('action_name', output)

    def test_download(self):
        """Translation file downloads."""
        output = execute(['download', 'hello/weblate/cs'])
        self.assertIn(b'Plural-Forms:', output)

        output = execute(['download', 'hello/weblate/cs', '--convert', 'csv'])
        self.assertIn(b'"location"', output)

        with NamedTemporaryFile() as handle:
            handle.close()
            execute(['download', 'hello/weblate/cs', '-o', handle.name])
            with open(handle.name, 'rb') as tmp:
                output = tmp.read()
            self.assertIn(b'Plural-Forms:', output)

        output = execute(['download', 'hello/weblate'], expected=1)
        self.assertIn('Not supported', output)

    def test_upload(self):
        """Translation file uploads."""
        msg = (
            'Error: Failed to upload translations!\n\n'
        )

        with self.get_text_io_wrapper("test upload data") as stdin:
            output = execute(['upload', 'hello/weblate/cs'], stdin=stdin)
            self.assertEqual('', output)

        with self.get_text_io_wrapper("wrong upload data") as stdin:
            output = execute(['upload', 'hello/weblate/cs'],
                             stdin=stdin,
                             expected=1)
            self.assertEqual(msg, output)

        with NamedTemporaryFile(delete=False) as handle:
            handle.write('test upload overwrite'.encode())
            handle.close()
            output = execute([
                'upload',
                'hello/weblate/cs',
                '-i',
                handle.name,
                '--overwrite'
            ])
            self.assertEqual('', output)

    def get_text_io_wrapper(self, string):
        """Create a text io wrapper from a string."""
        return TextIOWrapper(BytesIO(string.encode()), "utf8")
