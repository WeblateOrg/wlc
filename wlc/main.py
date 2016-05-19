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
"""Command line interface for Weblate."""
import sys
import json
import csv
from argparse import ArgumentParser

import wlc
from wlc.config import WeblateConfig, NoOptionError


COMMANDS = {}

SORT_ORDER = [
]


def register_command(command):
    """Decorator to register command in command line interface."""
    COMMANDS[command.name] = command
    return command


def get_parser():
    """Create argument parser."""
    parser = ArgumentParser(
        description='Weblate <{0}> command line utility.'.format(wlc.URL),
        epilog='This utility is developed at <{0}>.'.format(wlc.DEVEL_URL),
    )
    parser.add_argument(
        '--format', '-f',
        default='text',
        choices=('text', 'csv', 'json', 'html'),
        help='Output format to use'
    )
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='wlc {0}'.format(wlc.__version__)
    )
    parser.add_argument(
        '--config', '-c',
        help='Path to configuration file',
    )
    parser.add_argument(
        '--config-section', '-s',
        default='weblate',
        help='Configuration section to use'
    )
    parser.add_argument(
        '--key', '-k',
        help='API key',
    )
    parser.add_argument(
        '--url', '-u',
        help='API URL',
    )
    subparser = parser.add_subparsers(dest="cmd")

    for command in COMMANDS:
        COMMANDS[command].add_parser(subparser)

    return parser


class CommandError(Exception):
    """Generic error from command line."""
    def __init__(self, message, detail=None):
        if detail is not None:
            message = '\n'.join((message, detail))
        super(CommandError, self).__init__(message)


def sort_key(value):
    """Key getter for sorting."""
    try:
        return '{0:02d}'.format(SORT_ORDER.index(value))
    except ValueError:
        return value


def sorted_items(value):
    """Sorted items iterator."""
    for key in sorted(value.keys(), key=sort_key):
        yield key, value[key]


class Command(object):

    """Basic command object."""

    name = ''
    description = ''

    def __init__(self, args, config, stdout=None):
        """Construct Command object."""
        self.args = args
        self.config = config
        if stdout is None:
            self.stdout = sys.stdout
        else:
            self.stdout = stdout
        self.wlc = wlc.Weblate(config=config)

    @classmethod
    def add_parser(cls, subparser):
        """Create parser for command line."""
        return subparser.add_parser(
            cls.name, description=cls.description
        )

    def println(self, line):
        """Print single line to output."""
        print(line, file=self.stdout)

    def print_json(self, value):
        """JSON print."""
        json.dump(value, self.stdout, indent=2)

    @staticmethod
    def format_value(value):
        """Format value for rendering."""
        if isinstance(value, float):
            return '{0:.1f}'.format(value)
        elif isinstance(value, int):
            return '{0}'.format(value)
        elif value is None:
            return ''
        elif hasattr(value, 'to_value'):
            return value.to_value()
        return value

    def print_csv(self, value, header):
        """CSV print."""
        if header is not None:
            writer = csv.DictWriter(self.stdout, header)
            writer.writeheader()
            for row in value:
                writer.writerow(
                    {k: self.format_value(v) for k, v in row.items()}
                )
        else:
            writer = csv.writer(self.stdout)
            for key, data in sorted_items(value):
                writer.writerow((key, self.format_value(data)))

    def print_html(self, value, header):
        """HTML print."""
        if header is not None:
            self.println('<table>')
            self.println('  <thead>')
            self.println('    <tr>')
            for key in header:
                self.println('      <th>{0}</th>'.format(key))
            self.println('    </tr>')
            self.println('  </thead>')
            self.println('  <tbody>')

            for item in value:
                self.println('    <tr>')
                for key in header:
                    self.println('      <td>{0}</td>'.format(
                        self.format_value(getattr(item, key))
                    ))
                self.println('    </tr>')
            self.println('  </tbody>')
            self.println('</table>')
        else:
            self.println('<table>')
            for key, data in sorted_items(value):
                self.println('  <tr>')
                self.println('    <th>{0}</th><td>{1}</td>'.format(
                    key, self.format_value(data)
                ))
                self.println('  </tr>')
            self.println('</table>')

    def print_text(self, value, header):
        """Text print."""
        if header is not None:
            for item in value:
                for key in header:
                    self.println('{0}: {1}'.format(
                        key, self.format_value(getattr(item, key))
                    ))
                self.println('')
        else:
            for key, data in sorted_items(value):
                self.println('{0}: {1}'.format(
                    key, self.format_value(data)
                ))

    def print(self, value):
        """Print value."""
        header = None
        if isinstance(value, list):
            if len(value) == 0:
                return
            header = sorted(value[0].keys(), key=sort_key)

        if self.args.format == 'json':
            self.print_json(value)
        elif self.args.format == 'csv':
            self.print_csv(value, header)
        elif self.args.format == 'html':
            self.print_html(value, header)
        else:
            self.print_text(value, header)

    def run(self):
        """Main execution of the command."""
        raise NotImplementedError


