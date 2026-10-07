# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test output encoding."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import StringIO

from wlc.config import WeblateConfig
from wlc.main import Version

from .test_base import AttributeDict, CLITestBase


class JSONOutputTest(CLITestBase):
    """JSON output should preserve mapping contents."""

    def test_json_encoder_userdict(self) -> None:
        """UserDict values should support nesting and datetime encoding."""
        output = StringIO()
        cmd = Version(args=[], config=WeblateConfig(), stdout=output)
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
        cmd = Version(args=[], config=WeblateConfig(), stdout=output)
        obj = cmd.wlc.get_project("hello")
        cmd.print_json(obj)
        values = json.loads(output.getvalue())
        self.assertEqual(values["source_language"]["code"], "en")
        self.assertNotIn("id", values)

    def test_json_encoder_nullable_field(self) -> None:
        """Missing nullable model fields should still serialize as null."""
        output = StringIO()
        cmd = Version(args=[], config=WeblateConfig(), stdout=output)
        obj = cmd.wlc.get_component("hello/weblate")
        cmd.print_json(obj)
        self.assertIsNone(json.loads(output.getvalue())["category"])
