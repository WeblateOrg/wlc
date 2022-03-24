# PYTHON_ARGCOMPLETE_OK
#
# Copyright © 2012–2022 Michal Čihař <michal@cihar.com>
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Command-line interface for Weblate."""
import csv
import http.client
import json
import logging
import sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List

import argcomplete
from requests.exceptions import RequestException

import wlc
from wlc.config import NoOptionError, WeblateConfig

COMMANDS: Dict[str, Callable] = {}

SORT_ORDER: List[str] = []


def register_command(command):
    """Register command decorator in the command-line interface."""
    COMMANDS[command.name] = command
    return command


def get_parser():
    """Create argument parser."""
    parser = ArgumentParser(
        description=f"Weblate <{wlc.URL}> command-line utility.",
        epilog=f"This utility is developed at <{wlc.DEVEL_URL}>.",
    )
    parser.add_argument(
        "--format",
        "-f",
        default="text",
        choices=("text", "csv", "json", "html"),
        help="Output format to use",
    )
    parser.add_argument(
        "--version", "-v", action="version", version=f"wlc {wlc.__version__}"
    )
    parser.add_argument(
        "--debug", "-D", action="store_true", help="Print verbosely http communication"
    )
    parser.add_argument("--config", "-c", help="Path to configuration file")
    parser.add_argument(
        "--config-section", "-s", default="weblate", help="Configuration section to use"
    )
    parser.add_argument("--key", "-k", help="API key")
    parser.add_argument("--url", "-u", help="API URL")
    subparser = parser.add_subparsers(
        title="Command",
        description="""
