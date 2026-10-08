# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test CLI output formatting and encoding."""

from __future__ import annotations

import csv
import html
import json
from argparse import Namespace
from datetime import datetime, timezone
from io import StringIO

import wlc
from wlc.config import WeblateConfig
from wlc.main import Command, Version, format_for_stream

from .test_base import AttributeDict, CLITestBase, TTYStringIO


class JSONOutputTest(CLITestBase):
    """JSON output should preserve mapping contents."""

    def test_json_encoder_userdict(self) -> None:
        """UserDict values should support nesting and datetime encoding."""
        output = StringIO()
        cmd = Version(args=Namespace(), config=WeblateConfig(), stdout=output)
        cmd.print_json(
            AttributeDict(
                {
                    "nested": AttributeDict(
                        {"date": datetime(2026, 1, 1, tzinfo=timezone.utc)}
                    )
                }
            )
        )
        self.assertEqual(
            json.loads(output.getvalue()),
            {"nested": {"date": "2026-01-01T00:00:00+00:00"}},
        )

    def test_json_encoder_nested_models(self) -> None:
        """Lazy model fields should retain filtering and nested models."""
        output = StringIO()
        cmd = Version(args=Namespace(), config=WeblateConfig(), stdout=output)
        obj = cmd.wlc.get_project("hello")
        cmd.print_json(obj)
        values = json.loads(output.getvalue())
        self.assertEqual(values["source_language"]["code"], "en")
        self.assertNotIn("id", values)

    def test_json_encoder_nullable_field(self) -> None:
        """Missing nullable model fields should still serialize as null."""
        output = StringIO()
        cmd = Version(args=Namespace(), config=WeblateConfig(), stdout=output)
        obj = cmd.wlc.get_component("hello/weblate")
        cmd.print_json(obj)
        self.assertIsNone(json.loads(output.getvalue())["category"])


# pylint: disable-next=too-few-public-methods
class RawControlValue:
    """Value whose representation contains raw terminal controls."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __repr__(self) -> str:
        return self.value


class OutputTestBase(CLITestBase):
    """Shared command construction for output tests."""

    @staticmethod
    def create_command(output: StringIO, format_name: str) -> Command:
        """Create command instance for direct rendering tests."""
        return Command(
            args=Namespace(format=format_name),
            config=WeblateConfig(),
            stdout=output,
        )


class TestTextOutput(OutputTestBase):
    """Test text output formatting."""

    def test_version_text(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "text", "version"])
        self.assertIn(f"version: {wlc.__version__}", output)

    def test_projects_text(self) -> None:
        """Test projects printing."""
        output = self.execute(["--format", "text", "list-projects"])
        self.assertIn("name: Hello", output)

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

    def test_text_output_escapes_controls_in_structured_values(self) -> None:
        """Text output should escape controls after converting structured values."""
        output = TTYStringIO()
        cmd = self.create_command(output, "text")

        cmd.print({"aliases": ["safe", "hello\x1b[31mworld"]})

        rendered = output.getvalue()
        self.assertIn(r"hello\x1b[31mworld", rendered)
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


class TestCSVOutput(OutputTestBase):
    """Test CSV output formatting."""

    def test_version_csv(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "csv", "version"])
        self.assertIn(f"version,{wlc.__version__}", output)

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

    def test_csv_output_escapes_terminal_control_characters(self) -> None:
        """CSV output should not emit raw terminal control characters to a tty."""
        output = TTYStringIO()
        cmd = self.create_command(output, "csv")

        cmd.print_csv([AttributeDict({"name": "hello\x1b[31m\r\nworld"})], ["name"])

        rendered = output.getvalue()
        self.assertIn(r"hello\x1b[31m\r\nworld", rendered)
        self.assertNotIn("\x1b", rendered)

    def test_csv_output_escapes_controls_in_structured_values(self) -> None:
        """CSV output should escape controls after converting structured values."""
        aliases = [RawControlValue("escape\x1b[31m nul\x00byte c1\x85byte")]
        values = (
            ("detail", {"aliases": aliases}),
            ("tabular", [AttributeDict({"aliases": aliases})]),
        )

        for shape, value in values:
            with self.subTest(shape=shape):
                output = TTYStringIO()
                cmd = self.create_command(output, "csv")

                cmd.print(value)

                rendered = output.getvalue()
                self.assertIn(r"escape\x1b[31m", rendered)
                self.assertIn(r"nul\x00byte", rendered)
                self.assertIn(r"c1\x85byte", rendered)
                self.assertNotIn("\x1b", rendered)
                self.assertNotIn("\x00", rendered)
                self.assertNotIn("\x85", rendered)

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


class TestHTMLOutput(OutputTestBase):
    """Test HTML output formatting."""

    def test_version_html(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "html", "version"])
        self.assertIn(wlc.__version__, output)

    def test_projects_html(self) -> None:
        """Test projects printing."""
        output = self.execute(["--format", "html", "list-projects"])
        self.assertIn("Hello", output)

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


class TestJSONOutput(OutputTestBase):
    """Test JSON output formatting."""

    def test_version_json(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "json", "version"])
        values = json.loads(output)
        self.assertEqual({"version": wlc.__version__}, values)

    def test_projects_json(self) -> None:
        """Test projects printing."""
        output = self.execute(["--format", "json", "list-projects"])
        values = json.loads(output)
        self.assertEqual(2, len(values))
        self.assertEqual(values[1]["name"], "Hello")
        self.assertEqual(values[1]["slug"], "hello")

    def test_json_encoder(self) -> None:
        """Test JSON encoder."""
        output = StringIO()
        cmd = Version(args=Namespace(), config=WeblateConfig(), stdout=output)
        with self.assertRaises(TypeError):
            cmd.print_json(self)
