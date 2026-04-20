# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test command-line interface."""

from __future__ import annotations

import csv
import html
import json
import os
import sys
from abc import ABC
from io import BytesIO, StringIO, TextIOWrapper
from tempfile import NamedTemporaryFile, TemporaryDirectory
from types import SimpleNamespace

import wlc
from wlc.config import WeblateConfig
from wlc.main import Command, Version, format_for_stream, main

from .test_base import APITest

TEST_DATA = os.path.join(os.path.dirname(__file__), "test_data")
TEST_CONFIG = os.path.join(TEST_DATA, "wlc")
TEST_SECTION = os.path.join(TEST_DATA, "section")


class BufferedStringIO(StringIO):
    """StringIO with a writable binary buffer for CLI tests."""

    def __init__(self, tty: bool = False) -> None:
        super().__init__()
        self._buffer = BytesIO()
        self._tty = tty

    @property
    def buffer(self) -> BytesIO:
        """Expose a binary buffer like sys.stdout.buffer."""
        return self._buffer

    def isatty(self) -> bool:
        return self._tty


class TTYStringIO(BufferedStringIO):
    """Buffered StringIO behaving like a terminal."""

    def __init__(self) -> None:
        super().__init__(tty=True)


class AttributeDict(dict):
    """Dictionary exposing keys as attributes."""

    def __getattr__(self, key):
        """Provide attribute-style access."""
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class CLITestBase(APITest, ABC):
    """Base class for CLI testing."""

    def execute(
        self, args, settings=None, stdout=None, stdin=None, expected=0, tty=False
    ):
        """Execute command and return output."""
        if settings is None:
            settings = ()
        elif not settings:
            settings = None
        output = TTYStringIO() if tty else BufferedStringIO()
        backup = sys.stdout
        backup_err = sys.stderr
        try:
            sys.stdout = output
            sys.stderr = output
            if stdout:
                stdout = output
            result = main(args=args, settings=settings, stdout=stdout, stdin=stdin)
            self.assertEqual(result, expected)
        finally:
            sys.stdout = backup
            sys.stderr = backup_err
        result = output.buffer.getvalue()
        if result:
            return result
        return output.getvalue()


