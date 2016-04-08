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
from __future__ import print_function
from __future__ import unicode_literals

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
        default='wlc',
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


def key_value(value):
    """Validate key=value parameter."""
    if '=' not in value:
        raise ValueError('Please specify --param as key=value')
    return value


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

    @staticmethod
    def add_list_option(parser):
        """Add argparse argument --list."""
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all records (instead of printing summary)'
        )

    @staticmethod
    def add_line_option(parser):
        """Add argparse argument --line."""
        parser.add_argument(
            '--line',
            help='Line to use for listing'
        )

    def resolve(self, kind, value):
        """Resolve line/phone number from configuration."""
        if value is None:
            return None
        if value.isdigit():
            return value
        try:
            return self.config.get(kind, value)
        except NoOptionError:
            raise CommandError(
                'Invalid value for {0}: {1}'.format(kind, value)
            )

    @staticmethod
    def summary(values, fields):
        """Calculate summary of values."""
        result = {}
        for field in fields:
            result[field] = 0
        for value in values:
            for field in fields:
                result[field] += value[field]
        return result

    @staticmethod
    def summary_group(values, fields, group, groups):
        """Calculate summary of values groupped by attribute."""
        result = {}
        for field in fields:
            for group_name in groups:
                result['{0}_{1}'.format(field, group_name)] = 0

        for value in values:
            group_name = value[group]
            for field in fields:
                result['{0}_{1}'.format(field, group_name)] += value[field]
        return result

    @classmethod
    def calls_summary(cls, calls):
        """Wrapper for getting calls summary."""
        result = cls.summary(calls, ('price', 'length'))
        result.update(
            cls.summary_group(
                calls, ('length',), 'direction', ('in', 'out', 'redirected')
            )
        )
        result['count'] = len(calls)
        result['count_in'] = cls.count_direction(calls, 'in')
        result['count_out'] = cls.count_direction(calls, 'out')
        return result

    @classmethod
    def sms_summary(cls, messages):
        """Wrapper for getting sms summary."""
        result = cls.summary(messages, ('price',))
        result['count'] = len(messages)
        result['count_in'] = cls.count_direction(messages, 'in')
        result['count_out'] = cls.count_direction(messages, 'out')
        return result

    @classmethod
    def data_summary(cls, data_usage):
        """Wrapper for getting data summary."""
        return cls.summary(
            data_usage,
            ('bytes_total', 'bytes_down', 'bytes_up', 'price')
        )

    @staticmethod
    def count_direction(values, direction):
        """Counts items with matching direction"""
        return len(
            [value for value in values if value['direction'] == direction]
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

    @classmethod
    def format_csv_value(cls, value):
        """Format value for rendering in CSV."""
        value = cls.format_value(value)
        if sys.version_info < (3, 0):
            return value.encode('utf-8')
        return value

    def print_csv(self, value, header):
        """CSV print."""
        if header is not None:
            writer = csv.DictWriter(self.stdout, header)
            writer.writeheader()
            for row in value:
                writer.writerow(
                    {k: self.format_csv_value(v) for k, v in row.items()}
                )
        elif isinstance(list(value.items())[0][1], dict):
            for key, data in sorted_items(value):
                self.println(self.format_csv_value(key))
                self.print_csv(data, None)
                self.println(self.format_csv_value(''))
        else:
            writer = csv.writer(self.stdout)
            for key, data in sorted_items(value):
                writer.writerow((key, self.format_csv_value(data)))

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
        elif isinstance(list(value.items())[0][1], dict):
            for key, data in sorted_items(value):
                self.println('<h1>{0}</h1>'.format(key))
                self.print_html(data, None)
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
        elif isinstance(list(value.items())[0][1], dict):
            for key, data in sorted_items(value):
                self.println(key)
                self.print_text(data, None)
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
    description = "Lists all projects"""

    def run(self):
        """Main execution of the command."""
        self.print(self.wlc.list_projects())


@register_command
class ListComponents(Command):
    """Lists components."""

    name = 'list-components'
    description = "Lists all components"""

    def run(self):
        """Main execution of the command."""
        self.print(self.wlc.list_components())


@register_command
class ListLanguages(Command):
    """Lists languages."""

    name = 'list-languages'
    description = "Lists all languages"""

    def run(self):
        """Main execution of the command."""
        self.print(self.wlc.list_languages())


@register_command
class ListTranslations(Command):
    """Lists translations."""

    name = 'list-translations'
    description = "Lists all translations"""

    def run(self):
        """Main execution of the command."""
        self.print(self.wlc.list_translations())


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
    except (CommandError, wlc.WeblateException) as error:
        print('Error: {0}'.format(error), file=sys.stderr)
        sys.exit(1)
