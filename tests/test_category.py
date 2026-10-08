# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test category resource models."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import responses

from wlc import Category, Weblate, WeblateException

from .test_base import APITest


class CategoryTest(APITest):
    """Category model testing."""

    def test(self) -> None:
        obj = Category(Weblate(), "http://127.0.0.1:8000/api/categories/1/")
        self.assertIsInstance(obj, Category)
        self.assertIsNone(obj.category)
        self.assertEqual(obj.name, "Hi")
        self.assertEqual(obj.slug, "hi")

    def test_full_slug_with_parent_category_url(self) -> None:
        """Category parents returned as URLs should still build full slugs."""
        parent_url = "http://127.0.0.1:8000/api/categories/10/"
        responses.add(
            responses.GET,
            parent_url,
            json={
                "category": None,
                "name": "Parent",
                "project": "http://127.0.0.1:8000/api/projects/hello/",
                "slug": "parent",
                "url": parent_url,
            },
        )

        obj = Category(
            Weblate(),
            "http://127.0.0.1:8000/api/categories/11/",
            category=parent_url,
            name="Child",
            project={
                "url": "http://127.0.0.1:8000/api/projects/hello/",
                "slug": "hello",
            },
            slug="child",
        )

        self.assertEqual(obj.full_slug(), "hello/parent/child")

    def test_full_slug_with_three_category_levels(self) -> None:
        """Category slugs should include all three supported category levels."""
        root_url = "http://127.0.0.1:8000/api/categories/10/"
        parent_url = "http://127.0.0.1:8000/api/categories/11/"
        project = {
            "url": "http://127.0.0.1:8000/api/projects/hello/",
            "slug": "hello",
        }
        responses.add(
            responses.GET,
            parent_url,
            json={
                "category": root_url,
                "name": "Parent",
                "project": project,
                "slug": "parent",
                "url": parent_url,
            },
        )
        responses.add(
            responses.GET,
            root_url,
            json={
                "category": None,
                "name": "Root",
                "project": project,
                "slug": "root",
                "url": root_url,
            },
        )

        obj = Category(
            Weblate(),
            "http://127.0.0.1:8000/api/categories/12/",
            category=parent_url,
            name="Child",
            project=project,
            slug="child",
        )

        self.assertEqual(obj.full_slug(), "hello/root/parent/child")
        self.assertEqual(len(responses.calls), 2)

    def test_full_slug_rejects_self_cycle(self) -> None:
        """A category should not be able to name itself as its parent."""
        category_url = "http://127.0.0.1:8000/api/categories/10/"
        obj = Category(
            Weblate(),
            category_url,
            category=category_url,
            name="Cycle",
            project={
                "url": "http://127.0.0.1:8000/api/projects/hello/",
                "slug": "hello",
            },
            slug="cycle",
        )

        with self.assertRaisesRegex(WeblateException, "cyclic category hierarchy"):
            obj.full_slug()

        self.assertEqual(len(responses.calls), 0)

    def test_full_slug_rejects_parent_cycle(self) -> None:
        """A category parent cycle should stop before fetching a URL twice."""
        first_url = "http://127.0.0.1:8000/api/categories/10/"
        second_url = "http://127.0.0.1:8000/api/categories/11/"
        project = {
            "url": "http://127.0.0.1:8000/api/projects/hello/",
            "slug": "hello",
        }
        responses.add(
            responses.GET,
            second_url,
            json={
                "category": first_url,
                "name": "Second",
                "project": project,
                "slug": "second",
                "url": second_url,
            },
        )
        obj = Category(
            Weblate(),
            first_url,
            category=second_url,
            name="First",
            project=project,
            slug="first",
        )

        with self.assertRaisesRegex(WeblateException, "cyclic category hierarchy"):
            obj.full_slug()

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.url, second_url)

    def test_full_slug_rejects_excessive_depth(self) -> None:
        """A fourth category level should be rejected without being fetched."""
        urls = [
            f"http://127.0.0.1:8000/api/categories/{category_id}/"
            for category_id in range(10, 14)
        ]
        project = {
            "url": "http://127.0.0.1:8000/api/projects/hello/",
            "slug": "hello",
        }
        for index in (2, 1):
            responses.add(
                responses.GET,
                urls[index],
                json={
                    "category": urls[index - 1],
                    "name": f"Category {index}",
                    "project": project,
                    "slug": f"category-{index}",
                    "url": urls[index],
                },
            )
        obj = Category(
            Weblate(),
            urls[3],
            category=urls[2],
            name="Category 3",
            project=project,
            slug="category-3",
        )

        with self.assertRaisesRegex(WeblateException, "deeper than 3 levels"):
            obj.full_slug()

        self.assertEqual(len(responses.calls), 2)
        self.assertEqual(
            [call.request.url for call in responses.calls],
            [urls[2], urls[1]],
        )
