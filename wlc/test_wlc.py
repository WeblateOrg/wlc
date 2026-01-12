# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the module."""

from __future__ import annotations

import io
import os
from abc import ABC
from typing import Any, ClassVar

from requests.exceptions import RequestException

from wlc import (
    API_URL,
    Category,
    Change,
    Component,
    Project,
    Translation,
    Unit,
    Weblate,
    WeblateException,
)

from .test_base import APITest


class WeblateErrorTest(APITest):
    """Testing error handling."""

    def test_nonexisting(self) -> None:
        """Test error handling for non-existing objects."""
        with self.assertRaisesRegex(WeblateException, "not found"):
            Weblate().get_object("nonexisting")

    def test_denied(self) -> None:
        """Test permission denied error handling."""
        with self.assertRaisesRegex(WeblateException, "permission"):
            Weblate().get_object("denied")

    def test_denied_json(self) -> None:
        """Test permission denied when posting components."""
        with self.assertRaisesRegex(WeblateException, "Can not create"):
            Weblate().create_component(
                project="denied_json",
                slug="component1",
                name="component1",
                file_format="po",
                filemask="/something",
                repo="a_repo",
            )

    def test_denied_json_510(self) -> None:
        """Test permission denied when posting components."""
        with self.assertRaisesRegex(WeblateException, "This is a required error"):
            Weblate().create_component(
                project="denied_json_510",
                slug="component1",
                name="component1",
                file_format="po",
                filemask="/something",
                repo="a_repo",
            )

    def test_throttled(self) -> None:
        """Test handling of throttling error when listing projects."""
        with self.assertRaisesRegex(
            WeblateException,
            "Throttling.*Limit is 100 requests. Retry after 81818 seconds.",
        ):
            Weblate().get_object("throttled")

    def test_error(self) -> None:
        """Test general server error (HTTP 500) handling."""
        with self.assertRaisesRegex(WeblateException, "500"):
            Weblate().get_object("error")

    def test_oserror(self) -> None:
        """Test handling of OS/request-level errors when listing projects."""
        with self.assertRaises(RequestException):
            Weblate().get_object("io")

    def test_bug(self) -> None:
        """Test listing projects."""
        with self.assertRaises(FileNotFoundError):
            Weblate().get_object("bug")

    def test_invalid(self) -> None:
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, "invalid JSON"):
            Weblate().get_object("invalid")

    def test_too_long(self) -> None:
        """Test listing projects."""
        with self.assertRaises(ValueError):
            Weblate().get_object("a/b/c/d")

    def test_invalid_attribute(self) -> None:
        """Test attributes getting."""
        obj = Weblate().get_object("hello")
        self.assertEqual(obj.name, "Hello")
        with self.assertRaises(AttributeError):
            print(obj.invalid_attribute)


