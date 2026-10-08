# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test lazy object loading, equality, and mapping operations."""

from __future__ import annotations

from collections import UserDict
from copy import copy
from unittest.mock import patch

from wlc import (
    Component,
    Project,
    Statistics,
    Weblate,
)

from .test_base import APITest


class LazyObjectTest(APITest):
    """Test lazy object loading and representation."""

    def test_ensure_loaded(self) -> None:
        """Test lazy loading of attributes."""
        obj = Weblate().get_object("hello")
        obj.ensure_loaded("missing")
        obj.ensure_loaded("missing")
        with self.assertRaises(AttributeError):
            print(obj.missing)  # ruff: ignore[print]

    def test_setattrvalue(self) -> None:
        """Test lazy loading of attributes."""
        obj = Weblate().get_object("hello")
        with self.assertRaises(AttributeError):
            obj.setattrvalue("missing", "")

    def test_repr(self) -> None:
        """Test str and repr behavior."""
        obj = Weblate().get_object("hello")
        self.assertIn("'slug': 'hello'", repr(obj))
        self.assertIn("'slug': 'hello'", str(obj))


class LazyObjectEqualityTest(APITest):
    """Tests for equality behavior on lazy objects."""

    def test_equality_uses_additional_attributes(self) -> None:
        """Objects with different deferred attributes should not compare equal."""
        weblate = Weblate()
        first = Project(
            weblate,
            "projects/hello/",
            name="Hello",
            slug="hello",
            web="https://weblate.org/",
            web_url="https://weblate.org/projects/hello/",
            components_list_url="projects/hello/components/",
        )
        second = Project(
            weblate,
            "projects/hello/",
            name="Hello",
            slug="hello",
            web="https://weblate.org/",
            web_url="https://weblate.org/projects/hello/",
            categories_url="projects/hello/categories/",
        )

        self.assertNotEqual(first, second)

    def test_equality_does_not_refresh_unloaded_objects(self) -> None:
        """Comparing unloaded objects should not trigger a refresh."""
        weblate = Weblate()
        first = Project(weblate, "projects/hello/")
        second = Project(weblate, "projects/hello/")
        with (
            patch.object(
                first, "refresh", side_effect=AssertionError("refresh should not run")
            ) as first_refresh,
            patch.object(
                second, "refresh", side_effect=AssertionError("refresh should not run")
            ) as second_refresh,
        ):
            self.assertEqual(first, second)
            first_refresh.assert_not_called()
            second_refresh.assert_not_called()

    def test_lazy_objects_are_not_hashable(self) -> None:
        """Lazy objects should stay unhashable because equality is mutable."""
        obj = Project(Weblate(), "projects/hello/")

        with self.assertRaises(TypeError):
            hash(obj)

    def test_dict_comparison_does_not_refresh_unloaded_objects(self) -> None:
        """Comparing unloaded objects to dicts should stay local."""
        obj = Project(Weblate(), "projects/hello/")
        with patch.object(
            obj, "refresh", side_effect=AssertionError("refresh should not run")
        ) as refresh:
            self.assertEqual(obj, {"url": "projects/hello/"})
            self.assertEqual({"url": "projects/hello/"}, obj)
            self.assertEqual(obj, UserDict({"url": "projects/hello/"}))
            self.assertEqual(UserDict({"url": "projects/hello/"}), obj)
            self.assertNotEqual(obj, UserDict())
            refresh.assert_not_called()

    def test_dict_comparison_uses_lazy_data(self) -> None:
        """Dict comparison should use lazy object data, not dict base storage."""
        obj = Project(
            Weblate(),
            "projects/hello/",
            name="Hello",
            slug="hello",
            web="https://weblate.org/",
            web_url="https://weblate.org/projects/hello/",
        )

        self.assertEqual(
            obj,
            {
                "url": "projects/hello/",
                "name": "Hello",
                "slug": "hello",
                "web": "https://weblate.org/",
                "web_url": "https://weblate.org/projects/hello/",
            },
        )