class ObjectCommand(Command):
    """Command to require path to object"""

    @classmethod
    def add_parser(cls, subparser):
        """Create parser for command line."""
        parser = super(ObjectCommand, cls).add_parser(subparser)
        parser.add_argument(
            'object',
            nargs='*',
            help=(
                'Object on which we should operate '
                '(project, component or translation)'
            )
        )
        return parser

    def get_object(self):
        """Returns object"""
        if self.args.object:
            path = self.args.object[0]
        else:
            try:
                path = self.config.get(self.config.section, 'translation')
            except NoOptionError:
                path = None

        if not path:
            raise CommandError('No object passed on command line!')

        return self.wlc.get_object(path)

    def run(self):
        """Main execution of the command."""
        raise NotImplementedError


@register_command
class Version(Command):

    """Print version."""

    name = 'version'
    description = "Prints program version"

    @classmethod
    def add_parser(cls, subparser):
        """Create parser for command line."""
        parser = super(Version, cls).add_parser(subparser)
        parser.add_argument(
            '--bare',
            action='store_true',
            help='Print only version'
        )
        return parser

    def run(self):
        """Main execution of the command."""
        if self.args.bare:
            self.println(wlc.__version__)
        else:
            self.print({'version': wlc.__version__})


@register_command
class ListProjects(Command):
    """Lists projects."""

    name = 'list-projects'
    description = "Lists all projects"

    def run(self):
        """Main execution of the command."""
        self.print(list(self.wlc.list_projects()))


@register_command
class ListComponents(Command):
    """Lists components."""

    name = 'list-components'
    description = "Lists all components"

    def run(self):
        """Main execution of the command."""
        self.print(list(self.wlc.list_components()))


@register_command
class ListLanguages(Command):
    """Lists languages."""

    name = 'list-languages'
    description = "Lists all languages"

    def run(self):
        """Main execution of the command."""
        self.print(list(self.wlc.list_languages()))


@register_command
class ListTranslations(Command):
    """Lists translations."""

    name = 'list-translations'
    description = "Lists all translations"

    def run(self):
        """Main execution of the command."""
        self.print(list(self.wlc.list_translations()))


@register_command
class ShowObject(ObjectCommand):
    """Shows object"""

    name = 'show'
    description = "Shows translation, component or project"

    def run(self):
        """Executor"""
        self.print(self.get_object())


@register_command
class ListObject(ObjectCommand):
    """Lists object"""

    name = 'ls'
    description = "List content of translation, component or project"

    def run(self):
        """Executor"""
        try:
            obj = self.get_object()
            self.print(list(obj.list()))
        except CommandError:
            # Called without params
            lsproj = ListProjects(self.args, self.config, self.stdout)
            lsproj.run()


@register_command
class CommitObject(ObjectCommand):
    """Commits object"""

    name = 'commit'
    description = "Commits changes in translation, component or project"

    def run(self):
        """Executor"""
        obj = self.get_object()
        result = obj.commit()
        if not result['result']:
            raise CommandError(
                'Failed to commit changes!',
                result['detail'],
            )


@register_command
class PushObject(ObjectCommand):
    """Pushes object"""

    name = 'push'
    description = (
        "Pushes changes from Weblate to repository "
        "in translation, component or project from Weblate"
    )

    def run(self):
        """Executor"""
        obj = self.get_object()
        result = obj.push()
        if not result['result']:
            raise CommandError(
                'Failed to push changes!',
                result['detail'],
            )


@register_command
class PullObject(ObjectCommand):
    """Pulls object"""

    name = 'pull'
    description = (
        "Pulls changes to Weblate from repository "
        "in translation, component or project"
    )

    def run(self):
        """Executor"""
        obj = self.get_object()
        result = obj.pull()
        if not result['result']:
            raise CommandError(
                'Failed to pull changes!',
                result['detail'],
            )


@register_command
class RepoObject(ObjectCommand):
    """Displays repository status for object"""

    name = 'repo'
    description = (
        "Displays status of Weblate repository "
        "for translation, component or project"
    )

    def run(self):
        """Executor"""
        obj = self.get_object()
        self.print(obj.repository())


@register_command
class StatsObject(ObjectCommand):
    """Displays repository statistics for object"""

    name = 'stats'
    description = (
        "Displays statistics "
        "for translation, component or project"
    )

    def run(self):
        """Executor"""
        obj = self.get_object()
        if isinstance(obj, wlc.Project):
            raise CommandError('Not supported')
        elif isinstance(obj, wlc.Component):
            self.print(list(obj.statistics()))
        else:
            self.print(obj.statistics())


def main(settings=None, stdout=None, args=None):
    """Execution entry point."""
    parser = get_parser()
    if args is None:
        args = sys.argv[1:]
    args = parser.parse_args(args)

    config = WeblateConfig(args.config_section)
    if settings is None:
        config.load(args.config)
    else:
        for section, key, value in settings:
            config.set(section, key, value)

    for override in ('key', 'url'):
        value = getattr(args, override)
        if value is not None:
            config.set(args.config_section, override, value)

    command = COMMANDS[args.cmd](args, config, stdout)
    try:
        command.run()
        return 0
    except (CommandError, wlc.WeblateException) as error:
        print('Error: {0}'.format(error), file=sys.stderr)
        return 1
