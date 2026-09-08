# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Download command security tests."""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import responses

from wlc import Component, Weblate

from .test_main import CLITestBase


class TestDownloadSecurity(CLITestBase):
    """Download destination security tests."""

    def test_component_download_preserves_repository_slug(self) -> None:
        """The archive must belong to the requested component, not a sibling."""
        base_url = "http://127.0.0.1:8000/api/"
        component_url = f"{base_url}components/hello/docs_repository/"
        responses.get(
            component_url,
            json={
                "url": component_url,
                "slug": "docs_repository",
                "repository_url": f"{component_url}repository/",
                "project": {
                    "url": f"{base_url}projects/hello/",
                    "slug": "hello",
                },
                "category": None,
                "is_glossary": False,
            },
        )
        correct = responses.get(f"{component_url}file/", body=b"correct archive")
        decoy = responses.get(
            f"{base_url}components/hello/docs_file/file/", body=b"decoy archive"
        )

        with TemporaryDirectory() as directory:
            output = self.execute(
                ["download", "hello/docs_repository", "--output", directory]
            )
            archive = Path(directory) / "hello-docs_repository.zip"
            self.assertEqual(archive.read_bytes(), b"correct archive")

        self.assertIn(
            "downloaded translations for component: hello/docs_repository", output
        )
        self.assertEqual(correct.call_count, 1)
        self.assertEqual(decoy.call_count, 0)

    def create_symlink(self, target: str | Path, link: Path) -> None:
        """Create a symlink or skip on Windows without symlink privileges."""
        try:
            link.symlink_to(target)
        except OSError:
            if os.name == "nt":
                self.skipTest("Symlink creation is not permitted")
            raise

    def test_component_rejects_symlink(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            output_directory = root / "repository"
            output_directory.mkdir()
            victim = root / "victim"
            victim.write_bytes(b"original")
            destination = output_directory / "hello-weblate.zip"
            self.create_symlink("../victim", destination)

            output = self.execute(
                ["download", "hello/weblate", "--output", str(output_directory)],
                expected=1,
            )

            self.assertIn("Refusing to write downloaded file through symlink", output)
            self.assertTrue(destination.is_symlink())
            self.assertEqual(victim.read_bytes(), b"original")

    def test_translation_rejects_symlink(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            victim = root / "victim"
            victim.write_bytes(b"original")
            destination = root / "translation.po"
            self.create_symlink("victim", destination)

            output = self.execute(
                ["download", "hello/weblate/cs", "--output", str(destination)],
                expected=1,
            )

            self.assertIn("Refusing to write downloaded file through symlink", output)
            self.assertTrue(destination.is_symlink())
            self.assertEqual(victim.read_bytes(), b"original")

    def test_rejects_non_regular_destination(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            output_directory = Path(tmpdirname)
            destination = output_directory / "hello-weblate.zip"
            destination.mkdir()

            output = self.execute(
                ["download", "hello/weblate", "--output", str(output_directory)],
                expected=1,
            )

            self.assertIn(
                "Refusing to write downloaded file to non-regular path", output
            )
            self.assertTrue(destination.is_dir())

    def test_does_not_follow_racing_symlink(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            output_directory = root / "repository"
            output_directory.mkdir()
            victim = root / "victim"
            victim.write_bytes(b"original")
            destination = output_directory / "hello-weblate.zip"
            self.create_symlink("../victim", destination)

            with patch("wlc.main._download_destination_stat", return_value=None):
                self.execute(
                    [
                        "download",
                        "hello/weblate",
                        "--output",
                        str(output_directory),
                    ]
                )

            self.assertFalse(destination.is_symlink())
            self.assertNotEqual(destination.read_bytes(), b"original")
            self.assertEqual(victim.read_bytes(), b"original")

    def test_supports_long_destination_basename(self) -> None:
        if os.name == "nt":
            self.skipTest("Test basenames can exceed the legacy Windows path limit")

        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            for basename in ("a" * 250, "é" * 120):
                with self.subTest(basename=basename[:10]):
                    destination = root / basename
                    self.execute(
                        [
                            "download",
                            "hello/weblate/cs",
                            "--output",
                            str(destination),
                        ]
                    )
                    self.assertTrue(destination.is_file())

    def test_replaces_regular_file(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            output_directory = Path(tmpdirname)
            destination = output_directory / "hello-weblate.zip"
            destination.write_bytes(b"old content")
            destination.chmod(0o640)
            original_stat = destination.stat()

            self.execute(
                ["download", "hello/weblate", "--output", str(output_directory)]
            )

            self.assertNotEqual(destination.read_bytes(), b"old content")
            self.assertEqual(destination.stat().st_ino, original_stat.st_ino)
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o640)

    def test_updates_existing_file_without_temporary_inode(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            destination = Path(tmpdirname) / "translation.po"
            destination.write_bytes(b"old content")

            with patch(
                "wlc.main._open_download_temporary",
                side_effect=OSError(errno.ENOSPC, "No space left on device"),
            ) as open_temporary:
                self.execute(
                    [
                        "download",
                        "hello/weblate/cs",
                        "--output",
                        str(destination),
                    ]
                )

            open_temporary.assert_not_called()
            self.assertNotEqual(destination.read_bytes(), b"old content")

    def test_replaces_hard_link_without_modifying_target(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            output_directory = root / "repository"
            output_directory.mkdir()
            victim = root / "victim"
            victim.write_bytes(b"original")
            destination = output_directory / "hello-weblate.zip"
            destination.hardlink_to(victim)

            self.execute(
                ["download", "hello/weblate", "--output", str(output_directory)]
            )

            self.assertNotEqual(destination.read_bytes(), b"original")
            self.assertEqual(victim.read_bytes(), b"original")
            self.assertFalse(destination.samefile(victim))

    def test_updates_writable_file_in_protected_directory(self) -> None:
        if os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() == 0:
            self.skipTest("POSIX permissions require an unprivileged user")

        with TemporaryDirectory() as tmpdirname:
            output_directory = Path(tmpdirname) / "protected"
            output_directory.mkdir()
            destination = output_directory / "translation.po"
            destination.write_bytes(b"old content")
            destination.chmod(0o600)
            output_directory.chmod(0o500)
            try:
                self.execute(
                    [
                        "download",
                        "hello/weblate/cs",
                        "--output",
                        str(destination),
                    ]
                )
            finally:
                output_directory.chmod(0o700)

            self.assertNotEqual(destination.read_bytes(), b"old content")

    def test_rejects_replaced_destination(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            destination = root / "translation.po"
            destination.write_bytes(b"original")
            replacement = root / "replacement"
            replacement.write_bytes(b"replacement")
            original_destination = root / "original-destination"
            original_open = os.open
            swapped = False

            def replace_before_open(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal swapped
                if Path(path).name == destination.name and not swapped:
                    swapped = True
                    destination.rename(original_destination)
                    replacement.rename(destination)
                return original_open(path, flags, mode, dir_fd=dir_fd)

            with patch("wlc.main.os.open", side_effect=replace_before_open):
                output = self.execute(
                    [
                        "download",
                        "hello/weblate/cs",
                        "--output",
                        str(destination),
                    ],
                    expected=1,
                )

            self.assertIn("destination changed", output)
            self.assertEqual(destination.read_bytes(), b"replacement")
            self.assertEqual(original_destination.read_bytes(), b"original")

    def test_failure_cleans_temporary_file(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            output_directory = Path(tmpdirname)
            with (
                patch(
                    "wlc.main._replace_download_file",
                    side_effect=OSError("replace failed"),
                ),
                self.assertRaisesRegex(OSError, "replace failed"),
            ):
                self.execute(
                    [
                        "download",
                        "hello/weblate",
                        "--output",
                        str(output_directory),
                    ]
                )

            self.assertEqual(list(output_directory.iterdir()), [])


class TestComponentDownload(TestCase):
    """Component archive URL tests."""

    def test_download_preserves_url_identifiers(self) -> None:
        """Only the repository endpoint suffix changes when downloading."""
        cases = (
            ("http://127.0.0.1:8000/api/", "hello/docs"),
            ("http://127.0.0.1:8000/api/", "hello/docs_repository"),
            ("http://127.0.0.1:8000/api/", "my_repository/docs"),
            ("http://127.0.0.1:8000/repository/api/", "hello/docs"),
            ("https://repository.example/api/", "hello/docs"),
        )
        for base_url, slug in cases:
            for convert in (None, "csv"):
                with (
                    self.subTest(base_url=base_url, slug=slug, convert=convert),
                    responses.RequestsMock() as mock,
                ):
                    url = f"{base_url}components/{slug}/"
                    component = Component(
                        Weblate(url=base_url, key="synthetic"),
                        url=url,
                        repository_url=f"{url}repository/",
                    )
                    expected_url = f"{url}file/"
                    if convert is not None:
                        expected_url += "?format=csv"
                    mock.get(expected_url, body=b"correct archive")

                    self.assertEqual(component.download(convert), b"correct archive")
                    self.assertEqual(len(mock.calls), 1)
                    self.assertEqual(mock.calls[0].request.url, expected_url)
