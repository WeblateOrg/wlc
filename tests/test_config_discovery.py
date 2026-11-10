# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Project configuration discovery boundaries and explicit selection."""

from __future__ import annotations

import os
import stat
from contextlib import ExitStack
from functools import partialmethod
from itertools import combinations
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import Mock, patch

import responses

from wlc.config import WeblateConfig, WLCConfigurationError

from .test_base import CLITestBase

PROJECT_URL = "http://127.0.0.1:8000/api/"
PROJECT_CONFIG = f"[weblate]\nurl = {PROJECT_URL}\n"


class ProjectDiscoveryBase(TestCase):
    """Isolated checkout and link creation for discovery boundary tests."""

    def setUp(self) -> None:
        """Create a private checkout with an isolated working directory."""
        self.contexts = ExitStack()
        self.addCleanup(self.contexts.close)
        # Match Path.cwd(), which resolves aliases such as macOS /var.
        self.root = Path(self.contexts.enter_context(TemporaryDirectory())).resolve()
        self.repo = self.root / "repo"
        self.nested = self.repo / "nested"
        self.nested.mkdir(parents=True)
        (self.repo / ".git").mkdir()
        self.contexts.enter_context(
            patch("wlc.config.Path.cwd", return_value=self.nested)
        )

    def make_symlink(
        self, path: Path, target: Path, *, directory: bool = False
    ) -> None:
        """Create a link, allowing Windows installations without link privileges."""
        try:
            path.symlink_to(target, target_is_directory=directory)
        except OSError:
            if os.name == "nt":
                self.skipTest("Symlink creation requires Windows privileges")
            raise