class TestSettings(CLITestBase):
    """Test settings handling."""

    def test_commandline(self) -> None:
        """Configuration using command-line."""
        output = self.execute(["--url", "https://example.net/", "list-projects"])
        self.assertIn("Hello", output)

    def test_stdout(self) -> None:
        """Configuration using params."""
        output = self.execute(["list-projects"], stdout=True)
        self.assertIn("Hello", output)

    def test_debug(self) -> None:
        """Debug mode."""
        output = self.execute(["--debug", "list-projects"], stdout=True)
        self.assertIn("HTTP request", output)
        self.assertIn("api/projects", output)

    def test_debug_redacts_authorization(self) -> None:
        """Debug mode should not leak API tokens."""
        try:
            os.environ["WLC_KEY"] = "KEY"
            output = self.execute(["--debug", "show", "acl"], stdout=True)
            self.assertIn('"Authorization": "<redacted>"', output)
            self.assertNotIn("Token KEY", output)
        finally:
            del os.environ["WLC_KEY"]

    def test_settings(self) -> None:
        """Configuration using settings param."""
        output = self.execute(
            ["list-projects"], settings=(("weblate", "url", "https://example.net/"),)
        )
        self.assertIn("Hello", output)

    def test_config(self) -> None:
        """Configuration using custom config file."""
        output = self.execute(
            ["--config", TEST_CONFIG, "list-projects"], settings=False
        )
        self.assertIn("Hello", output)

    def test_config_section(self) -> None:
        """Configuration using custom config file section."""
        output = self.execute(
            ["--config", TEST_SECTION, "--config-section", "custom", "list-projects"],
            settings=False,
        )
        self.assertIn("Hello", output)

    def test_config_key(self) -> None:
        """Configuration using custom config file section and key set is ignored."""
        output = self.execute(
            ["--config", TEST_CONFIG, "--config-section", "withkey", "show", "acl"],
            settings=False,
            expected=1,
        )
        self.assertIn(
            "Error: Using 'key' in settings is insecure, use [keys] section instead",
            output,
        )

    def test_config_appdata(self) -> None:
        """Verify keys are loaded from the [keys] section in APPDATA-based config."""
        output = self.execute(["show", "acl"], settings=False, expected=1)
        self.assertIn("You don't have permission to access this object", output)
        try:
            os.environ["APPDATA"] = TEST_DATA
            output = self.execute(["show", "acl"], settings=False)
            self.assertIn("ACL", output)
        finally:
            del os.environ["APPDATA"]

    def test_env_key(self) -> None:
        """Verify WLC_KEY environment variable provides API key."""
        try:
            os.environ["WLC_KEY"] = "KEY"
            output = self.execute(["show", "acl"], settings=False)
            self.assertIn("ACL", output)
        finally:
            del os.environ["WLC_KEY"]

    def test_env_url(self) -> None:
        """Verify WLC_URL environment variable provides API URL."""
        try:
            os.environ["WLC_URL"] = "https://example.net/"
            output = self.execute(["list-projects"], settings=False)
            self.assertIn("Hello", output)
        finally:
            del os.environ["WLC_URL"]

    def test_config_cwd(self) -> None:
        """Test loading settings from current dir."""
        current = os.path.abspath(".")
        try:
            os.chdir(os.path.join(os.path.dirname(__file__), "test_data"))
            output = self.execute(["show"], settings=False)
            self.assertIn("Weblate", output)
        finally:
            os.chdir(current)

    def test_default_config_values(self) -> None:
        """Test default parser values."""
        config = WeblateConfig()
        self.assertEqual(config.get("weblate", "retries"), "0")
        self.assertEqual(config.get("weblate", "timeout"), "300")
        self.assertEqual(
            config.get("weblate", "method_whitelist"),
            "HEAD\nTRACE\nDELETE\nOPTIONS\nPUT\nGET",
        )
        self.assertEqual(config.get("weblate", "backoff_factor"), "0")
        self.assertIsNone(config.get("weblate", "status_forcelist"))

    def test_parsing(self) -> None:
        """Test config file parsing."""
        config = WeblateConfig()
        self.assertEqual(config.get("weblate", "url"), wlc.API_URL)
        config.load()
        config.load(TEST_CONFIG)
        self.assertEqual(config.get("weblate", "url"), "https://example.net/")
        self.assertEqual(config.get("weblate", "retries"), "999")
        self.assertEqual(config.get("weblate", "method_whitelist"), "PUT,POST")
        self.assertEqual(config.get("weblate", "backoff_factor"), "0.2")
        self.assertEqual(
            config.get("weblate", "status_forcelist"), "429,500,502,503,504"
        )

    def test_get_request_options(self) -> None:
        """Test the get_request_options method when all options are in config."""
        config = WeblateConfig()
        config.load()
        config.load(TEST_CONFIG)
        (
            retries,
            status_forcelist,
            method_whitelist,
            backoff_factor,
            _timeout,
        ) = config.get_request_options()
        self.assertEqual(retries, 999)
        self.assertEqual(status_forcelist, [429, 500, 502, 503, 504])
        self.assertEqual(method_whitelist, ["PUT", "POST"])
        self.assertEqual(backoff_factor, 0.2)

    def test_default_request_options(self) -> None:
        """Test the get_request_options method with default config values."""
        config = WeblateConfig()
        (
            retries,
            status_forcelist,
            method_whitelist,
            backoff_factor,
            timeout,
        ) = config.get_request_options()
        self.assertEqual(retries, 0)
        self.assertIsNone(status_forcelist)
        self.assertEqual(
            method_whitelist,
            ["HEAD", "TRACE", "DELETE", "OPTIONS", "PUT", "GET"],
        )
        self.assertEqual(backoff_factor, 0.0)
        self.assertEqual(timeout, 300)

    def test_argv(self) -> None:
        """Test sys.argv processing."""
        backup = sys.argv
        try:
            sys.argv = ["wlc", "version"]
            output = self.execute(None)
            self.assertIn(f"version: {wlc.__version__}", output)
        finally:
            sys.argv = backup


