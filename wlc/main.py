# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Command-line interface for Weblate."""

# pylint: disable=too-many-lines

from __future__ import annotations

import csv
import html
import json
import sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

import argcomplete
from requests.exceptions import RequestException

import wlc
from wlc.config import NoOptionError, WeblateConfig, WLCConfigurationError
from wlc.http_debug import disable_debug_logging, enable_debug_logging

from .utils import sanitize_slug

COMMANDS: dict[str, type[Command]] = {}

SORT_ORDER: list[str] = []
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")
CSV_DANGEROUS_LEADING = " \t\r\n"
TERMINAL_CONTROL_REPLACEMENTS = {
    "\a": r"\a",
    "\b": r"\b",
    "\t": r"\t",
    "\n": r"\n",
    "\v": r"\v",
    "\f": r"\f",
    "\r": r"\r",
}


def register_command(command: type[Command]) -> type[Command]:
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

    def __init__(self, message, detail=None) -> None:
        """Create CommandError exception."""
        if detail is not None:
            message = f"{message}\n{detail}"
        super().__init__(message)


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder with datetime support."""

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


def stream_isatty(stream) -> bool:
    """Check whether the given stream is an interactive terminal."""
    isatty = getattr(stream, "isatty", None)
    if callable(isatty):
        return isatty()
    return False


def escape_terminal_text(value: str) -> str:
    """Render terminal control characters visibly instead of executing them."""
    escaped: list[str] = []
    for char in value:
        if char in TERMINAL_CONTROL_REPLACEMENTS:
            escaped.append(TERMINAL_CONTROL_REPLACEMENTS[char])
            continue

        code = ord(char)
        if code == 0x7F or 0x00 <= code < 0x20 or 0x80 <= code < 0xA0:
            escaped.append(f"\\x{code:02x}")
            continue

        escaped.append(char)
    return "".join(escaped)


def format_for_stream(value, stream):
    """Format output for a stream, escaping control characters on terminals."""
    if isinstance(value, str) and stream_isatty(stream):
        return escape_terminal_text(value)
    return value


def print_stderr(message: str) -> None:
    """Print a terminal-safe error message to stderr."""
    print(format_for_stream(message, sys.stderr), file=sys.stderr)


class Command:
    """Basic command object."""

    name = ""
    description = ""

    def __init__(self, args, config, stdout=None, stdin=None) -> None:
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

    def println(self, line) -> None:
        """Print single line to output."""
        print(format_for_stream(line, self.stdout), file=self.stdout)

    def print_json(self, value) -> None:
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

    def format_csv_value(self, value):
        """Format value for CSV output and harden dangerous spreadsheet cells."""
        formatted = self.format_value(value)
        if not isinstance(formatted, str):
            return formatted

        stripped = formatted.lstrip(CSV_DANGEROUS_LEADING)
        if stripped and stripped[0] in CSV_FORMULA_PREFIXES:
            formatted = f"'{formatted}"

        return format_for_stream(formatted, self.stdout)

    def format_output_value(self, value):
        """Format a value for human-readable output."""
        return format_for_stream(self.format_value(value), self.stdout)

    @classmethod
    def format_html_value(cls, value) -> str:
        """Format value for safe HTML rendering."""
        return html.escape(str(cls.format_value(value)), quote=True)

    def print_csv(self, value, header) -> None:
        """CSV print."""
        writer = csv.writer(self.stdout)
        if header is not None:
            writer.writerow([self.format_csv_value(key) for key in header])
            for row in value:
                formatted_row = {
                    key: self.format_csv_value(data) for key, data in row.items()
                }
                writer.writerow([formatted_row.get(key, "") for key in header])
        else:
            for key, data in sorted_items(value):
                writer.writerow(
                    (self.format_csv_value(key), self.format_csv_value(data))
                )

    def print_html(self, value, header) -> None:
        """HTML print."""
        if header is not None:
            self.println("<table>")
            self.println("  <thead>")
            self.println("    <tr>")
            for key in header:
                self.println(f"      <th>{self.format_html_value(key)}</th>")
            self.println("    </tr>")
            self.println("  </thead>")
            self.println("  <tbody>")

            for item in value:
                self.println("    <tr>")
                for key in header:
                    self.println(
                        f"      <td>{self.format_html_value(getattr(item, key))}</td>"
                    )
                self.println("    </tr>")
            self.println("  </tbody>")
            self.println("</table>")
        else:
            self.println("<table>")
            for key, data in sorted_items(value):
                self.println("  <tr>")
                self.println(
                    "    "
                    f"<th>{self.format_html_value(key)}</th>"
                    f"<td>{self.format_html_value(data)}</td>"
                )
                self.println("  </tr>")
            self.println("</table>")

    def print_text(self, value, header) -> None:
        """Text print."""
        if header is not None:
            for item in value:
                for key in header:
                    self.println(
                        f"{self.format_output_value(key)}: "
                        f"{self.format_output_value(getattr(item, key))}"
                    )
                self.println("")
        else:
            for key, data in sorted_items(value):
                self.println(
                    f"{self.format_output_value(key)}: {self.format_output_value(data)}"
                )

    def print(self, value) -> None:
        """Print value."""
        header = None
        if isinstance(value, list):
            if len(value) == 0:
                return
            header = sorted(value[0].keys(), key=sort_key)

        match self.args.format:
            case "json":
                self.print_json(value)
            case "csv":
                self.print_csv(value, header)
            case "html":
                self.print_html(value, header)
            case _:
                self.print_text(value, header)

    def run(self) -> None:
        """Main execution of the command."""
        raise NotImplementedError


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
                "Object on which we should operate (project, component or translation)"
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

    def run(self) -> None:
        """Main execution of the command."""
        raise NotImplementedError

    @staticmethod
    def check_result(result, message) -> None:
        """Check result json data."""
        if not result["result"]:
            raise CommandError(message, result.get("detail", ""))


class ProjectCommand(ObjectCommand):
    """Wrapper to allow only project objects."""

    def get_object(self, blank: bool = False):
        """Return component object."""
        obj = super().get_object(blank=blank)
        if not isinstance(obj, wlc.Project):
            raise CommandError("Not supported")
        return obj

    def run(self) -> None:
        """Main execution of the command."""
        raise NotImplementedError


class ComponentCommand(ObjectCommand):
    """Wrapper to allow only component objects."""

    def get_object(self, blank: bool = False):
        """Return component object."""
        obj = super().get_object(blank=blank)
        if not isinstance(obj, wlc.Component):
            raise CommandError("This command is supported only at component level")
        return obj

    def run(self) -> None:
        """Main execution of the command."""
        raise NotImplementedError


class TranslationCommand(ObjectCommand):
    """Wrapper to allow only translation objects."""

    def get_object(self, blank: bool = False):
        """Return translation object."""
        obj = super().get_object(blank=blank)
        if not isinstance(obj, wlc.Translation):
            raise CommandError("This command is supported only at translation level")
        return obj

    def run(self) -> None:
        """Main execution of the command."""
        raise NotImplementedError


class UnitCommand(ObjectCommand):
    """Wrapper to allow only unit objects."""

    def get_object(self, blank: bool = False):
        """Return unit object."""
        obj = super().get_object(blank=blank)
        if not isinstance(obj, wlc.Unit):
            raise CommandError("This command is supported only at unit level")
        return obj

    def run(self) -> None:
        """Main execution of the command."""
        raise NotImplementedError


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

    def run(self) -> None:
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

    def run(self) -> None:
        """Main execution of the command."""
        self.print(list(self.wlc.list_projects()))


@register_command
class ListComponents(ProjectCommand):
    """List components."""

    name = "list-components"
    description = "Lists all components (optionally per project)"

    def run(self) -> None:
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

    def run(self) -> None:
        """Main execution of the command."""
        self.print(list(self.wlc.list_languages()))


@register_command
class ListTranslations(ComponentCommand):
    """List translations."""

    name = "list-translations"
    description = "Lists all translations (optionally per component)"

    def run(self) -> None:
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
class ListUnits(TranslationCommand):
    """List units."""

    name = "list-units"
    description = "Lists units for a translation"

    @classmethod
    def add_parser(cls, subparser):
        """Create parser for command-line."""
        parser = super().add_parser(subparser)
        parser.add_argument(
            "-q",
            "--query",
            default=None,
            help="Search query to filter units",
        )
        return parser

    def run(self) -> None:
        """Main execution of the command."""
        obj = self.get_object()
        kwargs = {}
        if self.args.query:
            kwargs["q"] = self.args.query
        self.print(list(obj.units(**kwargs)))


@register_command
class Show(ObjectCommand):
    """Show object."""

    name = "show"
    description = "Shows translation, component, project or unit"

    def run(self) -> None:
        """Executor."""
        self.print(self.get_object())


@register_command
class Delete(ObjectCommand):
    """Delete object."""

    name = "delete"
    description = "Delete translation, component, project or unit"

    def run(self) -> None:
        """Executor."""
        self.get_object().delete()


@register_command
class ListObjects(ObjectCommand):
    """List object."""

    name = "ls"
    description = "List content of translation, component or project"

    def run(self) -> None:
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

    def run(self) -> None:
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

    def run(self) -> None:
        """Executor."""
        obj = self.get_object()
        result = obj.push()
        self.check_result(result, "Failed to push changes!")


@register_command
class Pull(ObjectCommand):
    """Pull object."""

    name = "pull"
    description = (
        "Pulls changes to Weblate from repository in translation, component or project"
    )

    def run(self) -> None:
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

    def run(self) -> None:
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

    def run(self) -> None:
        """Executor."""
        obj = self.get_object()
        result = obj.cleanup()
        self.check_result(result, "Failed to cleanup changes!")


@register_command
class Repo(ObjectCommand):
    """Display repository status for object."""

    name = "repo"
    description = (
        "Displays status of Weblate repository for translation, component or project"
    )

    def run(self) -> None:
        """Executor."""
        obj = self.get_object()
        self.print(obj.repository())


@register_command
class Changes(ObjectCommand):
    """Display repository status for object."""

    name = "changes"
    description = "Displays list of changes for translation, component or project"

    def run(self) -> None:
        """Executor."""
        obj = self.get_object()
        self.print(list(obj.changes()))


@register_command
class Stats(ObjectCommand):
    """Display repository statistics for object."""

    name = "stats"
    description = "Displays statistics for translation, component or project"

    def run(self) -> None:
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

    def run(self) -> None:
        """Executor."""
        obj = self.get_object()
        self.print(obj.lock_status())


@register_command
class Lock(ComponentCommand):
    """Lock component for translation."""

    name = "lock"
    description = "Locks components from translations"

    def run(self) -> None:
        """Executor."""
        obj = self.get_object()
        obj.lock()


@register_command
class Unlock(ComponentCommand):
    """Unlock component for translation."""

    name = "unlock"
    description = "Unlocks components from translations"

    def run(self) -> None:
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

    def download_component(self, component) -> None:
        """Download a single component as file (if not a translation)."""
        content = component.download(self.args.convert)
        if self.args.output is None:
            raise CommandError("Output is needed for download!")

        directory = Path(self.args.output)
        file_path = directory / (
            f"{sanitize_slug(component.project.slug)}-{sanitize_slug(component.slug)}.zip"
        )
        directory.mkdir(exist_ok=True, parents=True)
        file_path.write_bytes(content)

    def download_components(self, iterable) -> None:
        for component in iterable:
            # Ignore glossary via --no-glossary
            if getattr(component, "is_glossary", False) and self.args.no_glossary:
                continue
            self.download_component(component)
            self.println(
                f"downloaded translations for component: {component.full_slug()}"
            )

    def run(self) -> None:
        """Executor."""
        obj = self.get_object(blank=True)

        # Translation locale for a component
        if isinstance(obj, wlc.Translation):
            content = obj.download(self.args.convert)
            if self.args.output and self.args.output != "-":
                with open(self.args.output, "wb") as handle:
                    handle.write(content)
            else:
                if stream_isatty(self.stdout):
                    raise CommandError(
                        "Refusing to write downloaded file to terminal. "
                        "Use --output or redirect stdout."
                    )
                self.stdout.buffer.write(content)
            return

        # All translations for a component
        if isinstance(obj, wlc.Component):
            # Only download for the component we scoped
            self.download_components(
                [
                    component
                    for component in self.wlc.list_components()
                    if obj.full_slug() == component.full_slug()
                ]
            )
            return

        # All translations for a project
        if isinstance(obj, wlc.Project):
            self.download_components(obj.list())
            self.println(f"downloaded translations for project: {obj.full_slug()}")
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
            "--conflicts",
            choices=("ignore", "replace-translated", "replace-approved"),
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

    def run(self) -> None:
        """Executor."""
        obj = self.get_object()

        kwargs = {"overwrite": self.args.overwrite}
        for arg in ("author_name", "author_email", "method", "fuzzy", "conflicts"):
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
                result.get("detail", ""),
            )


@register_command
class EditUnit(UnitCommand):
    """Edit a unit."""

    name = "edit-unit"
    description = "Edits a unit"

    @classmethod
    def add_parser(cls, subparser):
        """Create parser for command-line."""
        parser = super().add_parser(subparser)
        parser.add_argument(
            "--target",
            nargs="+",
            help="Target (translated) string(s)",
        )
        parser.add_argument(
            "--state",
            type=int,
            help="Unit state (0: empty, 10: fuzzy, 20: translated, 30: approved)",
        )
        parser.add_argument(
            "--explanation",
            help="String explanation",
        )
        parser.add_argument(
            "--extra-flags",
            help="Additional string flags",
        )
        return parser

    def run(self) -> None:
        """Executor."""
        obj = self.get_object()
        kwargs = {}
        if self.args.target is not None:
            kwargs["target"] = self.args.target
        if self.args.state is not None:
            kwargs["state"] = self.args.state
        if self.args.explanation is not None:
            kwargs["explanation"] = self.args.explanation
        if self.args.extra_flags is not None:
            kwargs["extra_flags"] = self.args.extra_flags
        if not kwargs:
            raise CommandError("No changes specified!")
        obj.patch(**kwargs)


def parse_settings(args, settings):
    """Read settings based on command-line params."""
    config = WeblateConfig(args.config_section)
    if settings is None:
        config.load(args.config)
    else:
        for section, key, value in settings:
            config.set(section, key, value)

    if args.key:
        config.cli_key = args.key
    if args.url:
        config.cli_url = args.url

    return config


def main(settings=None, stdout=None, stdin=None, args=None) -> int:
    """Execution entry point."""
    parser = get_parser()
    if args is None:
        args = sys.argv[1:]
    args = parser.parse_args(args)

    debug_handler = None
    previous_wlc_level = None
    previous_wlc_propagate = None
    if args.debug:
        debug_handler, previous_wlc_level, previous_wlc_propagate = (
            enable_debug_logging()
        )

    try:
        config = parse_settings(args, settings)
    except WLCConfigurationError as error:
        print_stderr(f"Error: {error}")
        return 1

    command = COMMANDS[args.command](args, config, stdout, stdin)
    try:
        command.run()
    except wlc.WeblateDeniedError:
        url, key = config.get_url_key()
        if key:
            print_stderr(f"API key configured for {url} was rejected by server.")
        else:
            print_stderr(f"Missing API key for {url}.")
            print_stderr(
                "The API key can be specified by --key or in the configuration file."
            )
        return 1
    except RequestException as error:
        print_stderr(f"Request failed: {error}")
        return 10
    except (CommandError, wlc.WeblateException) as error:
        print_stderr(f"Error: {error}")
        return 1
    else:
        return 0
    finally:
        if debug_handler is not None:
            disable_debug_logging(
                debug_handler, previous_wlc_level, previous_wlc_propagate
            )
