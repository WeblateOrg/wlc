# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Keyword-only API option contracts."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

from inspect import signature
from unittest import TestCase

from wlc import Component, Translation, Weblate
from wlc.exceptions import WeblateThrottlingError
from wlc.main import Command, CommandError, main


class KeywordOptionsTest(TestCase):
    """Keep ambiguous options out of positional API calls."""

    def test_options_reject_positional_calls(self) -> None:
        for function, arguments, options in (
            (
                Weblate,
                (),
                {"key": "KEY", "url": "https://example.com/api/", "config": None},
            ),
            (
                Weblate.request,
                (None, "get", "projects/"),
                {"data": {}, "files": {}, "params": {}},
            ),
            (
                Weblate.raw_request,
                (None, "get", "projects/"),
                {"data": {}, "files": {}, "params": {}},
            ),
            (
                Weblate.invoke_request,
                (None, "get", "projects/"),
                {"data": {}, "files": {}, "params": {}},
            ),
            (Weblate.post, (None, "projects/"), {"files": {}, "params": {}}),
            (Weblate.get, (None, "projects/"), {"params": {}}),
            (Weblate.list_factory, (None, "projects/", Component), {"params": {}}),
            (Weblate.list_units, (None, "units/"), {"params": {}}),
            (
                Weblate.add_source_string,
                (None,),
                {
                    "project": "project",
                    "component": "component",
                    "msgid": "key",
                    "msgstr": "value",
                    "source_language": "en",
                },
            ),
            (
                Weblate.create_project,
                (None,),
                {
                    "name": "Name",
                    "slug": "slug",
                    "website": "https://example.com/",
                    "source_language_name": "English",
                    "source_language_code": "en",
                },
            ),
            (
                Weblate.create_language,
                (None,),
                {"code": "en", "name": "English", "direction": "ltr", "plural": {}},
            ),
            (Component.add_source_string, (None,), {"msgid": "key", "msgstr": "value"}),
            (WeblateThrottlingError, (), {"limit": "100", "retry_after": "60"}),
            (
                Translation.upload,
                (None, b"content"),
                {"overwrite": True, "format": "po"},
            ),
            (Translation.download, (None,), {"convert": "csv"}),
            (Component.download, (None,), {"convert": "csv"}),
            (Command, (None, None), {"stdout": None, "stdin": None}),
            (CommandError, ("message",), {"detail": "detail"}),
            (main, (), {"settings": None, "stdout": None, "stdin": None, "args": []}),
        ):
            with self.subTest(function=function.__qualname__):
                call_signature = signature(function)
                call_signature.bind(*arguments, **options)
                option_items = list(options.items())
                for count in range(1, len(option_items) + 1):
                    with (
                        self.subTest(positional_options=count),
                        self.assertRaises(TypeError),
                    ):
                        call_signature.bind(
                            *arguments,
                            *(value for _name, value in option_items[:count]),
                            **dict(option_items[count:]),
                        )
