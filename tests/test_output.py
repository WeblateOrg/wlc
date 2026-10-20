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
from typing import TYPE_CHECKING
from unittest.mock import patch
from weakref import ref

import responses

import wlc
from wlc.config import WeblateConfig
from wlc.main import Command, Version, format_for_stream, main, print_stderr

from .test_base import AttributeDict, CLITestBase, TTYStringIO

if TYPE_CHECKING:
    from collections.abc import Iterator
    from weakref import ReferenceType


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


class StreamingOutputTest(OutputTestBase):
    """Listings should write each row before consuming the next one."""

    def test_iterator_output_matches_existing_formatting(self) -> None:
        """One-pass listings retain headers, encoding, and whitespace."""
        rows = [
            AttributeDict(
                {
                    "name": '=Hello <&>\n"world"',
                    "nested": AttributeDict(
                        {"date": datetime(2026, 1, 1, tzinfo=timezone.utc)}
                    ),
                }
            ),
            AttributeDict({"name": "Unicode: čeština", "nested": None}),
        ]

        def listing(count: int, output: StringIO) -> Iterator[AttributeDict]:
            for index in range(count):
                yield rows[index]
                self.assertIn("Hello", output.getvalue())

        for format_name in ("text", "csv", "html", "json"):
            for count in (0, 1, 2):
                with self.subTest(format=format_name, count=count):
                    output = StringIO()
                    expected = StringIO()
                    baseline = self.create_command(expected, format_name)
                    if count:
                        if format_name == "json":
                            baseline.print_json(rows[:count])
                        else:
                            renderer = getattr(baseline, f"print_{format_name}")
                            renderer(rows[:count], sorted(rows[0].keys()))

                    self.create_command(output, format_name).print(
                        listing(count, output)
                    )
                    self.assertEqual(output.getvalue(), expected.getvalue())

    def test_iterator_does_not_retain_complete_listing(self) -> None:
        """Rendered rows should be released during a long listing."""

        def listing(
            references: list[ReferenceType[AttributeDict]],
        ) -> Iterator[AttributeDict]:
            for index in range(100):
                row = AttributeDict({"name": str(index)})
                references.append(ref(row))
                yield row
                self.assertLessEqual(
                    sum(reference() is not None for reference in references),
                    3,
                )

        for format_name in ("text", "csv", "html", "json"):
            with self.subTest(format=format_name):
                references: list[ReferenceType[AttributeDict]] = []

                self.create_command(StringIO(), format_name).print(listing(references))

    def test_paginated_cli_output_and_late_failure(self) -> None:
        """Write page one before fetching page two, including on failure."""
        for format_name in ("text", "csv", "html", "json"):
            for fail in (False, True):
                with self.subTest(format=format_name, fail=fail):
                    self.check_paginated_cli_output(format_name, fail=fail)

    def check_paginated_cli_output(self, format_name: str, *, fail: bool) -> None:
        """Exercise page delivery and failure with independent output streams."""
        output = StringIO()
        errors = StringIO()
        url = "http://127.0.0.1:8001/api/projects/"
        row = {
            "url": f"{url}project/",
            "web_url": "http://127.0.0.1:8001/projects/project/",
            "name": "First page project",
            "slug": "project",
            "web": "https://example.com/",
        }
        responses.add(
            responses.GET,
            url,
            json={"results": [row], "next": f"{url}?page=2"},
            match=[responses.matchers.query_param_matcher({})],
        )

        def next_page(
            _request: object,
        ) -> tuple[int, dict[str, str], str]:
            self.assertIn("First page project", output.getvalue())
            if fail:
                return 500, {}, ""
            return (
                200,
                {"Content-Type": "application/json"},
                json.dumps({"results": [row], "next": None}),
            )

        responses.add_callback(responses.GET, f"{url}?page=2", callback=next_page)
        with patch("sys.stderr", errors):
            result = main(
                args=[
                    "--url",
                    "http://127.0.0.1:8001/api/",
                    "--format",
                    format_name,
                    "list-projects",
                ],
                settings=(),
                stdout=output,
            )
        self.assertEqual(result, 1 if fail else 0)
        if fail:
            self.assertIn("Error: HTTP error 500:", errors.getvalue())
            self.assertNotIn("Error:", output.getvalue())
            if format_name == "json":
                with self.assertRaises(json.JSONDecodeError):
                    json.loads(output.getvalue())
            elif format_name == "html":
                self.assertNotIn("</table>", output.getvalue())
        else:
            self.assertEqual(errors.getvalue(), "")
            if format_name == "json":
                self.assertEqual(len(json.loads(output.getvalue())), 2)
        responses.remove(responses.GET, url)
        responses.remove(responses.GET, f"{url}?page=2")

    def test_first_row_failure_has_no_output(self) -> None:
        """A failure before any result should not emit an empty container."""
        for format_name in ("text", "csv", "html", "json"):
            with self.subTest(format=format_name):
                output = StringIO()

                def listing() -> Iterator[AttributeDict]:
                    msg = "Listing failed"
                    raise wlc.WeblateException(msg)
                    yield

                with self.assertRaisesRegex(wlc.WeblateException, "Listing failed"):
                    self.create_command(output, format_name).print(listing())
                self.assertEqual(output.getvalue(), "")


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

    def test_format_for_stream_escapes_unicode_display_controls(self) -> None:
        """Terminal output should visibly render selected Unicode controls."""
        codepoints = (
            0x00AD,
            0x061C,
            0x200B,
            0x200E,
            0x200F,
            0x202A,
            0x202B,
            0x202C,
            0x202D,
            0x202E,
            0x2060,
            0x2061,
            0x2062,
            0x2063,
            0x2064,
            0x2066,
            0x2067,
            0x2068,
            0x2069,
            0xFEFF,
        )
        for codepoint in codepoints:
            with self.subTest(codepoint=f"U+{codepoint:04X}"):
                self.assertEqual(
                    format_for_stream(chr(codepoint), TTYStringIO()),
                    f"\\u{codepoint:04x}",
                )

    def test_format_for_stream_preserves_non_terminal_unicode(self) -> None:
        """Data streams and ordinary RTL text should preserve Unicode."""
        value = "עברית العربية harmless\u202egnp.suriv\u202c"
        self.assertEqual(format_for_stream(value, StringIO()), value)
        self.assertEqual(format_for_stream(value, object()), value)
        self.assertEqual(
            format_for_stream("עברית العربية", TTYStringIO()),
            "עברית العربية",
        )
        joining_text = "می\u200cروم 👩\u200d💻"
        self.assertEqual(format_for_stream(joining_text, TTYStringIO()), joining_text)

    def test_stderr_escapes_unicode_display_controls(self) -> None:
        """Interactive error output should visibly render Unicode controls."""
        output = TTYStringIO()
        with patch("wlc.main.sys.stderr", output):
            print_stderr("harmless\u202egnp.suriv\u202c")

        self.assertEqual(output.getvalue(), "harmless\\u202egnp.suriv\\u202c\n")

    def test_text_output_escapes_terminal_control_characters(self) -> None:
        """Text output should not emit raw terminal control characters."""
        output = TTYStringIO()
        cmd = self.create_command(output, "text")

        cmd.print({"name": "hello\x1b[31m\r\nworld\u202espoof\u202c"})

        rendered = output.getvalue()
        self.assertIn(r"hello\x1b[31m\r\nworld\u202espoof\u202c", rendered)
        self.assertNotIn("\x1b", rendered)
        self.assertNotIn("\u202e", rendered)

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

    def test_csv_escapes_formulas_after_control_whitespace(self) -> None:
        """Harden formula markers after VT, FF, and mixed leading whitespace."""
        for leading in ("\v", "\f", " \t\r\n\v\f", "\v \f\t"):
            for prefix in ("=", "+", "-", "@"):
                for stream in (StringIO, TTYStringIO):
                    with self.subTest(leading=leading, prefix=prefix, stream=stream):
                        output = stream()
                        cmd = self.create_command(output, "csv")
                        value = f"{leading}{prefix}1+1"
                        expected = format_for_stream(f"'{value}", output)

                        self.assertEqual(cmd.format_csv_value(value), expected)
                        cmd.print_csv([AttributeDict({value: value})], [value])
                        cmd.print_csv({value: value}, None)

                        rows = list(csv.reader(StringIO(output.getvalue())))
                        self.assertEqual(
                            rows, [[expected], [expected], [expected, expected]]
                        )

    def test_csv_preserves_non_formula_control_whitespace(self) -> None:
        """Preserve VT and FF when they do not obscure a formula marker."""
        output = StringIO()
        cmd = self.create_command(output, "csv")
        values = ("\v", "\f", "\vHello", "\fHello", "Hello\v=1+1", "Hello\f=1+1")

        for value in values:
            with self.subTest(value=value):
                self.assertEqual(cmd.format_csv_value(value), value)

        cmd.print_csv([AttributeDict({"value": value}) for value in values], ["value"])
        rows = list(csv.reader(StringIO(output.getvalue())))
        self.assertEqual(rows, [["value"], *[[value] for value in values]])

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
        aliases = [
            RawControlValue(
                "escape\x1b[31m nul\x00byte c1\x85byte bidi\u2066text\u2069"
            )
        ]
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
                self.assertIn(r"bidi\u2066text\u2069", rendered)
                self.assertNotIn("\x1b", rendered)
                self.assertNotIn("\x00", rendered)
                self.assertNotIn("\x85", rendered)
                self.assertNotIn("\u2066", rendered)
                self.assertNotIn("\u2069", rendered)

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

        cmd.print({"name": "hello\x1b[31m\r\nworld zero\u200bwidth"})

        rendered = output.getvalue()
        self.assertIn(r"hello\x1b[31m\r\nworld zero\u200bwidth", rendered)
        self.assertNotIn("\x1b", rendered)
        self.assertNotIn("\u200b", rendered)

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

    def test_json_preserves_unicode_display_controls(self) -> None:
        """JSON should preserve Unicode controls as structured data."""
        output = TTYStringIO()
        cmd = self.create_command(output, "json")
        value = {"name": "harmless\u202egnp.suriv\u202c"}

        cmd.print(value)

        self.assertEqual(json.loads(output.getvalue()), value)

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