class ProjectDiscoveryTest(ProjectDiscoveryBase):
    """Automatic discovery respects directory and file trust boundaries."""

    def test_filename_precedence_and_nearest_file(self) -> None:
        """The nearest file wins, with the established filename precedence."""
        for name in ("weblate.ini", ".weblate.ini", ".weblate"):
            with self.subTest(name=name):
                path = self.repo / name
                path.write_text(PROJECT_CONFIG, encoding="utf-8")
                self.assertEqual(WeblateConfig.find_project_config(), path)
        nearer = self.nested / "weblate.ini"
        nearer.write_text(PROJECT_CONFIG, encoding="utf-8")
        self.assertEqual(WeblateConfig.find_project_config(), nearer)

    def test_repository_roots(self) -> None:
        """Git, worktree, Mercurial, and Subversion roots bound discovery."""
        (self.root / ".weblate").write_text(PROJECT_CONFIG, encoding="utf-8")
        (self.repo / ".git").rmdir()
        for marker, directory in (
            (".git", True),
            (".git", False),
            (".hg", True),
            (".svn", True),
        ):
            with self.subTest(marker=marker, directory=directory):
                path = self.repo / marker
                if directory:
                    path.mkdir()
                else:
                    path.write_text("gitdir: ../worktrees/repo\n", encoding="utf-8")
                self.assertIsNone(WeblateConfig.find_project_config())
                config = self.repo / ".weblate"
                config.write_text(PROJECT_CONFIG, encoding="utf-8")
                self.assertEqual(WeblateConfig.find_project_config(), config)
                config.unlink()
                if directory:
                    path.rmdir()
                else:
                    path.unlink()

    def test_non_repository_marker_files(self) -> None:
        """Only Git uses a regular file as its repository marker."""
        (self.repo / ".git").rmdir()
        for marker in (".hg", ".svn"):
            (self.repo / marker).touch()
        config = self.root / ".weblate"
        config.write_text(PROJECT_CONFIG, encoding="utf-8")
        self.assertEqual(WeblateConfig.find_project_config(), config)

    def test_nested_repository(self) -> None:
        """A nested repository does not inherit the outer repository's file."""
        (self.repo / ".weblate").write_text(PROJECT_CONFIG, encoding="utf-8")
        (self.nested / ".git").mkdir()
        self.assertIsNone(WeblateConfig.find_project_config())
        config = self.nested / ".weblate"
        config.write_text(PROJECT_CONFIG, encoding="utf-8")
        self.assertEqual(WeblateConfig.find_project_config(), config)

    def test_non_regular_config_is_ignored(self) -> None:
        """A directory with a config filename does not hide a regular file."""
        (self.repo / ".weblate").mkdir()
        config = self.repo / ".weblate.ini"
        config.write_text(PROJECT_CONFIG, encoding="utf-8")
        self.assertEqual(WeblateConfig.find_project_config(), config)

    @skipUnless(os.name == "posix", "Requires POSIX permission bits")
    def test_world_writable_directory(self) -> None:
        """World-write, including sticky directories, stops discovery."""
        parent_config = self.repo / ".weblate"
        parent_config.write_text(PROJECT_CONFIG, encoding="utf-8")
        for mode in (0o777, 0o1777):
            with self.subTest(mode=mode):
                self.nested.chmod(mode)
                self.assertIsNone(WeblateConfig.find_project_config())
                config = self.nested / ".weblate"
                config.write_text(PROJECT_CONFIG, encoding="utf-8")
                with self.assertRaisesRegex(WLCConfigurationError, "--project-config"):
                    WeblateConfig.find_project_config()
                config.unlink()

    @skipUnless(os.name == "posix", "Requires POSIX permission bits")
    def test_world_writable_file(self) -> None:
        """An unsafe candidate produces an error rather than endpoint fallback."""
        config = self.repo / ".weblate"
        config.write_text(PROJECT_CONFIG, encoding="utf-8")
        config.chmod(0o666)
        with self.assertRaisesRegex(
            WLCConfigurationError, "Unsafe project configuration"
        ):
            WeblateConfig.find_project_config()

    @skipUnless(os.name == "posix", "Requires POSIX permission bits")
    def test_group_write_is_supported(self) -> None:
        """Group collaboration remains available for trusted owners."""
        self.repo.chmod(0o770)
        config = self.repo / ".weblate"
        config.write_text(PROJECT_CONFIG, encoding="utf-8")
        config.chmod(0o660)
        self.assertEqual(WeblateConfig.find_project_config(), config)

    @skipUnless(os.name == "posix", "Requires POSIX permission bits")
    def test_private_child_of_world_writable_directory(self) -> None:
        """A safe nearer file remains usable beneath an unsafe ancestor."""
        (self.repo / ".git").rmdir()
        self.root.chmod(0o1777)
        (self.root / ".weblate").write_text(PROJECT_CONFIG, encoding="utf-8")
        config = self.repo / ".weblate"
        config.write_text(PROJECT_CONFIG, encoding="utf-8")
        self.assertEqual(WeblateConfig.find_project_config(), config)

    def test_owner_policy(self) -> None:
        """Only root and the effective user are accepted on POSIX systems."""
        config = self.nested / ".weblate"
        config.write_text(PROJECT_CONFIG, encoding="utf-8")
        original_stat = Path.stat
        for uid, expected in ((0, True), (1234, True), (5678, False)):

            def owner_stat(
                path: Path, *, follow_symlinks: bool = True, owner: int = uid
            ) -> os.stat_result:
                info = original_stat(path, follow_symlinks=follow_symlinks)
                values = list(info)
                # Isolate ownership from Windows' synthetic write-permission bits.
                values[0] = info.st_mode & ~stat.S_IWOTH
                values[4] = owner
                return os.stat_result(values)

            with (
                self.subTest(uid=uid),
                patch("wlc.config.CHECK_PROJECT_PERMISSIONS", new=True),
                patch("wlc.config.os.geteuid", return_value=1234, create=True),
                patch.object(Path, "stat", owner_stat),
                # Windows lstat() does not delegate to Path.stat().
                patch.object(
                    Path, "lstat", partialmethod(owner_stat, follow_symlinks=False)
                ),
            ):
                if expected:
                    self.assertEqual(WeblateConfig.find_project_config(), config)
                else:
                    with self.assertRaisesRegex(
                        WLCConfigurationError, "--project-config"
                    ):
                        WeblateConfig.find_project_config()

    def test_foreign_ownership_boundary(self) -> None:
        """Foreign ownership stops directory search and rejects candidate files."""
        original_stat = Path.stat
        foreign_path = self.repo

        def owner_stat(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
            info = original_stat(path, follow_symlinks=follow_symlinks)
            values = list(info)
            values[0] = info.st_mode & ~stat.S_IWOTH
            values[4] = 5678 if path == foreign_path else 1234
            return os.stat_result(values)

        with (
            patch("wlc.config.CHECK_PROJECT_PERMISSIONS", new=True),
            patch("wlc.config.os.geteuid", return_value=1234, create=True),
            patch.object(Path, "stat", owner_stat),
            patch.object(
                Path, "lstat", partialmethod(owner_stat, follow_symlinks=False)
            ),
        ):
            self.assertIsNone(WeblateConfig.find_project_config())
            (self.repo / ".weblate").write_text(PROJECT_CONFIG, encoding="utf-8")
            with self.assertRaisesRegex(WLCConfigurationError, "--project-config"):
                WeblateConfig.find_project_config()
            foreign_path = self.repo / ".weblate"
            with self.assertRaisesRegex(WLCConfigurationError, "--project-config"):
                WeblateConfig.find_project_config()

    def test_windows_policy(self) -> None:
        """Windows uses repository boundaries without POSIX permission checks."""
        (self.root / ".weblate").write_text(PROJECT_CONFIG, encoding="utf-8")
        with (
            patch("wlc.config.CHECK_PROJECT_PERMISSIONS", new=False),
            patch("wlc.config.os.geteuid", create=True) as geteuid,
        ):
            self.assertIsNone(WeblateConfig.find_project_config())
            config = self.repo / ".weblate"
            config.write_text(PROJECT_CONFIG, encoding="utf-8")
            config.chmod(0o666)
            self.assertEqual(WeblateConfig.find_project_config(), config)
            geteuid.assert_not_called()


class ProjectSymlinkTest(ProjectDiscoveryBase):
    """Every directory traversed by a configuration link must be trusted."""

    def test_safe_internal_symlink(self) -> None:
        """Internal configuration links can point into another safe subdirectory."""
        target = self.nested / "settings.ini"
        target.write_text(PROJECT_CONFIG, encoding="utf-8")
        config = self.repo / ".weblate"
        self.make_symlink(config, target)
        self.assertEqual(WeblateConfig.find_project_config(), config)

    def test_safe_internal_symlink_chain(self) -> None:
        """Internal relative links and parent components remain supported."""
        target = self.repo / "settings.ini"
        target.write_text(PROJECT_CONFIG, encoding="utf-8")
        intermediate = self.nested / "settings.ini"
        self.make_symlink(intermediate, Path("../settings.ini"))
        config = self.repo / ".weblate"
        self.make_symlink(config, Path("nested/../nested/settings.ini"))
        self.assertEqual(WeblateConfig.find_project_config(), config)

    def test_repeated_directory_symlink(self) -> None:
        """Reusing a directory alias is not necessarily a symbolic link loop."""
        target = self.repo / "settings.ini"
        target.write_text(PROJECT_CONFIG, encoding="utf-8")
        self.make_symlink(self.repo / "alias", Path(), directory=True)
        config = self.repo / ".weblate"
        self.make_symlink(config, Path("alias/alias/settings.ini"))
        self.assertEqual(WeblateConfig.find_project_config(), config)

    def test_intermediate_external_symlink(self) -> None:
        """A final internal file does not authorize traversal outside the root."""
        target = self.repo / "settings.ini"
        target.write_text(PROJECT_CONFIG, encoding="utf-8")
        intermediate = self.root / "settings.ini"
        self.make_symlink(intermediate, target)
        config = self.repo / ".weblate"
        self.make_symlink(config, intermediate)
        with self.assertRaisesRegex(WLCConfigurationError, "--project-config"):
            WeblateConfig.find_project_config()
        with patch.object(WeblateConfig, "find_config", return_value=None):
            resolved = WeblateConfig()
            resolved.load(project_path=config)
            self.assertEqual(resolved.get_url_key()[0], PROJECT_URL)

    def test_parent_traversal_outside_boundary(self) -> None:
        """Leaving and reentering the root through parent components is rejected."""
        (self.repo / "settings.ini").write_text(PROJECT_CONFIG, encoding="utf-8")
        self.make_symlink(self.repo / ".weblate", Path("../repo/settings.ini"))
        with self.assertRaisesRegex(WLCConfigurationError, "--project-config"):
            WeblateConfig.find_project_config()

    @skipUnless(os.name == "posix", "Requires POSIX permission bits")
    def test_intermediate_world_writable_directory(self) -> None:
        """All directories crossed by a link chain must pass the permission policy."""
        target = self.repo / "settings.ini"
        target.write_text(PROJECT_CONFIG, encoding="utf-8")
        self.make_symlink(self.nested / "settings.ini", target)
        self.make_symlink(self.repo / ".weblate", Path("nested/settings.ini"))
        self.nested.chmod(0o777)
        with (
            patch("wlc.config.Path.cwd", return_value=self.repo),
            self.assertRaisesRegex(WLCConfigurationError, "--project-config"),
        ):
            WeblateConfig.find_project_config()

    @skipUnless(os.name == "posix", "Requires POSIX ownership")
    def test_intermediate_foreign_directory(self) -> None:
        """Foreign-owned intermediate directories cannot disappear in resolution."""
        target = self.repo / "settings.ini"
        target.write_text(PROJECT_CONFIG, encoding="utf-8")
        self.make_symlink(self.nested / "settings.ini", target)
        self.make_symlink(self.repo / ".weblate", Path("nested/settings.ini"))
        original_lstat = Path.lstat

        def foreign_lstat(path: Path) -> os.stat_result:
            values = list(original_lstat(path))
            if path == self.nested:
                values[4] = os.geteuid() + 1
            return os.stat_result(values)

        with (
            patch("wlc.config.Path.cwd", return_value=self.repo),
            patch.object(Path, "lstat", foreign_lstat),
            self.assertRaisesRegex(WLCConfigurationError, "--project-config"),
        ):
            WeblateConfig.find_project_config()

    def test_symlink_loop_during_validation(self) -> None:
        """The component validator detects loops independently of initial stat."""
        config = self.repo / ".weblate"
        self.make_symlink(config, Path(".weblate"))
        with (
            patch.object(WeblateConfig, "_project_file_in", return_value=config),
            self.assertRaisesRegex(WLCConfigurationError, "Symbolic link loop"),
        ):
            WeblateConfig.find_project_config()

    def test_windows_extended_link_targets(self) -> None:
        """Windows link targets compare using ordinary drive and UNC spelling."""
        for target, expected in (
            (r"\\?\C:\repo\settings.ini", r"C:\repo\settings.ini"),
            (r"\\?\UNC\server\share\settings.ini", r"\\server\share\settings.ini"),
            (r"\\?\unc\server\share\settings.ini", r"\\server\share\settings.ini"),
        ):
            with (
                self.subTest(target=target),
                patch.object(Path, "readlink", return_value=PureWindowsPath(target)),
            ):
                # Exercise Windows spelling independently of the host platform.
                # pylint: disable-next=protected-access
                reader = WeblateConfig._project_link_target  # ruff: ignore[private-member-access]
                result = reader(self.repo)
                self.assertEqual(result, Path(expected))

    def test_directory_junction(self) -> None:
        """Windows junction metadata is inspected like an intermediate symlink."""
        target = self.nested / "settings.ini"
        target.write_text(PROJECT_CONFIG, encoding="utf-8")
        junction = self.repo / "junction"
        self.make_symlink(junction, self.nested, directory=True)
        config = self.repo / ".weblate"
        self.make_symlink(config, Path("junction/settings.ini"))
        original_lstat = Path.lstat
        tag = 0xA0000003

        def junction_lstat(path: Path) -> os.stat_result:
            if path == junction:
                return Mock(st_mode=stat.S_IFDIR | 0o755, st_reparse_tag=tag)
            return original_lstat(path)

        with (
            patch.object(stat, "IO_REPARSE_TAG_MOUNT_POINT", tag, create=True),
            patch.object(Path, "lstat", junction_lstat),
        ):
            self.assertEqual(WeblateConfig.find_project_config(), config)

    def test_external_symlink(self) -> None:
        """A link cannot silently import configuration from outside the checkout."""
        target = self.root / "settings.ini"
        target.write_text(PROJECT_CONFIG, encoding="utf-8")
        self.make_symlink(self.repo / ".weblate", target)
        with self.assertRaisesRegex(WLCConfigurationError, "--project-config"):
            WeblateConfig.find_project_config()

    @skipUnless(os.name == "posix", "Requires POSIX permission bits")
    def test_symlink_to_unsafe_directory(self) -> None:
        """Safe file modes do not make a world-writable target directory safe."""
        target = self.nested / "settings.ini"
        target.write_text(PROJECT_CONFIG, encoding="utf-8")
        self.nested.chmod(0o777)
        self.make_symlink(self.repo / ".weblate", target)
        with (
            patch("wlc.config.Path.cwd", return_value=self.repo),
            self.assertRaisesRegex(WLCConfigurationError, "--project-config"),
        ):
            WeblateConfig.find_project_config()

    def test_inspection_failure(self) -> None:
        """Access failures and symlink-resolution failures are handled errors."""
        config = self.repo / ".weblate"
        config.write_text(PROJECT_CONFIG, encoding="utf-8")
        with (
            patch.object(WeblateConfig, "_project_stat", side_effect=PermissionError),
            self.assertRaisesRegex(WLCConfigurationError, "Could not inspect"),
        ):
            WeblateConfig.find_project_config()
        with (
            patch.object(Path, "lstat", side_effect=RuntimeError("Symlink loop")),
            self.assertRaisesRegex(WLCConfigurationError, "Could not inspect"),
        ):
            WeblateConfig.find_project_config()


class ExplicitConfigTest(CLITestBase):
    """CLI selection and library loading preserve configuration source policy."""

    @skipUnless(os.name == "posix", "Requires POSIX permission bits")
    def test_unsafe_discovery_sends_no_request(self) -> None:
        """Unsafe configuration fails before any request uses a fallback server."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            (root / ".git").mkdir()
            config = root / ".weblate"
            config.write_text(PROJECT_CONFIG, encoding="utf-8")
            config.chmod(0o666)
            with (
                patch("wlc.config.Path.cwd", return_value=root),
                patch.object(WeblateConfig, "find_config", return_value=None),
            ):
                output = self.execute(["list-projects"], settings=False, expected=1)
                self.assertIn("Unsafe project configuration", output)
                self.assertIn("--project-config", output)
                self.assertEqual(len(responses.calls), 0)

    def test_project_config_keeps_personal_keys(self) -> None:
        """Explicit project selection keeps scoped keys and project restrictions."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            personal = root / "personal.ini"
            personal.write_text(f"[keys]\n{PROJECT_URL} = KEY\n", encoding="utf-8")
            project = root / "project.ini"
            project.write_text(
                PROJECT_CONFIG + "[insecure_ssl]\nhttps://example.com = yes\n",
                encoding="utf-8",
            )
            project.chmod(0o666)
            with (
                patch.object(WeblateConfig, "find_config", return_value=personal),
                patch.object(WeblateConfig, "find_project_config") as discover,
            ):
                output = self.execute(
                    ["--project-config", str(project), "show", "acl"], settings=False
                )
                self.assertIn("ACL", output)
                self.assertEqual(
                    responses.calls[-1].request.headers["Authorization"], "Token KEY"
                )
                config = WeblateConfig()
                config.load(project_path=project)
                self.assertFalse(
                    config.has_option("insecure_ssl", "https://example.com")
                )
                discover.assert_not_called()

    def test_project_config_requires_url_for_unscoped_keys(self) -> None:
        """Explicit project selection grants no new credential privileges."""
        with TemporaryDirectory() as tmpdirname:
            project = Path(tmpdirname) / "project.ini"
            project.write_text(PROJECT_CONFIG, encoding="utf-8")
            with patch.object(WeblateConfig, "find_config", return_value=None):
                output = self.execute(
                    ["--project-config", str(project), "--key", "KEY", "show", "acl"],
                    settings=False,
                    expected=1,
                )
                self.assertIn("requires --url", output)

    def test_project_config_must_be_read(self) -> None:
        """An explicit project path must exist and be readable."""
        with (
            patch.object(WeblateConfig, "find_config", return_value=None),
            patch("wlc.config.RawConfigParser.read", return_value=[]),
            self.assertRaisesRegex(WLCConfigurationError, "Could not read"),
        ):
            WeblateConfig().load(project_path="missing.ini")

    def test_conflicting_library_paths(self) -> None:
        """Library callers cannot combine the two explicit loading modes."""
        with self.assertRaisesRegex(WLCConfigurationError, "Cannot combine"):
            WeblateConfig().load("explicit.ini", project_path="project.ini")

    def test_no_config_preserves_environment(self) -> None:
        """No-config skips all file reads but keeps URL and key overrides."""
        with (
            patch.object(WeblateConfig, "load") as load,
            patch.dict(os.environ, {"WLC_URL": PROJECT_URL, "WLC_KEY": "KEY"}),
        ):
            output = self.execute(["--no-config", "show", "acl"], settings=False)
            self.assertIn("ACL", output)
            load.assert_not_called()

    def test_no_config_preserves_cli_and_programmatic_settings(self) -> None:
        """File suppression keeps explicit caller instructions available."""
        output = self.execute(
            ["--no-config", "--url", "https://example.net/", "list-projects"],
            settings=False,
        )
        self.assertIn("Hello", output)
        output = self.execute(
            ["--no-config", "list-projects"],
            settings=(("weblate", "url", "https://example.net/"),),
        )
        self.assertIn("Hello", output)

    def test_conflicting_cli_options(self) -> None:
        """CLI modes are mutually exclusive rather than silently overriding."""
        for first, second in combinations(
            (["--config", "a.ini"], ["--project-config", "b.ini"], ["--no-config"]),
            2,
        ):
            with (
                self.subTest(first=first, second=second),
                self.assertRaises(SystemExit),
            ):
                self.execute([*first, *second, "list-projects"])