class WeblateTest(APITest):
    """Testing of Weblate class."""

    def test_languages(self) -> None:
        """Test listing projects."""
        self.assertEqual(len(list(Weblate().list_languages())), 47)

    def test_api_trailing_slash(self) -> None:
        """Test listing projects."""
        self.assertEqual(len(list(Weblate(url=API_URL[:-1]).list_languages())), 47)

    def test_projects(self) -> None:
        """Test listing projects."""
        self.assertEqual(len(list(Weblate().list_projects())), 2)

    def test_components(self) -> None:
        """Test listing components."""
        self.assertEqual(len(list(Weblate().list_components())), 2)

    def test_translations(self) -> None:
        """Test listing translations."""
        self.assertEqual(len(list(Weblate().list_translations())), 50)

    def test_categories(self) -> None:
        """Test listing translations."""
        self.assertEqual(len(list(Weblate().list_categories())), 2)

    def test_authentication(self) -> None:
        """Test authentication against server."""
        with self.assertRaisesRegex(WeblateException, "permission"):
            Weblate().get_object("acl")
        obj = Weblate(key="KEY").get_object("acl")
        self.assertEqual(obj.name, "ACL")

    def test_ensure_loaded(self) -> None:
        """Test lazy loading of attributes."""
        obj = Weblate().get_object("hello")
        obj.ensure_loaded("missing")
        obj.ensure_loaded("missing")
        with self.assertRaises(AttributeError):
            print(obj.missing)

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

    def test_add_source_string_to_monolingual_component(self) -> None:
        resp = Weblate().add_source_string(
            project="hello",
            component="android",
            msgid="test-monolingual",
            msgstr="test-me",
        )
        # ensure it is definitely monolingual
        self.assertEqual(resp["component"]["template"], "android/values/strings.xml")
        self.assertEqual(resp["component"]["slug"], "android")
        self.assertEqual(resp["id"], 1646)

    def test_create_project(self) -> None:
        resp = Weblate().create_project(
            "Hello", "hello", "http://example.com/", "Malayalam", "ml"
        )
        self.assertEqual("Hello", resp["name"])
        self.assertEqual("hello", resp["slug"])
        self.assertEqual("http://example.com/", resp["web"])
        self.assertEqual("Malayalam", resp["source_language"]["name"])
        self.assertEqual("ml", resp["source_language"]["code"])

    def test_create_language(self) -> None:
        resp = Weblate().create_language(
            name="Test Language",
            code="tst",
            direction="rtl",
            plural={"number": 2, "formula": "n != 1"},
        )
        self.assertEqual("Test Language", resp["name"])
        self.assertEqual("tst", resp["code"])
        self.assertEqual("rtl", resp["direction"])
        self.assertEqual(2, resp["plural"]["number"])
        self.assertEqual("n != 1", resp["plural"]["formula"])

    def test_create_component(self) -> None:
        resp = Weblate().create_component(
            project="hello",
            branch="main",
            file_format="po",
            filemask="po/*.po",
            git_export="",
            license="",
            license_url="",
            name="Weblate",
            slug="weblate",
            repo="file:///home/nijel/work/weblate-hello",
            template="",
            new_base="",
            vcs="git",
        )
        self.assertEqual("Hello", resp["project"]["name"])
        self.assertEqual("hello", resp["project"]["slug"])
        self.assertEqual("Weblate", resp["name"])
        self.assertEqual("weblate", resp["slug"])
        self.assertEqual("file:///home/nijel/work/weblate-hello", resp["repo"])
        self.assertEqual("http://example.com/git/hello/weblate/", resp["git_export"])
        self.assertEqual("main", resp["branch"])
        self.assertEqual("po/*.po", resp["filemask"])
        self.assertEqual("git", resp["vcs"])
        self.assertEqual("po", resp["file_format"])

        with self.assertRaisesRegex(WeblateException, "required"):
            Weblate().create_component(project="hello")

        with self.assertRaisesRegex(WeblateException, "required"):
            Weblate().create_component(project="hello", name="Weblate")

        with self.assertRaisesRegex(WeblateException, "required"):
            Weblate().create_component(project="hello", name="Weblate", slug="weblate")

        with self.assertRaisesRegex(WeblateException, "required"):
            Weblate().create_component(
                project="hello", name="Weblate", slug="weblate", file_format="po"
            )

        with self.assertRaisesRegex(WeblateException, "required"):
            Weblate().create_component(
                project="hello",
                name="Weblate",
                slug="weblate",
                file_format="po",
                filemask="po/*.po",
            )

    def test_create_component_local_files(self) -> None:
        test_file = os.path.join(
            os.path.dirname(__file__), "test_data", "mock", "project-local-file.pot"
        )
        with open(test_file, encoding="utf-8") as file:
            resp = Weblate().create_component(
                docfile=file.read(),
                project="hello",
                branch="main",
                file_format="po",
                filemask="po/*.po",
                git_export="",
                license="",
                license_url="",
                name="Weblate",
                slug="weblate",
                repo="local:",
                template="",
                new_base="",
                vcs="local",
            )
            self.assertEqual("Hello", resp["project"]["name"])
            self.assertEqual("hello", resp["project"]["slug"])
            self.assertEqual("Weblate", resp["name"])
            self.assertEqual("weblate", resp["slug"])
            self.assertEqual("local:", resp["repo"])
            self.assertEqual("main", resp["branch"])
            self.assertEqual("po/*.po", resp["filemask"])
            self.assertEqual("local", resp["vcs"])
            self.assertEqual("po", resp["file_format"])

            with self.assertRaisesRegex(WeblateException, "required"):
                Weblate().create_component(project="hello")

            with self.assertRaisesRegex(WeblateException, "required"):
                Weblate().create_component(project="hello", name="Weblate")

            with self.assertRaisesRegex(WeblateException, "required"):
                Weblate().create_component(
                    project="hello", name="Weblate", slug="weblate"
                )

            with self.assertRaisesRegex(WeblateException, "required"):
                Weblate().create_component(
                    project="hello", name="Weblate", slug="weblate", file_format="po"
                )

            with self.assertRaisesRegex(WeblateException, "required"):
                Weblate().create_component(
                    project="hello",
                    name="Weblate",
                    slug="weblate",
                    file_format="po",
                    filemask="po/*.po",
                )

    def test_should_verify_ssl(self) -> None:
        self.assertEqual(Weblate.should_verify_ssl("http://localhost/api/"), False)
        self.assertEqual(Weblate.should_verify_ssl("invalid/api/"), True)
        self.assertEqual(
            Weblate.should_verify_ssl("https://localhost.example.com/api/"), True
        )
        self.assertEqual(Weblate.should_verify_ssl("http://example.com/api/"), True)