class LazyObjectMappingTest(APITest):
    """Mapping operations should use the loaded API fields."""

    def test_stored_values_and_urls(self) -> None:
        """Stored lookup should preserve values and avoid unnecessary fetches."""
        # Exercise the internal lookup shared by the public API methods.
        # pylint: disable=protected-access
        obj = Component(
            Weblate(),
            "components/hello/weblate/",
            priority=100,
            extra={"enabled": True},
            repository_url="components/hello/weblate/repository/",
        )
        with patch.object(obj, "refresh") as refresh:
            self.assertEqual(
                obj._get_stored("priority"),  # ruff: ignore[private-member-access]
                100,
            )
            self.assertEqual(
                obj._get_stored("extra"),  # ruff: ignore[private-member-access]
                {"enabled": True},
            )
            self.assertEqual(
                obj._get_stored_url("repository_url"),  # ruff: ignore[private-member-access]
                "components/hello/weblate/repository/",
            )
            refresh.assert_not_called()

    def test_mapping_lookups_preserve_dynamic_field_types(self) -> None:
        """Typed callers should be able to use lookups as concrete field values."""

        def get_name(project: Project) -> str:
            return project.get("name", "")

        def pop_name(project: Project) -> str:
            return project.pop("name", "")

        def setdefault_name(project: Project) -> str:
            return project.setdefault("name", "Default")

        obj = Project(Weblate(), "projects/hello/", name="Hello")
        with patch.object(obj, "refresh") as refresh:
            self.assertEqual(get_name(obj), "Hello")
            self.assertEqual(setdefault_name(obj), "Hello")
            self.assertEqual(pop_name(obj), "Hello")
            self.assertEqual(get_name(obj), "")
            self.assertEqual(pop_name(obj), "")
            self.assertEqual(setdefault_name(obj), "Default")
            self.assertEqual(get_name(obj), "Default")
            refresh.assert_not_called()

    def test_mapping_operations_share_storage(self) -> None:
        """Mapping writes and attribute writes should share loaded fields."""
        obj = Project(Weblate(), "projects/hello/", name="Hello")
        self.assertIsInstance(obj, UserDict)
        with patch.object(obj, "refresh") as refresh:
            self.assertIn("name", obj)
            self.assertEqual(obj.get("name"), "Hello")
            self.assertEqual(obj.get("missing", "default"), "default")
            self.assertEqual(list(obj), ["name", "url"])
            obj["name"] = "Updated"
            self.assertEqual(obj.name, "Updated")
            obj.update(name="Again")
            self.assertEqual(obj["name"], "Again")
            obj.setattrvalue("name", "Final")
            self.assertEqual(obj.get("name"), "Final")
            del obj["name"]
            self.assertNotIn("name", obj)
            refresh.assert_not_called()

    def test_copy_and_snapshot_are_independent(self) -> None:
        """Copies should retain model state and independent field storage."""
        obj = Project(Weblate(), "projects/hello/", name="Hello")
        with patch.object(obj, "refresh") as refresh:
            snapshot = obj.get_data()
            self.assertIsInstance(snapshot, dict)
            cloned = copy(obj)
            self.assertEqual(cloned, obj)
            cloned["name"] = "Changed"
            snapshot["name"] = "Snapshot"
            self.assertEqual(obj.name, "Hello")
            self.assertEqual(cloned.name, "Changed")
            refresh.assert_not_called()

    def test_keyed_access_still_loads_missing_fields(self) -> None:
        """Known unloaded fields should still load through keyed access."""
        obj = Project(Weblate(), "projects/hello/")
        self.assertEqual(obj["name"], "Hello")
        self.assertEqual(obj.get("name"), "Hello")
        self.assertIn("name", obj)

    def test_get_does_not_load_missing_fields(self) -> None:
        """Known and unknown missing fields should use defaults on all versions."""
        obj = Project(Weblate(), "projects/hello/")
        with patch.object(obj, "refresh") as refresh:
            self.assertIsNone(obj.get("name"))
            self.assertEqual(obj.get("name", "default"), "default")
            self.assertIsNone(obj.get("missing"))
            self.assertEqual(obj.get("missing", "default"), "default")
            refresh.assert_not_called()

    def test_pop_and_setdefault_use_loaded_fields(self) -> None:
        """Defaults should work for absent fields without lazy lookups."""
        obj = Statistics(Weblate(), total=3)
        with patch.object(obj, "refresh") as refresh:
            self.assertEqual(obj.pop("translated", 0), 0)
            with self.assertRaises(KeyError):
                obj.pop("translated")
            self.assertEqual(obj.setdefault("translated", 0), 0)
            self.assertEqual(obj.translated, 0)
            self.assertEqual(obj.setdefault("translated", 10), 0)
            self.assertEqual(obj.pop("translated"), 0)
            self.assertIsNone(obj.setdefault("missing"))
            self.assertIsNone(obj.pop("missing", "default"))
            self.assertIsNone(obj.pop("missing", None))
            self.assertEqual(obj.total, 3)
            refresh.assert_not_called()

    def test_popitem_and_clear_use_loaded_fields(self) -> None:
        """Removing loaded fields should never refresh the object."""
        obj = Project(Weblate(), "projects/hello/")
        with patch.object(obj, "refresh") as refresh:
            self.assertEqual(obj.popitem(), ("url", "projects/hello/"))
            with self.assertRaises(KeyError):
                obj.popitem()
            obj.update(name="Hello", slug="hello")
            obj.clear()
            self.assertEqual(obj.get_data(), {})
            refresh.assert_not_called()

    def test_unions_return_plain_dictionaries(self) -> None:
        """Unions should preserve precedence and avoid model construction."""
        obj = Project(Weblate(), "projects/hello/", name="Hello")
        original = obj.get_data()
        with patch.object(obj, "refresh") as refresh:
            for other in ({"name": "Updated"}, UserDict({"name": "Updated"})):
                with self.subTest(other=type(other)):
                    merged = obj | other
                    reverse = other | obj
                    self.assertIs(type(merged), dict)
                    self.assertIs(type(reverse), dict)
                    self.assertEqual(merged, {**original, "name": "Updated"})
                    self.assertEqual(reverse, original)
            self.assertEqual(obj.get_data(), original)
            peer = Project(obj.weblate, "projects/other/", name="Other")
            self.assertEqual(obj | peer, peer.get_data())
            with self.assertRaises(TypeError):
                _ = obj | []
            with self.assertRaises(TypeError):
                _ = [] | obj
            obj |= {"name": "Updated"}
            self.assertEqual(obj.name, "Updated")
            refresh.assert_not_called()
