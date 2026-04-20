# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the module."""

from __future__ import annotations

import io

import responses

from wlc import (
    Weblate,
    WeblateException,
)

from .test_base import APITest


class WeblateURLValidationTest(APITest):
    """Tests request URL normalization for server-provided URLs."""

    evil_domain = "http://evil.example.com/api"

    def assert_origin_rejected(self, action, attacker_url, method=responses.GET):
        """Assert the client rejects a cross-origin URL before any request is sent."""
        attacker_requests = []

        def trap(request):
            attacker_requests.append(request)
            return 200, {}, "{}"

        responses.add_callback(
            method,
            attacker_url,
            callback=trap,
            content_type="application/json",
        )

        with self.assertRaisesRegex(
            WeblateException, "outside the configured API origin"
        ):
            action()

        self.assertFalse(attacker_requests)
        self.assertFalse(
            any(
                call.request.url is None or call.request.url.startswith(attacker_url)
                for call in responses.calls
            )
        )

    def test_rejects_cross_origin_pagination_url(self) -> None:
        """Pagination should not follow a hostile absolute next URL."""
        attacker_url = f"{self.evil_domain}/projects/"
        responses.add(
            responses.GET,
            "http://127.0.0.1:8000/api/hostile-projects/",
            json={"next": attacker_url, "results": []},
        )

        self.assert_origin_rejected(
            lambda: list(Weblate(key="KEY").list_projects("hostile-projects/")),
            attacker_url,
        )

    def test_rejects_cross_origin_refresh_url(self) -> None:
        """Lazy refresh should reject a hostile object URL from the API."""
        attacker_url = f"{self.evil_domain}/projects/hostile/"
        responses.add(
            responses.GET,
            "http://127.0.0.1:8000/api/projects/hostile/",
            json={
                "name": "Hostile",
                "slug": "hostile",
                "url": attacker_url,
                "web": "https://example.com/projects/hostile/",
                "web_url": "https://example.com/projects/hostile/",
            },
        )

        self.assert_origin_rejected(
            lambda: Weblate(key="KEY").get_project("hostile").refresh(),
            attacker_url,
        )

    def test_rejects_cross_origin_file_download_url(self) -> None:
        """Translation downloads should reject a hostile file_url."""
        attacker_url = f"{self.evil_domain}/translations/hostile/weblate/cs/file/"
        responses.add(
            responses.GET,
            "http://127.0.0.1:8000/api/translations/hostile/weblate/cs/",
            json={
                "url": "http://127.0.0.1:8000/api/translations/hostile/weblate/cs/",
                "file_url": attacker_url,
            },
        )

        self.assert_origin_rejected(
            lambda: Weblate(key="KEY").get_translation("hostile/weblate/cs").download(),
            attacker_url,
        )

    def test_rejects_cross_origin_file_upload_url(self) -> None:
        """Translation uploads should reject a hostile file_url."""
        attacker_url = f"{self.evil_domain}/translations/hostile/weblate/cs/file/"
        responses.add(
            responses.GET,
            "http://127.0.0.1:8000/api/translations/hostile/weblate/cs/",
            json={
                "url": "http://127.0.0.1:8000/api/translations/hostile/weblate/cs/",
                "file_url": attacker_url,
            },
        )

        self.assert_origin_rejected(
            lambda: (
                Weblate(key="KEY")
                .get_translation("hostile/weblate/cs")
                .upload(io.StringIO("test upload data"))
            ),
            attacker_url,
            method=responses.POST,
        )

    def test_rejects_cross_origin_repository_get_url(self) -> None:
        """Repository reads should reject a hostile repository_url."""
        attacker_url = f"{self.evil_domain}/translations/hostile/weblate/cs/repository/"
        responses.add(
            responses.GET,
            "http://127.0.0.1:8000/api/translations/hostile/weblate/cs/",
            json={
                "url": "http://127.0.0.1:8000/api/translations/hostile/weblate/cs/",
                "repository_url": attacker_url,
            },
        )

        self.assert_origin_rejected(
            lambda: (
                Weblate(key="KEY").get_translation("hostile/weblate/cs").repository()
            ),
            attacker_url,
        )

    def test_rejects_cross_origin_repository_post_url(self) -> None:
        """Repository mutations should reject a hostile repository_url."""
        attacker_url = f"{self.evil_domain}/translations/hostile/weblate/cs/repository/"
        responses.add(
            responses.GET,
            "http://127.0.0.1:8000/api/translations/hostile/weblate/cs/",
            json={
                "url": "http://127.0.0.1:8000/api/translations/hostile/weblate/cs/",
                "repository_url": attacker_url,
            },
        )

        self.assert_origin_rejected(
            lambda: Weblate(key="KEY").get_translation("hostile/weblate/cs").commit(),
            attacker_url,
            method=responses.POST,
        )

    def test_rejects_invalid_port_in_server_url(self) -> None:
        """Malformed absolute URLs should raise a WeblateException."""
        attacker_url = "http://evil.example.com:99999/api/projects/"
        responses.add(
            responses.GET,
            "http://127.0.0.1:8000/api/hostile-projects/",
            json={"next": attacker_url, "results": []},
        )

        with self.assertRaisesRegex(WeblateException, "invalid URL"):
            list(Weblate(key="KEY").list_projects("hostile-projects/"))

        self.assertFalse(
            any(
                call.request.url is not None and ":99999/" in call.request.url
                for call in responses.calls
            )
        )
