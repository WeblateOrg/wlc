# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Package facade tests."""

from unittest import TestCase

import wlc
from wlc import (
    API_URL as ROOT_API_URL,
)
from wlc import (
    USER_AGENT as ROOT_USER_AGENT,
)
from wlc import (
    Component as RootComponent,
)
from wlc import (
    Project as RootProject,
)
from wlc import (
    Translation as RootTranslation,
)
from wlc import (
    Unit as RootUnit,
)
from wlc import (
    Weblate as RootWeblate,
)
from wlc import (
    WeblateException as RootWeblateException,
)
from wlc.client import Weblate
from wlc.const import API_URL, USER_AGENT
from wlc.exceptions import WeblateException
from wlc.models import Component, Project, Translation, Unit


class PackageFacadeTestCase(TestCase):
    """Tests for the package-level compatibility facade."""

    def test_root_reexports_objects(self) -> None:
        """Representative API objects remain importable from the package root."""
        self.assertIs(RootWeblate, Weblate)
        self.assertIs(RootProject, Project)
        self.assertIs(RootComponent, Component)
        self.assertIs(RootTranslation, Translation)
        self.assertIs(RootUnit, Unit)
        self.assertIs(RootWeblateException, WeblateException)

    def test_root_reexports_constants(self) -> None:
        """Representative constants remain available from the package root."""
        self.assertEqual(ROOT_API_URL, API_URL)
        self.assertEqual(ROOT_USER_AGENT, USER_AGENT)
        self.assertEqual(ROOT_USER_AGENT, f"wlc/{wlc.__version__}")

    def test_root_all_lists_public_symbols(self) -> None:
        """The package facade declares the expected public API."""
        self.assertIn("Weblate", wlc.__all__)
        self.assertIn("Project", wlc.__all__)
        self.assertIn("Component", wlc.__all__)
        self.assertIn("Translation", wlc.__all__)
        self.assertIn("Unit", wlc.__all__)
