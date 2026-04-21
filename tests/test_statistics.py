# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test statistics models."""

from __future__ import annotations

from unittest.mock import patch

import responses

from wlc import LanguageStats, Project, Statistics, Weblate

from .test_base import APITest


class ProjectLanguageStatisticsTest(APITest):
    """Project language statistics compatibility tests."""

    def test_legacy_items(self) -> None:
        """Legacy language statistics should only expose present fields."""
        project = Weblate().get_project("hello")
        stats = project.languages()[0]

        with patch.object(stats.weblate, "get") as get:
            values = dict(stats.items())
            self.assertRaises(AttributeError, getattr, stats, "failing")

        get.assert_not_called()
        self.assertEqual("cs", values["code"])
        self.assertEqual("čeština", values["language"])
        self.assertEqual("http://127.0.0.1:8000/projects/hello/-/cs/", values["url"])
        self.assertEqual(63.3, values["words_percent"])
        self.assertNotIn("failing", values)

    def test_paginated(self) -> None:
        """Project languages should accept paginated responses."""
        page1 = "http://127.0.0.1:8000/api/projects/paged/languages/"
        page2 = f"{page1}?page=2"
        responses.add(
            responses.GET,
            page1,
            json={
                "next": page2,
                "results": [
                    {
                        "code": "cs",
                        "language": "Czech",
                        "total": 8,
                        "translated": 5,
                        "translated_percent": 62.5,
                        "total_words": 30,
                        "translated_words": 19,
                        "url": "http://127.0.0.1:8000/projects/paged/-/cs/",
                        "words_percent": 63.3,
                    }
                ],
            },
        )
        responses.add(
            responses.GET,
            page2,
            json={
                "next": None,
                "results": [
                    {
                        "code": "en",
                        "language": "English",
                        "total": 8,
                        "translated": 4,
                        "translated_percent": 50.0,
                        "total_words": 30,
                        "translated_words": 15,
                        "url": "http://127.0.0.1:8000/projects/paged/-/en/",
                        "words_percent": 50.0,
                    }
                ],
            },
        )

        project = Project(
            Weblate(),
            "http://127.0.0.1:8000/api/projects/paged/",
            languages_url=page1,
        )

        self.assertEqual(["cs", "en"], [item.code for item in project.languages()])

    def test_current_statistics_shape(self) -> None:
        """Project languages should accept current statistics responses."""
        languages_url = "http://127.0.0.1:8000/api/projects/current/languages/"
        responses.add(
            responses.GET,
            languages_url,
            json=[
                {
                    "total": 8,
                    "total_words": 30,
                    "total_chars": 120,
                    "last_change": None,
                    "recent_changes": 1,
                    "translated": 5,
                    "translated_words": 19,
                    "translated_percent": 62.5,
                    "translated_words_percent": 63.3,
                    "translated_chars": 75,
                    "translated_chars_percent": 62.5,
                    "fuzzy": 0,
                    "fuzzy_percent": 0.0,
                    "fuzzy_words": 0,
                    "fuzzy_words_percent": 0.0,
                    "fuzzy_chars": 0,
                    "fuzzy_chars_percent": 0.0,
                    "failing": 1,
                    "failing_percent": 12.5,
                    "approved": 4,
                    "approved_percent": 50.0,
                    "approved_words": 15,
                    "approved_words_percent": 50.0,
                    "approved_chars": 60,
                    "approved_chars_percent": 50.0,
                    "readonly": 0,
                    "readonly_percent": 0.0,
                    "readonly_words": 0,
                    "readonly_words_percent": 0.0,
                    "readonly_chars": 0,
                    "readonly_chars_percent": 0.0,
                    "suggestions": 2,
                    "comments": 3,
                    "code": "cs",
                    "name": "Czech",
                    "translate_url": "http://127.0.0.1:8000/projects/current/-/cs/",
                }
            ],
        )
        project = Project(
            Weblate(),
            "http://127.0.0.1:8000/api/projects/current/",
            languages_url=languages_url,
        )

        stats = project.languages()[0]

        self.assertIsInstance(stats, LanguageStats)
        self.assertIsInstance(stats, Statistics)
        self.assertEqual("cs", stats.code)
        self.assertEqual("Czech", stats.name)
        self.assertEqual(50.0, stats.approved_percent)
        self.assertEqual(63.3, stats.translated_words_percent)
        self.assertNotIn("url", stats.keys())


class StatisticsTest(APITest):
    """Statistics model tests."""

    def test_url_less_statistics_do_not_refresh(self) -> None:
        """Missing fields on URL-less statistics should fail locally."""
        stats = Statistics(Weblate(), total=8)

        with patch.object(stats.weblate, "get") as get:
            self.assertRaises(AttributeError, getattr, stats, "url")
            self.assertEqual({"total": 8}, dict(stats.items()))

        get.assert_not_called()