class ObjectTestBaseClass(APITest, ABC):
    """Base class for objects testing."""

    _name: str | None = None
    _cls: Any = None

    def check_object(self, obj) -> None:
        """Perform verification whether object is valid."""
        raise NotImplementedError

    def get(self):
        """Return remote object."""
        return Weblate().get_object(self._name)

    def test_get(self) -> None:
        """Test getting project."""
        obj = self.get()
        self.assertIsInstance(obj, self._cls)
        self.check_object(obj)

    def check_list(self, obj) -> None:
        """Perform verification whether listing is valid."""
        raise NotImplementedError

    def test_list(self) -> None:
        """Item listing test."""
        obj = self.get()
        self.check_list(obj.list())


class ObjectTest(ObjectTestBaseClass, ABC):
    """Additional tests for projects, components, and translations."""

    def test_refresh(self) -> None:
        """Object refreshing test."""
        obj = self.get()
        obj.refresh()
        self.assertIsInstance(obj, self._cls)
        self.check_object(obj)

    def test_changes(self) -> None:
        """Item listing test."""
        obj = self.get()
        lst = list(obj.changes())
        self.assertEqual(len(lst), 2)
        self.assertIsInstance(lst[0], Change)

    def test_repository(self) -> None:
        """Repository get test."""
        obj = self.get()
        repository = obj.repository()
        self.assertFalse(repository.needs_commit)

    def test_repository_commit(self) -> None:
        """Repository commit test."""
        obj = self.get()
        repository = obj.repository()
        self.assertEqual(repository.commit(), {"result": True})

    def test_commit(self) -> None:
        """Direct commit test."""
        obj = self.get()
        self.assertEqual(obj.commit(), {"result": True})

    def test_pull(self) -> None:
        """Direct pull test."""
        obj = self.get()
        self.assertEqual(obj.pull(), {"result": True})

    def test_reset(self) -> None:
        """Direct reset test."""
        obj = self.get()
        self.assertEqual(obj.reset(), {"result": True})

    def test_cleanup(self) -> None:
        """Direct cleanup test."""
        obj = self.get()
        self.assertEqual(obj.cleanup(), {"result": True})

    def test_push(self) -> None:
        """Direct push test."""
        obj = self.get()
        self.assertEqual(
            obj.push(),
            {"result": False, "detail": "Push is disabled for Hello/Weblate."},
        )

    def test_data(self) -> None:
        obj = self.get()
        self.assertIsNotNone(obj.get_data())

    def test_delete(self) -> None:
        obj = self.get()
        self.assertIsNone(obj.delete())