class TestOutput(CLITestBase):
    """Test output formatting."""

    @staticmethod
    def create_command(output: StringIO, format_name: str) -> Command:
        """Create command instance for direct rendering tests."""
        return Command(
            args=SimpleNamespace(format=format_name),
            config=WeblateConfig(),
            stdout=output,
        )

    def test_version_text(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "text", "version"])
        self.assertIn(f"version: {wlc.__version__}", output)

    def test_version_json(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "json", "version"])
        values = json.loads(output)
        self.assertEqual({"version": wlc.__version__}, values)

    def test_version_csv(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "csv", "version"])
        self.assertIn(f"version,{wlc.__version__}", output)

    def test_version_html(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "html", "version"])
        self.assertIn(wlc.__version__, output)

    def test_projects_text(self) -> None:
        """Test projects printing."""
        output = self.execute(["--format", "text", "list-projects"])
        self.assertIn("name: Hello", output)

    def test_projects_json(self) -> None:
        """Test projects printing."""
        output = self.execute(["--format", "json", "list-projects"])
        values = json.loads(output)
        self.assertEqual(2, len(values))

    def test_projects_csv(self) -> None:
        """Test projects printing."""
        output = self.execute(["--format", "csv", "list-projects"])
        self.assertIn("Hello", output)

    def test_csv_escapes_formula_values(self) -> None:
        """CSV output should neutralize spreadsheet formulas."""
        output = StringIO()
        cmd = self.create_command(output, "csv")

        cmd.print(
            {
                "plain": "Hello",
                "formula": "=1+1",
                "spaced": " \t@SUM(A1:A2)",
            }
        )

        rows = dict(csv.reader(StringIO(output.getvalue())))
        self.assertEqual(rows["plain"], "Hello")
        self.assertEqual(rows["formula"], "'=1+1")
        self.assertEqual(rows["spaced"], "' \t@SUM(A1:A2)")

    def test_csv_escapes_formula_headers(self) -> None:
        """CSV headers should also be hardened."""
        output = StringIO()
        cmd = self.create_command(output, "csv")

        cmd.print_csv([AttributeDict({"=name": "=Hello"})], ["=name"])

        rows = list(csv.reader(StringIO(output.getvalue())))
        self.assertEqual(rows[0], ["'=name"])
        self.assertEqual(rows[1], ["'=Hello"])

    def test_projects_html(self) -> None:
        """Test projects printing."""
        output = self.execute(["--format", "html", "list-projects"])
        self.assertIn("Hello", output)

    def test_format_for_stream_escapes_terminal_control_characters(self) -> None:
        """Terminal output should render control characters visibly."""
        self.assertEqual(
            format_for_stream("hello\x1b[31m\r\nworld", TTYStringIO()),
            r"hello\x1b[31m\r\nworld",
        )

    def test_text_output_escapes_terminal_control_characters(self) -> None:
        """Text output should not emit raw terminal control characters."""
        output = TTYStringIO()
        cmd = self.create_command(output, "text")

        cmd.print({"name": "hello\x1b[31m\r\nworld"})

        rendered = output.getvalue()
        self.assertIn(r"hello\x1b[31m\r\nworld", rendered)
        self.assertNotIn("\x1b", rendered)

    def test_text_output_sorts_detail_keys_lexically(self) -> None:
        """Text detail output should render keys in lexical order."""
        output = StringIO()
        cmd = self.create_command(output, "text")

        cmd.print({"zeta": "last", "alpha": "first", "middle": "mid"})

        self.assertEqual(
            output.getvalue().splitlines(),
            ["alpha: first", "middle: mid", "zeta: last"],
        )

    def test_text_output_sorts_list_headers_lexically(self) -> None:
        """Text list output should render fields in lexical order."""
        output = StringIO()
        cmd = self.create_command(output, "text")

        cmd.print([AttributeDict({"zeta": "last", "alpha": "first"})])

        self.assertEqual(output.getvalue(), "alpha: first\nzeta: last\n\n")

    def test_csv_output_escapes_terminal_control_characters(self) -> None:
        """CSV output should not emit raw terminal control characters to a tty."""
        output = TTYStringIO()
        cmd = self.create_command(output, "csv")

        cmd.print_csv([AttributeDict({"name": "hello\x1b[31m\r\nworld"})], ["name"])

        rendered = output.getvalue()
        self.assertIn(r"hello\x1b[31m\r\nworld", rendered)
        self.assertNotIn("\x1b", rendered)

    def test_csv_output_allows_missing_optional_fields(self) -> None:
        """CSV output should leave blank cells for missing optional fields."""
        output = StringIO()
        cmd = self.create_command(output, "csv")

        cmd.print(
            [
                AttributeDict({"name": "Hello", "source_language": "en"}),
                AttributeDict({"name": "World"}),
            ]
        )

        rows = list(csv.reader(StringIO(output.getvalue())))
        self.assertEqual(rows[0], ["name", "source_language"])
        self.assertEqual(rows[1], ["Hello", "en"])
        self.assertEqual(rows[2], ["World", ""])

    def test_csv_output_sorts_list_headers_lexically(self) -> None:
        """CSV list output should render headers in lexical order."""
        output = StringIO()
        cmd = self.create_command(output, "csv")

        cmd.print([AttributeDict({"zeta": "last", "alpha": "first"})])

        rows = list(csv.reader(StringIO(output.getvalue())))
        self.assertEqual(rows[0], ["alpha", "zeta"])
        self.assertEqual(rows[1], ["first", "last"])

    def test_html_output_escapes_terminal_control_characters(self) -> None:
        """HTML output should not emit raw terminal control characters to a tty."""
        output = TTYStringIO()
        cmd = self.create_command(output, "html")

        cmd.print({"name": "hello\x1b[31m\r\nworld"})

        rendered = output.getvalue()
        self.assertIn(r"hello\x1b[31m\r\nworld", rendered)
        self.assertNotIn("\x1b", rendered)

    def test_html_escapes_list_output(self) -> None:
        """HTML list output escapes headers and values."""
        payload_key = '<script>alert("key")</script>'
        payload_value = '<img src=x onerror=alert("value")>'
        output = StringIO()
        cmd = self.create_command(output, "html")

        cmd.print([AttributeDict({payload_key: payload_value})])

        rendered = output.getvalue()
        self.assertIn(html.escape(payload_key), rendered)
        self.assertIn(html.escape(payload_value), rendered)
        self.assertNotIn(payload_key, rendered)
        self.assertNotIn(payload_value, rendered)

    def test_html_output_sorts_list_headers_lexically(self) -> None:
        """HTML list output should render headers in lexical order."""
        output = StringIO()
        cmd = self.create_command(output, "html")

        cmd.print([AttributeDict({"zeta": "last", "alpha": "first"})])

        rendered = output.getvalue()
        self.assertLess(
            rendered.index("<th>alpha</th>"), rendered.index("<th>zeta</th>")
        )
        self.assertLess(
            rendered.index("<td>first</td>"), rendered.index("<td>last</td>")
        )

    def test_html_escapes_detail_output(self) -> None:
        """HTML detail output escapes keys and values."""
        payload_value = '<svg onload=alert("value")>'
        output = StringIO()
        cmd = self.create_command(output, "html")

        cmd.print({"name": payload_value})

        rendered = output.getvalue()
        self.assertIn(html.escape(payload_value), rendered)
        self.assertNotIn(payload_value, rendered)

    def test_json_encoder(self) -> None:
        """Test JSON encoder."""
        output = StringIO()
        cmd = Version(args=[], config=WeblateConfig(), stdout=output)
        with self.assertRaises(TypeError):
            cmd.print_json(self)


