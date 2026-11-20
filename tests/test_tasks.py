# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Queued API operations and their CLI outcomes."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

from contextlib import redirect_stderr
from io import BytesIO, StringIO, TextIOWrapper
from typing import cast
from unittest.mock import patch

import responses

from wlc import Weblate, WeblateException, WeblateTaskTimeoutError
from wlc.config import WeblateConfig, WLCConfigurationError
from wlc.main import main

from .test_base import CLITestBase

API = "http://127.0.0.1:8000/api/"
TASK = API + "tasks/123/"
COMPONENT = API + "components/hello/weblate/"
TRANSLATION = API + "translations/hello/weblate/cs/"
REPOSITORY = API + "projects/hello/repository/"


class TaskTest(CLITestBase):
    """Exercise status handling through real client request dispatch."""

    def setUp(self) -> None:
        super().setUp()
        self.client = Weblate(url=API, key="KEY")
        responses.add(responses.GET, TASK, json={"completed": True, "result": None})

    def finish(self, result: object) -> None:
        responses.replace(
            responses.GET, TASK, json={"completed": True, "result": result}
        )

    def queue(self, method: str, url: str, **fields: object) -> None:
        responses.replace(method, url, status=202, json={"task_url": TASK, **fields})

    def test_poll_until_completed(self) -> None:
        responses.replace(responses.GET, TASK, json={"completed": False, "result": 20})
        responses.add(responses.GET, TASK, json={"completed": True, "result": None})
        with patch("wlc.client.sleep") as sleep:
            self.assertIsNone(self.client.wait_for_task(TASK))
        sleep.assert_called_once_with(1)
        self.assertEqual(len(responses.calls), 2)
        for call in responses.calls:
            self.assertEqual(call.request.headers["Authorization"], "Token KEY")

    def test_invalid_status(self) -> None:
        for status in ([], {"completed": 1}, {"completed": True}):
            with self.subTest(status=status):
                responses.replace(responses.GET, TASK, json=status)
                with self.assertRaises(WeblateException):
                    self.client.wait_for_task(TASK)

    def test_repository_scope(self) -> None:
        self.queue(
            responses.POST,
            REPOSITORY,
            included_components=["hello/weblate"],
            skipped_components=[],
        )
        self.finish({"result": True, "skipped_components": ["hello/other"]})
        self.assertEqual(
            self.client.get_project("hello").commit(),
            {
                "result": True,
                "included_components": ["hello/weblate"],
                "skipped_components": ["hello/other"],
            },
        )
        self.finish("worker unavailable")
        self.assertEqual(
            self.execute(["commit", "hello"], expected=1), "Error: worker unavailable\n"
        )
        self.finish(
            {
                "result": False,
                "completion_message": {"level": "error", "text": "Merge failed"},
            }
        )
        self.assertEqual(
            self.execute(["pull", "hello"], expected=1),
            "Error: Failed to pull changes!\nMerge failed\n",
        )

    def test_delete(self) -> None:
        self.queue(responses.DELETE, COMPONENT)
        self.assertEqual(self.execute(["delete", "hello/weblate"]), "")
        self.queue(responses.DELETE, TRANSLATION)
        self.finish({"detail": "Removal failed"})
        self.assertEqual(
            self.execute(["delete", "hello/weblate/cs"], expected=1),
            "Error: Removal failed\n",
        )
        responses.replace(responses.DELETE, TRANSLATION, status=204)
        self.assertEqual(self.execute(["delete", "hello/weblate/cs"]), "")
        self.assertEqual(sum(call.request.url == TASK for call in responses.calls), 2)

    def test_upload(self) -> None:
        self.queue(responses.POST, TRANSLATION + "file/")
        counts = {
            "count": 2,
            "result": True,
            "total": 2,
            "accepted": 2,
            "not_found": 0,
            "skipped": 0,
            "upload_warnings": [],
        }
        self.finish(counts)
        self.assertEqual(
            self.client.get_translation("hello/weblate/cs").upload(b"test"), counts
        )
        self.finish({"detail": "Invalid translation file"})
        with TextIOWrapper(BytesIO(b"test"), encoding="utf-8") as stdin:
            self.assertEqual(
                self.execute(["upload", "hello/weblate/cs"], stdin=stdin, expected=1),
                "Error: Invalid translation file\n",
            )

    def test_translation_creation(self) -> None:
        self.queue(responses.POST, COMPONENT + "translations/")
        component = self.client.get_component("hello/weblate")
        self.finish({"url": TRANSLATION})
        self.assertEqual(
            component.add_translation("cs"), {"data": self.client.get(TRANSLATION)}
        )
        for result, message in (
            ({"detail": "Creation failed"}, "Creation failed"),
            ({"url": "https://elsewhere.invalid/api/"}, "outside the configured"),
            (None, "Unexpected task result"),
        ):
            with self.subTest(result=result):
                self.finish(result)
                with self.assertRaisesRegex(WeblateException, message):
                    component.add_translation("cs")
                self.assertEqual(responses.calls[-1].request.url, TASK)
        self.finish({"url": TRANSLATION})
        responses.replace(responses.GET, TRANSLATION, json=[])
        with self.assertRaisesRegex(WeblateException, "Invalid translation response"):
            component.add_translation("cs")

    def test_invalid_submission(self) -> None:
        project = self.client.get_project("hello")
        for status, body, message in (
            (202, [], "Invalid operation response"),
            (202, {}, "no valid task URL"),
            (202, {"task_url": "https://elsewhere.invalid/"}, "outside the configured"),
            (423, {"task_url": TASK}, "HTTP error 423"),
        ):
            with self.subTest(body=body):
                responses.replace(responses.POST, REPOSITORY, status=status, json=body)
                before = len(responses.calls)
                with self.assertRaisesRegex(WeblateException, message):
                    project.commit()
                self.assertEqual(len(responses.calls), before + 1)

    def test_poll_failure_does_not_repeat_submission(self) -> None:
        project = self.client.get_project("hello")
        self.queue(responses.POST, REPOSITORY)
        responses.replace(responses.GET, TASK, status=404)
        with self.assertRaisesRegex(WeblateException, "Object not found"):
            project.commit()
        responses.replace(responses.GET, TASK, json={"completed": False})
        with (
            patch("wlc.client.sleep", side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            project.commit()
        self.assertEqual(
            [call.request.method for call in responses.calls],
            ["GET", "POST", "GET", "POST", "GET"],
        )

    def test_timeout_settings(self) -> None:
        self.assertEqual(self.client.task_timeout, 1800)
        config = WeblateConfig("custom")
        self.assertEqual(Weblate(config=config).task_timeout, 1800)
        config.set("custom", "task_timeout", "77")
        self.assertEqual(Weblate(config=config).task_timeout, 77)
        self.assertEqual(Weblate(config=config, task_timeout=0).task_timeout, 0)
        for invalid in ("-1", "1.5", ""):
            config.set("custom", "task_timeout", invalid)
            with (
                self.subTest(invalid=invalid),
                self.assertRaises(WLCConfigurationError),
            ):
                Weblate(config=config)
        for value in (-1, True, 0.5):
            with self.subTest(value=value):
                with self.assertRaisesRegex(WeblateException, "nonnegative integer"):
                    Weblate(task_timeout=cast("int", value))
                with self.assertRaisesRegex(WeblateException, "nonnegative integer"):
                    self.client.wait_for_task(TASK, timeout=cast("int", value))
        self.assertFalse(responses.calls)

    def test_expiry_and_resume(self) -> None:
        responses.replace(responses.GET, TASK, json={"completed": False})
        with (
            patch(
                "wlc.client.monotonic_ns",
                side_effect=[0, 0, 750_000_000, 1_000_000_000],
            ),
            patch("wlc.client.sleep") as sleep,
            self.assertRaises(WeblateTaskTimeoutError) as caught,
        ):
            self.client.wait_for_task(TASK, timeout=1)
        sleep.assert_called_once_with(0.25)
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(caught.exception.task_url, TASK)
        self.finish("done")
        self.assertEqual(self.client.wait_for_task(caught.exception.task_url), "done")

    def test_late_poll(self) -> None:
        for completed in (True, False):
            with (
                self.subTest(completed=completed),
                patch("wlc.client.monotonic_ns", side_effect=[0, 0, 10**10]),
                patch.object(
                    self.client,
                    "get",
                    return_value={"completed": completed, "result": "done"},
                ) as get,
            ):
                if completed:
                    self.assertEqual(self.client.wait_for_task(TASK, timeout=1), "done")
                else:
                    with self.assertRaises(WeblateTaskTimeoutError):
                        self.client.wait_for_task(TASK, timeout=1)
                get.assert_called_once_with(TASK)

    def test_cli_timeout(self) -> None:
        self.queue(responses.POST, REPOSITORY)
        responses.replace(responses.GET, TASK, json={"completed": False})
        with (
            patch("wlc.client.monotonic_ns", side_effect=[0, 0, 10**9]),
            redirect_stderr(StringIO()) as stderr,
        ):
            result = main(args=["--task-timeout", "1", "pull", "hello"], settings=())
        self.assertEqual(result, 1)
        self.assertIn("server task may still be running", stderr.getvalue())
        self.assertIn(TASK, stderr.getvalue())
        responses.replace(responses.GET, TASK, json={"completed": False})
        responses.add(
            responses.GET, TASK, json={"completed": True, "result": {"result": True}}
        )
        with (
            patch("wlc.client.monotonic_ns", side_effect=AssertionError),
            patch("wlc.client.sleep") as sleep,
        ):
            self.assertEqual(
                self.execute(
                    ["--task-timeout", "0", "pull", "hello"],
                    settings=[("weblate", "task_timeout", "1")],
                ),
                "",
            )
        sleep.assert_called_once_with(1)
        self.assertIn(
            "task_timeout",
            str(self.execute(["--task-timeout", "-1", "pull", "hello"], expected=1)),
        )

    def test_immediate_response_with_task_url(self) -> None:
        project = self.client.get_project("hello")
        data = {"result": True, "task_url": TASK}
        responses.replace(responses.POST, REPOSITORY, status=200, json=data)
        with patch.object(
            self.client, "invoke_request", wraps=self.client.invoke_request
        ) as request:
            self.assertEqual(project.pull(), data)
        request.assert_called_once_with("post", REPOSITORY, data={"operation": "pull"})