class ProjectTest(ObjectTest):
    """Project object tests."""

    _name = "hello"
    _cls = Project

    def check_object(self, obj) -> None:
        """Perform verification whether object is valid."""
        self.assertEqual(obj.name, "Hello")

    def check_list(self, obj) -> None:
        """Perform verification whether listing is valid."""
        lst = list(obj)
        self.assertEqual(len(lst), 2)
        self.assertIsInstance(lst[0], Component)

    def test_languages(self) -> None:
        """Component statistics test."""
        obj = self.get()
        self.assertEqual(2, len(list(obj.languages())))

    def test_statistics(self) -> None:
        """Component statistics test."""
        obj = self.get()
        stats = obj.statistics()
        self.assertEqual(stats["name"], "Hello")

    def test_categories(self) -> None:
        obj = self.get()
        self.assertEqual(2, len(list(obj.categories())))

    def test_create_component(self) -> None:
        """Component creation test."""
        obj = self.get()
        resp = obj.create_component(
            branch="main",
            file_format="po",
            filemask="po/*.po",
            git_export="",
            license="",
            license_url="",
            name="Weblate",
            slug="weblate",
            repo="file:///home/nijel/work/weblate-hello",
            template="",
            new_base="",
            vcs="git",
        )
        self.assertEqual("Hello", resp["project"]["name"])
        self.assertEqual("hello", resp["project"]["slug"])
        self.assertEqual("Weblate", resp["name"])
        self.assertEqual("weblate", resp["slug"])
        self.assertEqual("file:///home/nijel/work/weblate-hello", resp["repo"])
        self.assertEqual("http://example.com/git/hello/weblate/", resp["git_export"])
        self.assertEqual("main", resp["branch"])
        self.assertEqual("po/*.po", resp["filemask"])
        self.assertEqual("git", resp["vcs"])
        self.assertEqual("po", resp["file_format"])


class ComponentTest(ObjectTest):
    """Component object tests."""

    _name = "hello/weblate"
    _cls = Component

    def check_object(self, obj) -> None:
        """Perform verification whether object is valid."""
        self.assertEqual(obj.name, "Weblate")
        self.assertEqual(obj.priority, 100)
        self.assertEqual(obj.agreement, "")

    def check_list(self, obj) -> None:
        """Perform verification whether listing is valid."""
        lst = list(obj)
        self.assertEqual(len(lst), 33)
        self.assertIsInstance(lst[0], Translation)

    def test_add_translation(self) -> None:
        """Perform verification that the correct endpoint is accessed."""
        obj = self.get()
        resp = obj.add_translation("nl_BE")
        self.assertEqual(resp["data"]["id"], 827)
        self.assertEqual(
            resp["data"]["revision"], "da6ea2777f61fbe1d2a207ff6ebdadfa15f26d1a"
        )

    def test_statistics(self) -> None:
        """Component statistics test."""
        obj = self.get()
        self.assertEqual(33, len(list(obj.statistics())))

    def test_lock_status(self) -> None:
        """Component lock status test."""
        obj = self.get()
        self.assertEqual({"locked": False}, obj.lock_status())

    def test_lock(self) -> None:
        """Component lock test."""
        obj = self.get()
        self.assertEqual({"locked": True}, obj.lock())

    def test_unlock(self) -> None:
        """Component unlock test."""
        obj = self.get()
        self.assertEqual({"locked": False}, obj.unlock())

    def test_keys(self) -> None:
        """Test keys lazy loading."""
        obj = Component(Weblate(), f"components/{self._name}/")
        self.assertCountEqual(
            obj.keys(),
            [
                "agreement",
                "branch",
                "category",
                "file_format",
                "filemask",
                "git_export",
                "is_glossary",
                "license",
                "license_url",
                "name",
                "new_base",
                "priority",
                "project",
                "repo",
                "slug",
                "source_language",
                "template",
                "url",
                "vcs",
                "web_url",
            ],
        )

    def test_components_patch(self) -> None:
        obj = self.get()
        resp = obj.patch(priority=80)
        self.assertIn("--patched--", resp.decode())