class TestCommands(CLITestBase):
    """Individual command tests."""

    def test_version_bare(self) -> None:
        """Test version printing."""
        output = self.execute(["version", "--bare"])
        self.assertEqual(f"{wlc.__version__}\n", output)

    def test_ls(self) -> None:
        """Project listing."""
        output = self.execute(["ls"])
        self.assertIn("Hello", output)
        output = self.execute(["ls", "hello"])
        self.assertIn("Weblate", output)
        output = self.execute(["ls", "empty"])
        self.assertEqual("", output)

    def test_list_languages(self) -> None:
        """Language listing."""
        output = self.execute(["list-languages"])
        self.assertIn("Turkish", output)

    def test_list_projects(self) -> None:
        """Project listing."""
        output = self.execute(["list-projects"])
        self.assertIn("Hello", output)

    def test_list_components(self) -> None:
        """Components listing."""
        output = self.execute(["list-components"])
        self.assertIn("/hello/weblate", output)

        output = self.execute(["list-components", "hello"])
        self.assertIn("/hello/weblate", output)

        output = self.execute(["list-components", "hello/weblate"], expected=1)
        self.assertIn("Not supported", output)

    def test_list_translations(self) -> None:
        """Translations listing."""
        output = self.execute(["list-translations"])
        self.assertIn("/hello/weblate/cs/", output)

        output = self.execute(["list-translations", "hello/weblate"])
        self.assertIn("/hello/weblate/cs/", output)

        output = self.execute(["list-translations", "hello/weblate"])
        self.assertIn("/hello/weblate/cs/", output)

        output = self.execute(
            ["--format", "json", "list-translations", "hello/weblate"]
        )
        self.assertIn("/hello/weblate/cs/", output)

    def test_show(self) -> None:
        """Project show."""
        output = self.execute(["show", "hello"])
        self.assertIn("Hello", output)

        output = self.execute(["show", "hello/weblate"])
        self.assertIn("Weblate", output)

        output = self.execute(["show", "hello/weblate/cs"])
        self.assertIn("/hello/weblate/cs/", output)

    def test_show_error(self) -> None:
        self.execute(["show", "io"], expected=10)
        with self.assertRaises(FileNotFoundError):
            self.execute(["show", "bug"])

    def test_delete(self) -> None:
        """Project delete."""
        output = self.execute(["delete", "hello"])
        self.assertEqual("", output)

        output = self.execute(["delete", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["delete", "hello/weblate/cs"])
        self.assertEqual("", output)

    def test_commit(self) -> None:
        """Project commit."""
        output = self.execute(["commit", "hello"])
        self.assertEqual("", output)

        output = self.execute(["commit", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["commit", "hello/weblate/cs"])
        self.assertEqual("", output)

    def test_push(self) -> None:
        """Project push."""
        msg = "Error: Failed to push changes!\nPush is disabled for Hello/Weblate.\n"
        output = self.execute(["push", "hello"], expected=1)
        self.assertEqual(msg, output)

        output = self.execute(["push", "hello/weblate"], expected=1)
        self.assertEqual(msg, output)

        output = self.execute(["push", "hello/weblate/cs"], expected=1)
        self.assertEqual(msg, output)

    def test_pull(self) -> None:
        """Project pull."""
        output = self.execute(["pull", "hello"])
        self.assertEqual("", output)

        output = self.execute(["pull", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["pull", "hello/weblate/cs"])
        self.assertEqual("", output)

    def test_reset(self) -> None:
        """Project reset."""
        output = self.execute(["reset", "hello"])
        self.assertEqual("", output)

        output = self.execute(["reset", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["reset", "hello/weblate/cs"])
        self.assertEqual("", output)

    def test_cleanup(self) -> None:
        """Project cleanup."""
        output = self.execute(["cleanup", "hello"])
        self.assertEqual("", output)

        output = self.execute(["cleanup", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["cleanup", "hello/weblate/cs"])
        self.assertEqual("", output)

    def test_repo(self) -> None:
        """Project repo."""
        output = self.execute(["repo", "hello"])
        self.assertIn("needs_commit", output)

        output = self.execute(["repo", "hello/weblate"])
        self.assertIn("needs_commit", output)

        output = self.execute(["repo", "hello/weblate/cs"])
        self.assertIn("needs_commit", output)

    def test_stats(self) -> None:
        """Project stats."""
        output = self.execute(["stats", "hello"])
        self.assertIn("translated_percent", output)

        output = self.execute(["stats", "hello/weblate"])
        self.assertIn("failing_percent", output)

        output = self.execute(["stats", "hello/weblate/cs"])
        self.assertIn("failing_percent", output)

    def test_locks(self) -> None:
        """Project locks."""
        output = self.execute(["lock-status", "hello"], expected=1)
        self.assertIn("This command is supported only at component level", output)

        output = self.execute(["lock-status", "hello/weblate"])
        self.assertIn("locked", output)
        output = self.execute(["lock", "hello/weblate"])
        self.assertEqual("", output)
        output = self.execute(["unlock", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["lock-status", "hello/weblate/cs"], expected=1)
        self.assertIn("This command is supported only at component level", output)

    def test_changes(self) -> None:
        """Project changes."""
        output = self.execute(["changes", "hello"])
        self.assertIn("action_name", output)

        output = self.execute(["changes", "hello/weblate"])
        self.assertIn("action_name", output)

        output = self.execute(["changes", "hello/weblate/cs"])
        self.assertIn("action_name", output)

    def test_download(self) -> None:
        """Translation file downloads."""
        output = self.execute(["download"], expected=1)
        self.assertIn("Output is needed", output)

        with TemporaryDirectory() as tmpdirname:
            self.execute(["download", "--output", tmpdirname])

        output = self.execute(["download", "hello/weblate/cs"])
        self.assertIn(b"Plural-Forms:", output)

        output = self.execute(
            ["download", "hello/weblate/cs"], stdout=True, expected=1, tty=True
        )
        self.assertIn("Refusing to write downloaded file to terminal", output)

        output = self.execute(["download", "hello/weblate/cs", "--convert", "csv"])
        self.assertIn(b'"location"', output)

        with NamedTemporaryFile() as handle:
            handle.close()
            self.execute(["download", "hello/weblate/cs", "-o", handle.name])
            with open(handle.name, "rb") as tmp:
                output = tmp.read()
            self.assertIn(b"Plural-Forms:", output)

        output = self.execute(["download", "hello/weblate"], expected=1)
        self.assertIn("Output is needed", output)

        with TemporaryDirectory() as tmpdirname:
            self.execute(["download", "hello/weblate", "--output", tmpdirname])

        output = self.execute(["download", "hello"], expected=1)
        self.assertIn("Output is needed", output)

        with TemporaryDirectory() as tmpdirname:
            self.execute(["download", "hello", "--no-glossary", "--output", tmpdirname])
            # The hello-android should not be present as it is flagged as a glossary
            self.assertEqual(os.listdir(tmpdirname), ["hello-weblate.zip"])

        with TemporaryDirectory() as tmpdirname:
            self.execute(
                [
                    "download",
                    "hello",
                    "--convert",
                    "zip",
                    "--output",
                    os.path.join(tmpdirname, "output"),
                ]
            )
            self.assertEqual(os.listdir(tmpdirname), ["output"])

    def test_download_config(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            self.execute(
                [
                    "--config",
                    TEST_CONFIG,
                    "--config-section",
                    "withcomponent",
                    "download",
                    "--output",
                    tmpdirname,
                ],
                settings=False,
            )
            self.assertEqual(os.listdir(tmpdirname), ["hello-weblate.zip"])
        with TemporaryDirectory() as tmpdirname:
            self.execute(
                [
                    "--config",
                    TEST_CONFIG,
                    "--config-section",
                    "withproject",
                    "download",
                    "--output",
                    tmpdirname,
                ],
                settings=False,
            )
            self.assertEqual(
                set(os.listdir(tmpdirname)), {"hello-weblate.zip", "hello-android.zip"}
            )

    def test_upload(self) -> None:
        """Translation file uploads."""
        msg = "Error: Failed to upload translations!\nNot found.\n"

        output = self.execute(["upload", "hello/weblate"], expected=1)
        self.assertEqual(
            "Error: This command is supported only at translation level\n", output
        )

        with self.get_text_io_wrapper("test upload data") as stdin:
            output = self.execute(["upload", "hello/weblate/cs"], stdin=stdin)
            self.assertEqual("", output)

        with self.get_text_io_wrapper("wrong upload data") as stdin:
            output = self.execute(
                ["upload", "hello/weblate/cs"], stdin=stdin, expected=1
            )
            self.assertEqual(msg, output)

        with NamedTemporaryFile(delete=False) as handle:
            handle.write(b"test upload overwrite")
            handle.close()
            output = self.execute(
                ["upload", "hello/weblate/cs", "-i", handle.name, "--overwrite"]
            )
            self.assertEqual("", output)

    @staticmethod
    def get_text_io_wrapper(string):
        """Create a text io wrapper from a string."""
        return TextIOWrapper(BytesIO(string.encode()), "utf8")

    def test_list_units(self) -> None:
        """Unit listing."""
        output = self.execute(["list-units", "hello/weblate/cs"])
        self.assertIn("id", output)

        output = self.execute(
            ["list-units", "hello/weblate/cs", "--query", 'source:="mr"']
        )
        self.assertIn("117", output)

        output = self.execute(["list-units", "hello/weblate"], expected=1)
        self.assertIn("This command is supported only at translation level", output)

    def test_show_unit(self) -> None:
        """Unit show."""
        output = self.execute(["show", "123"])
        self.assertIn("123", output)
        self.assertIn("source", output)

    def test_delete_unit(self) -> None:
        """Unit delete."""
        output = self.execute(["delete", "123"])
        self.assertEqual("", output)

    def test_edit_unit(self) -> None:
        """Unit edit."""
        output = self.execute(["edit-unit", "123", "--target", "foo", "--state", "30"])
        self.assertEqual("", output)

        output = self.execute(["edit-unit", "hello/weblate/cs"], expected=1)
        self.assertIn("This command is supported only at unit level", output)

        output = self.execute(["edit-unit", "123"], expected=1)
        self.assertIn("No changes specified", output)


class TestErrors(CLITestBase):
    """Error handling tests."""

    def test_commandline_missing_key(self) -> None:
        """Configuration using command-line."""
        output = self.execute(
            ["--url", "http://denied.example.com", "list-projects"], expected=1
        )
        self.assertIn("Missing API key", output)

    def test_commandline_wrong_key(self) -> None:
        """Configuration using command-line."""
        output = self.execute(
            ["--key", "x", "--url", "http://denied.example.com", "list-projects"],
            expected=1,
        )
        self.assertIn("was rejected by server", output)