Specifies what action to perform.
Invoke with --help to get more detailed help.
    """,
        dest="command",
    )
    subparser.required = True

    for command in COMMANDS.values():
        command.add_parser(subparser)

    argcomplete.autocomplete(parser)

    return parser


class CommandError(Exception):
    """Generic error from command-line."""

    def __init__(self, message, detail=None):
        """Create CommandError exception."""
        if detail is not None:
            message = "\n".join((message, detail))
        super().__init__(message)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()

        return super().default(o)


def sort_key(value):
    """Key getter for sorting."""
    try:
        return f"{SORT_ORDER.index(value):02d}"
    except ValueError:
        return value


def sorted_items(value):
    """Sorted items iterator."""
    for key in sorted(value.keys(), key=sort_key):
        yield key, value[key]


class Command:
    """Basic command object."""

    name = ""
    description = ""

    def __init__(self, args, config, stdout=None, stdin=None):
        """Construct Command object."""
        self.args = args
        self.config = config
        if stdout is None:
            self.stdout = sys.stdout
        else:
            self.stdout = stdout

        if stdin is None:
            self.stdin = sys.stdin
        else:
            self.stdin = stdin

        self.wlc = wlc.Weblate(config=config)

    @classmethod
    def add_parser(cls, subparser):
        """Create parser for command-line."""
        return subparser.add_parser(cls.name, description=cls.description)

    def println(self, line):
        """Print single line to output."""
        print(line, file=self.stdout)

    def print_json(self, value):
        """JSON print."""
        json.dump(value, self.stdout, cls=DateTimeEncoder, indent=2)

    @staticmethod
    def format_value(value):
        """Format value for rendering."""
        if isinstance(value, float):
            return f"{value:.1f}"
        if isinstance(value, int):
            return f"{value}"
        if value is None:
            return ""
        if hasattr(value, "to_value"):
            return value.to_value()
        return value

    def print_csv(self, value, header):
        """CSV print."""
        if header is not None:
            writer = csv.DictWriter(self.stdout, header)
            writer.writeheader()
            for row in value:
                writer.writerow({k: self.format_value(v) for k, v in row.items()})
        else:
            writer = csv.writer(self.stdout)
            for key, data in sorted_items(value):
                writer.writerow((key, self.format_value(data)))

    def print_html(self, value, header):
        """HTML print."""
        if header is not None:
            self.println("<table>")
            self.println("  <thead>")
            self.println("    <tr>")
            for key in header:
                self.println(f"      <th>{key}</th>")
            self.println("    </tr>")
            self.println("  </thead>")
            self.println("  <tbody>")

            for item in value:
                self.println("    <tr>")
                for key in header:
                    self.println(
                        "      <td>{}</td>".format(
                            self.format_value(getattr(item, key))
                        )
                    )
                self.println("    </tr>")
            self.println("  </tbody>")
            self.println("</table>")
        else:
            self.println("<table>")
            for key, data in sorted_items(value):
                self.println("  <tr>")
                self.println(f"    <th>{key}</th><td>{self.format_value(data)}</td>")
                self.println("  </tr>")
            self.println("</table>")

    def print_text(self, value, header):
        """Text print."""
        if header is not None:
            for item in value:
                for key in header:
                    self.println(f"{key}: {self.format_value(getattr(item, key))}")
                self.println("")
        else:
            for key, data in sorted_items(value):
                self.println(f"{key}: {self.format_value(data)}")

    def print(self, value):
        """Print value."""
        header = None
        if isinstance(value, list):
            if len(value) == 0:
                return
            header = sorted(value[0].keys(), key=sort_key)

        if self.args.format == "json":
            self.print_json(value)
        elif self.args.format == "csv":
            self.print_csv(value, header)
        elif self.args.format == "html":
            self.print_html(value, header)
        else:
            self.print_text(value, header)

    def run(self):
        """Main execution of the command."""
        raise NotImplementedError()


class ObjectCommand(Command):
    """Command to require path to object."""

    @classmethod
    def add_parser(cls, subparser):
        """Create parser for command-line."""
        parser = super().add_parser(subparser)
        parser.add_argument(
            "object",
            nargs="*",
            help=(
                "Object on which we should operate "
                "(project, component or translation)"
            ),
        )
        return parser

    def get_object(self, blank: bool = False):
        """Return object."""
        if self.args.object:
            path = self.args.object[0]
        else:
            try:
                path = self.config.get(self.config.section, "translation")
            except NoOptionError:
                path = None

        if not path:
            if blank:
                return None
            raise CommandError("No object passed on command-line!")

        return self.wlc.get_object(path)

    def run(self):
        """Main execution of the command."""
        raise NotImplementedError()

    @staticmethod
    def check_result(result, message):
        """Check result json data."""
        if not result["result"]:
            raise CommandError(message, result["detail"] if "detail" in result else "")


class ProjectCommand(ObjectCommand):
    """Wrapper to allow only project objects."""

    def get_object(self, blank: bool = False):
        """Return component object."""
        obj = super().get_object(blank=blank)
        if not isinstance(obj, wlc.Project):
            raise CommandError("Not supported")
        return obj

    def run(self):
        """Main execution of the command."""
        raise NotImplementedError()


class ComponentCommand(ObjectCommand):
    """Wrapper to allow only component objects."""

    def get_object(self, blank: bool = False):
        """Return component object."""
        obj = super().get_object(blank=blank)
        if not isinstance(obj, wlc.Component):
            raise CommandError("This command is supported only at component level")
        return obj

    def run(self):
        """Main execution of the command."""
        raise NotImplementedError()


class TranslationCommand(ObjectCommand):
    """Wrapper to allow only translation objects."""

    def get_object(self, blank: bool = False):
        """Return translation object."""
        obj = super().get_object(blank=blank)
        if not isinstance(obj, wlc.Translation):
            raise CommandError("This command is supported only at translation level")
        return obj

    def run(self):
        """Main execution of the command."""
        raise NotImplementedError()


@register_command
class Version(Command):
    """Print version."""

    name = "version"
    description = "Prints program version"

    @classmethod
    def add_parser(cls, subparser):
        """Create parser for command-line."""
        parser = super().add_parser(subparser)
        parser.add_argument("--bare", action="store_true", help="Print only version")
        return parser

    def run(self):
        """Main execution of the command."""
        if self.args.bare:
            self.println(wlc.__version__)
        else:
            self.print({"version": wlc.__version__})


@register_command
class ListProjects(Command):
    """List projects."""

    name = "list-projects"
    description = "Lists all projects"

    def run(self):
        """Main execution of the command."""
        self.print(list(self.wlc.list_projects()))


@register_command
class ListComponents(ProjectCommand):
    """List components."""

    name = "list-components"
    description = "Lists all components (optionally per project)"

    def run(self):
        """Main execution of the command."""
        if self.args.object:
            obj = self.get_object()

            component_list = list(obj.list())
            for component in component_list:
                component.setattrvalue("project", obj)

            self.print(component_list)
        else:
            self.print(list(self.wlc.list_components()))


@register_command
class ListLanguages(Command):
    """List languages."""

    name = "list-languages"
    description = "Lists all languages"

    def run(self):
        """Main execution of the command."""
        self.print(list(self.wlc.list_languages()))


@register_command
class ListTranslations(ComponentCommand):
    """List translations."""

    name = "list-translations"
    description = "Lists all translations (optionally per component)"

    def run(self):
        """Main execution of the command."""
        if self.args.object:
            obj = self.get_object()

            translation_list = list(obj.list())
            for translation in translation_list:
                translation.setattrvalue("component", obj)

            self.print(translation_list)
        else:
            self.print(list(self.wlc.list_translations()))


@register_command
class Show(ObjectCommand):
    """Show object."""

    name = "show"
    description = "Shows translation, component or project"

    def run(self):
        """Executor."""
        self.print(self.get_object())


@register_command
class Delete(ObjectCommand):
    """Delete object."""

    name = "delete"
    description = "Delete translation, component or project"

    def run(self):
        """Executor."""
        self.get_object().delete()


@register_command
class ListObjects(ObjectCommand):
    """List object."""

    name = "ls"
    description = "List content of translation, component or project"

    def run(self):
        """Executor."""
        obj = self.get_object(blank=True)
        if obj:
            self.print(list(obj.list()))
        else:
            # Called without params
            lsproj = ListProjects(self.args, self.config, self.stdout)
            lsproj.run()


@register_command
class Commit(ObjectCommand):
    """Commit object."""

    name = "commit"
    description = "Commits changes in translation, component or project"

    def run(self):
        """Executor."""
        obj = self.get_object()
        result = obj.commit()
        self.check_result(result, "Failed to commit changes!")


@register_command
class Push(ObjectCommand):
    """Push object."""

    name = "push"
    description = (
        "Pushes changes from Weblate to repository "
        "in translation, component or project from Weblate"
    )

    def run(self):
        """Executor."""
        obj = self.get_object()
        result = obj.push()
        self.check_result(result, "Failed to push changes!")


@register_command
class Pull(ObjectCommand):
    """Pull object."""

    name = "pull"
    description = (
        "Pulls changes to Weblate from repository "
        "in translation, component or project"
    )

    def run(self):
        """Executor."""
        obj = self.get_object()
        result = obj.pull()
        self.check_result(result, "Failed to pull changes!")


@register_command
class Reset(ObjectCommand):
    """Reset object."""

    name = "reset"
    description = (
        "Resets all changes in Weblate repository to upstream "
        "in translation, component or project"
    )

    def run(self):
        """Executor."""
        obj = self.get_object()
        result = obj.reset()
        self.check_result(result, "Failed to reset changes!")


@register_command
class Cleanup(ObjectCommand):
    """Cleanup object."""

    name = "cleanup"
    description = (
        "Cleanups all untracked changes in Weblate repository "
        "in translation, component or project"
    )

    def run(self):
        """Executor."""
        obj = self.get_object()
        result = obj.cleanup()
        self.check_result(result, "Failed to cleanup changes!")


@register_command
class Repo(ObjectCommand):
    """Display repository status for object."""

    name = "repo"
    description = (
        "Displays status of Weblate repository " "for translation, component or project"
    )

    def run(self):
        """Executor."""
        obj = self.get_object()
        self.print(obj.repository())


@register_command
class Changes(ObjectCommand):
    """Display repository status for object."""

    name = "changes"
    description = "Displays list of changes " "for translation, component or project"

    def run(self):
        """Executor."""
        obj = self.get_object()
        self.print(list(obj.changes()))


@register_command
class Stats(ObjectCommand):
    """Display repository statistics for object."""

    name = "stats"
    description = "Displays statistics " "for translation, component or project"

    def run(self):
        """Executor."""
        obj = self.get_object()
        if isinstance(obj, wlc.Project):
            self.print(obj.statistics())
        elif isinstance(obj, wlc.Component):
            self.print(list(obj.statistics()))
        else:
            self.print(obj.statistics())


@register_command
class LockStatus(ComponentCommand):
    """Show lock status."""

    name = "lock-status"
    description = "Shows component lock status"

    def run(self):
        """Executor."""
        obj = self.get_object()
        self.print(obj.lock_status())


@register_command
class Lock(ComponentCommand):
    """Lock component for transaltion."""

    name = "lock"
    description = "Locks componets from translations"

    def run(self):
        """Executor."""
        obj = self.get_object()
        obj.lock()


@register_command
class Unlock(ComponentCommand):
    """Unock component for transaltion."""

    name = "unlock"
    description = "Unlocks componets from translations"

    def run(self):
        """Executor."""
        obj = self.get_object()
        obj.unlock()


@register_command
class Download(ObjectCommand):
    """Downloads translation file."""

    name = "download"
    description = """
    Downloads translation file for a project, a component or a file
    For a project or a component we will download a zip to --output
    """

    @classmethod
    def add_parser(cls, subparser):
        """Create parser for command-line."""
        parser = super().add_parser(subparser)
        parser.add_argument(
            "-c", "--convert", help="Convert file format on server (defaults to none)"
        )
        parser.add_argument(
            "-o",
            "--output",
            help="File|Directory where to store output (defaults to stdout)",
        )
        parser.add_argument(
            "-g",
            "--no-glossary",
            action="store_true",
            default=False,
            help="Disable download glossary (defaults to False)",
        )
        return parser

    def download_component(self, component):
        """Download a single component as file (if not a translation)."""
        content = component.download(self.args.convert)
        if self.args.output is None:
            raise CommandError("Output is needed for download!")

        directory = Path(self.args.output)
        file_path = directory.joinpath(f"{component.project.slug}-{component.slug}.zip")

        if not directory.exists():
            directory.mkdir(exist_ok=True, parents=True)

        with open(file_path, "wb") as file:
            file.write(content)

    def download_components(self, iterable):
        for component in iterable:
            # Ignore glossary via --no-glossary
            if getattr(component, "is_glossary", False) and self.args.no_glossary:
                continue
            self.download_component(component)
            item = f"{component.project.slug}/{component.slug}"
            self.println(f"downloaded translations for component: {item}")

    def run(self):
        """Executor."""
        obj = self.get_object(blank=True)

        # Translation locale for a component
        if isinstance(obj, wlc.Translation):
            content = obj.download(self.args.convert)
            if self.args.output and self.args.output != "-":
                with open(self.args.output, "wb") as handle:
                    handle.write(content)
            else:
                self.stdout.buffer.write(content)
            return

        # All translations for a component
        if isinstance(obj, wlc.Component):
            for component in self.wlc.list_components():
                # Only download for the component we scoped
                if obj.slug == component.slug:
                    self.download_component(component)
                    self.println(
                        f"downloaded translations for component: {self.args.object[0]}"
                    )

            return

        # All translations for a project
        if isinstance(obj, wlc.Project):
            self.download_components(obj.list())
            self.println(f"downloaded translations for project: {self.args.object[0]}")
            return

        self.download_components(self.wlc.list_components())


@register_command
class Upload(TranslationCommand):
    """Uploads translation file."""

    name = "upload"
    description = "Uploads translation file"

    @classmethod
    def add_parser(cls, subparser):
        """Create parser for command-line."""
        parser = super().add_parser(subparser)
        parser.add_argument("-i", "--input", help="File to upload (defaults to stdin)")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite existing translations (defaults to none)",
        )
        parser.add_argument(
            "--author-name",
            help="Author name, to override currently authenticated user",
        )
        parser.add_argument(
            "--author-email",
            help="Author e-mail, to override currently authenticated user",
        )
        parser.add_argument(
            "--method",
            choices=(
                "translate",
                "approve",
                "suggest",
                "fuzzy",
                "replace",
                "source",
                "add",
            ),
            default="translate",
        )
        parser.add_argument("--fuzzy", choices=("", "process", "approve"), default="")
        return parser

    def run(self):
        """Executor."""
        obj = self.get_object()

        kwargs = {"overwrite": self.args.overwrite}
        for arg in ("author_name", "author_email", "method", "fuzzy"):
            value = getattr(self.args, arg, None)
            if value:
                kwargs[arg] = value

        if self.args.input and self.args.input != "-":
            with open(self.args.input, "rb") as handle:
                result = obj.upload(handle, **kwargs)
        else:
            result = obj.upload(self.stdin.buffer.read(), **kwargs)

        if not (
            "count" in result
            and "result" in result
            and "total" in result
            and "accepted" in result
            and "not_found" in result
            and "skipped" in result
        ):
            raise CommandError(
                "Failed to upload translations!",
                result["detail"] if "detail" in result else "",
            )


def parse_settings(args, settings):
    """Read settings based on command-line params."""
    config = WeblateConfig(args.config_section)
    if settings is None:
        config.load(args.config)
    else:
        for section, key, value in settings:
            config.set(section, key, value)

    for override in ("key", "url"):
        value = getattr(args, override)
        if value is not None:
            config.set(args.config_section, override, value)

    return config


def main(settings=None, stdout=None, stdin=None, args=None):
    """Execution entry point."""
    parser = get_parser()
    if args is None:
        args = sys.argv[1:]
    args = parser.parse_args(args)

    if args.debug:
        http.client.HTTPConnection.debuglevel = 1
        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

    config = parse_settings(args, settings)

    command = COMMANDS[args.command](args, config, stdout, stdin)
    try:
        command.run()
        return 0
    except wlc.WeblateDeniedError:
        url, key = config.get_url_key()
        if key:
            print(
                f"API key configured for {url} was rejected by server.", file=sys.stderr
            )
        else:
            print(f"Missing API key for {url}.", file=sys.stderr)
            print(
                "The API key can be specified by --key or in the configuration file.",
                file=sys.stderr,
            )
        return 1
    except RequestException as error:
        print(f"Request failed: {error}", file=sys.stderr)
        return 10
    except (CommandError, wlc.WeblateException) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        if args.debug:
            http.client.HTTPConnection.debuglevel = 0
            logging.getLogger().setLevel(logging.DEBUG)
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