class ComponentCompatibilityTest(ObjectTest):
    """Tests a component with lack of all optional fields in a response."""

    _name = "hello/olderweblate"
    _cls = Component

    def check_object(self, obj) -> None:
        """Perform verification whether object is valid."""
        self.assertEqual(obj.name, "Weblate")
        self.assertEqual(obj.priority, 100)
        self.assertEqual(obj.agreement, "")

    def check_list(self, obj) -> None:
        """Perform verification whether listing is valid."""
        lst = list(obj)
        self.assertEqual(len(lst), 33)
        self.assertIsInstance(lst[0], Translation)

    def test_keys(self) -> None:
        """Test keys lazy loading."""
        obj = Component(Weblate(), f"components/{self._name}/")
        self.assertCountEqual(
            obj.keys(),
            [
                "agreement",
                "category",
                "branch",
                "file_format",
                "filemask",
                "git_export",
                "license",
                "license_url",
                "name",
                "new_base",
                "priority",
                "project",
                "repo",
                "slug",
                "template",
                "url",
                "vcs",
                "web_url",
            ],
        )


class TranslationTest(ObjectTest):
    """Translation object tests."""

    _name = "hello/weblate/cs"
    _cls = Translation

    def check_object(self, obj) -> None:
        """Perform verification whether object is valid."""
        self.assertEqual(obj.language.code, "cs")

    def check_list(self, obj) -> None:
        """Perform verification whether listing is valid."""
        self.assertIsInstance(obj, Translation)

    def test_statistics(self) -> None:
        """Translation statistics test."""
        obj = self.get()
        data = obj.statistics()
        self.assertEqual(data.name, "Czech")

    def test_download(self) -> None:
        """Test verbatim file download."""
        obj = self.get()
        content = obj.download()
        self.assertIn(b"Plural-Forms:", content)

    def test_download_csv(self) -> None:
        """Test download of file converted to CSV."""
        obj = self.get()
        content = obj.download("csv")
        self.assertIn(b'"location"', content)

    def test_upload(self) -> None:
        """Test file upload."""
        obj = self.get()
        file = io.StringIO("test upload data")

        obj.upload(file)

    def test_upload_method(self) -> None:
        """Test file upload."""
        obj = self.get()
        file = io.StringIO("test upload data")

        obj.upload(file, method="translate")

    def test_upload_format(self) -> None:
        """Test file upload."""
        obj = self.get()
        file = io.StringIO("test upload data")

        obj.upload(file, format="po")

    def test_units(self) -> None:
        obj = self.get()
        units = list(obj.units())
        self.assertEqual(1, len(units))
        self.assertIsInstance(units[0], Unit)
        self.assertEqual(units[0].id, 35664)

    def test_units_search(self) -> None:
        obj = self.get()
        units = list(obj.units(q='source:="mr"'))
        self.assertEqual(1, len(units))
        self.assertIsInstance(units[0], Unit)
        self.assertEqual(units[0].id, 117)


class UnitTest(ObjectTestBaseClass):
    """Unit model testing."""

    _name = "123"
    _cls = Unit
    patch_data: ClassVar[dict[str, Any]] = {
        "target": ["foo"],
        "state": 30,
    }

    def check_object(self, obj) -> None:
        """Perform verification whether object is valid."""
        self.assertEqual(obj.id, 123)

    def check_list(self, obj) -> None:
        """Perform verification whether listing is valid."""
        self.assertIsInstance(obj, Unit)

    def test_units_patch(self) -> None:
        obj = self.get()
        resp = obj.patch(**self.patch_data)
        self.assertIn("--patched--", resp.decode())

    def test_units_put(self) -> None:
        obj = self.get()
        resp = obj.put(**self.patch_data)
        self.assertIn("--put--", resp.decode())

    def test_units_delete(self) -> None:
        obj = self.get()
        resp = obj.delete()
        self.assertIn("--deleted--", resp.decode())


class CategoryTest(APITest):
    """Category model testing."""

    def test(self) -> None:
        obj = Category(Weblate(), "http://127.0.0.1:8000/api/categories/1/")
        self.assertIsInstance(obj, Category)
        self.assertIsNone(obj.category)
        self.assertEqual(obj.name, "Hi")
        self.assertEqual(obj.slug, "hi")


# Delete the reference, so that the abstract class is not discovered
# when running tests
del ObjectTest
del ObjectTestBaseClass
