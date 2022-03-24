#
# Copyright © 2012–2022 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate Client <https://github.com/WeblateOrg/wlc>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Test the module."""
import io
import os
from typing import Any, Optional

from requests.exceptions import RequestException

from wlc import (
    API_URL,
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

    def test_nonexisting(self):
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, "not found"):
            Weblate().get_object("nonexisting")

    def test_denied(self):
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, "permission"):
            Weblate().get_object("denied")

    def test_denied_json(self):
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

    def test_throttled(self):
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, "Throttling"):
            Weblate().get_object("throttled")

    def test_error(self):
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, "500"):
            Weblate().get_object("error")

    def test_oserror(self):
        """Test listing projects."""
        with self.assertRaises(RequestException):
            Weblate().get_object("io")

    def test_bug(self):
        """Test listing projects."""
        with self.assertRaises(FileNotFoundError):
            Weblate().get_object("bug")

    def test_invalid(self):
        """Test listing projects."""
        with self.assertRaisesRegex(WeblateException, "invalid JSON"):
            Weblate().get_object("invalid")

    def test_too_long(self):
        """Test listing projects."""
        with self.assertRaises(ValueError):
            Weblate().get_object("a/b/c/d")

    def test_invalid_attribute(self):
        """Test attributes getting."""
        obj = Weblate().get_object("hello")
        self.assertEqual(obj.name, "Hello")
        with self.assertRaises(AttributeError):
            print(obj.invalid_attribute)


class WeblateTest(APITest):
    """Testing of Weblate class."""

    def test_languages(self):
        """Test listing projects."""
        self.assertEqual(len(list(Weblate().list_languages())), 47)

    def test_api_trailing_slash(self):
        """Test listing projects."""
        self.assertEqual(len(list(Weblate(url=API_URL[:-1]).list_languages())), 47)

    def test_projects(self):
        """Test listing projects."""
        self.assertEqual(len(list(Weblate().list_projects())), 2)

    def test_components(self):
        """Test listing components."""
        self.assertEqual(len(list(Weblate().list_components())), 2)

    def test_translations(self):
        """Test listing translations."""
        self.assertEqual(len(list(Weblate().list_translations())), 50)

    def test_authentication(self):
        """Test authentication against server."""
        with self.assertRaisesRegex(WeblateException, "permission"):
            obj = Weblate().get_object("acl")
        obj = Weblate(key="KEY").get_object("acl")
        self.assertEqual(obj.name, "ACL")

    def test_ensure_loaded(self):
        """Test lazy loading of attributes."""
        obj = Weblate().get_object("hello")
        obj.ensure_loaded("missing")
        obj.ensure_loaded("missing")
        with self.assertRaises(AttributeError):
            print(obj.missing)

    def test_setattrvalue(self):
        """Test lazy loading of attributes."""
        obj = Weblate().get_object("hello")
        with self.assertRaises(AttributeError):
            obj.setattrvalue("missing", "")

    def test_repr(self):
        """Test str and repr behavior."""
        obj = Weblate().get_object("hello")
        self.assertIn("'slug': 'hello'", repr(obj))
        self.assertIn("'slug': 'hello'", str(obj))

    def test_add_source_string_to_monolingual_component(self):
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

    def test_create_project(self):
        resp = Weblate().create_project(
            "Hello", "hello", "http://example.com/", "Malayalam", "ml"
        )
        self.assertEqual("Hello", resp["name"])
        self.assertEqual("hello", resp["slug"])
        self.assertEqual("http://example.com/", resp["web"])
        self.assertEqual("Malayalam", resp["source_language"]["name"])
        self.assertEqual("ml", resp["source_language"]["code"])

    def test_create_language(self):
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

    def test_create_component(self):
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

    def test_create_component_local_files(self):

        test_file = os.path.join(
            os.path.dirname(__file__), "test_data", "mock", "project-local-file.pot"
        )
        with open(test_file) as file:
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


class ObjectTestBaseClass(APITest):
    """Base class for objects testing."""

    _name: Optional[str] = None
    _cls: Any = None

    def check_object(self, obj):
        """Perform verification whether object is valid."""
        raise NotImplementedError()

    def get(self):
        """Return remote object."""
        return Weblate().get_object(self._name)

    def test_get(self):
        """Test getting project."""
        obj = self.get()
        self.assertIsInstance(obj, self._cls)
        self.check_object(obj)

    def check_list(self, obj):
        """Perform verification whether listing is valid."""
        raise NotImplementedError()

    def test_list(self):
        """Item listing test."""
        obj = self.get()
        self.check_list(obj.list())


class ObjectTest(ObjectTestBaseClass):
    """Additional tests for projects, components, and translations."""

    def test_refresh(self):
        """Object refreshing test."""
        obj = self.get()
        obj.refresh()
        self.assertIsInstance(obj, self._cls)
        self.check_object(obj)

    def test_changes(self):
        """Item listing test."""
        obj = self.get()
        lst = list(obj.changes())
        self.assertEqual(len(lst), 2)
        self.assertIsInstance(lst[0], Change)

    def test_repository(self):
        """Repository get test."""
        obj = self.get()
        repository = obj.repository()
        self.assertFalse(repository.needs_commit)

    def test_repository_commit(self):
        """Repository commit test."""
        obj = self.get()
        repository = obj.repository()
        self.assertEqual(repository.commit(), {"result": True})

    def test_commit(self):
        """Direct commit test."""
        obj = self.get()
        self.assertEqual(obj.commit(), {"result": True})

    def test_pull(self):
        """Direct pull test."""
        obj = self.get()
        self.assertEqual(obj.pull(), {"result": True})

    def test_reset(self):
        """Direct reset test."""
        obj = self.get()
        self.assertEqual(obj.reset(), {"result": True})

    def test_cleanup(self):
        """Direct cleanup test."""
        obj = self.get()
        self.assertEqual(obj.cleanup(), {"result": True})

    def test_push(self):
        """Direct push test."""
        obj = self.get()
        self.assertEqual(
            obj.push(),
            {"result": False, "detail": "Push is disabled for Hello/Weblate."},
        )

    def test_data(self):
        obj = self.get()
        self.assertIsNotNone(obj.get_data())

    def test_delete(self):
        obj = self.get()
        self.assertIsNone(obj.delete())


class ProjectTest(ObjectTest):
    """Project object tests."""

    _name = "hello"
    _cls = Project

    def check_object(self, obj):
        """Perform verification whether object is valid."""
        self.assertEqual(obj.name, "Hello")

    def check_list(self, obj):
        """Perform verification whether listing is valid."""
        lst = list(obj)
        self.assertEqual(len(lst), 2)
        self.assertIsInstance(lst[0], Component)

    def test_languages(self):
        """Component statistics test."""
        obj = self.get()
        self.assertEqual(2, len(list(obj.languages())))

    def test_statistics(self):
        """Component statistics test."""
        obj = self.get()
        stats = obj.statistics()
        self.assertEqual(stats["name"], "Hello")

    def test_create_component(self):
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

    def check_object(self, obj):
        """Perform verification whether object is valid."""
        self.assertEqual(obj.name, "Weblate")

    def check_list(self, obj):
        """Perform verification whether listing is valid."""
        lst = list(obj)
        self.assertEqual(len(lst), 33)
        self.assertIsInstance(lst[0], Translation)

    def test_add_translation(self):
        """Perform verification that the correct endpoint is accessed."""
        obj = self.get()
        resp = obj.add_translation("nl_BE")
        self.assertEqual(resp["data"]["id"], 827)
        self.assertEqual(
            resp["data"]["revision"], "da6ea2777f61fbe1d2a207ff6ebdadfa15f26d1a"
        )

    def test_statistics(self):
        """Component statistics test."""
        obj = self.get()
        self.assertEqual(33, len(list(obj.statistics())))

    def test_lock_status(self):
        """Component lock status test."""
        obj = self.get()
        self.assertEqual({"locked": False}, obj.lock_status())

    def test_lock(self):
        """Component lock test."""
        obj = self.get()
        self.assertEqual({"locked": True}, obj.lock())

    def test_unlock(self):
        """Component unlock test."""
        obj = self.get()
        self.assertEqual({"locked": False}, obj.unlock())

    def test_keys(self):
        """Test keys lazy loading."""
        obj = Component(Weblate(), f"components/{self._name}/")
        self.assertEqual(
            sorted(obj.keys()),
            sorted(
                [
                    "branch",
                    "file_format",
                    "filemask",
                    "git_export",
                    "license",
                    "license_url",
                    "name",
                    "new_base",
                    "project",
                    "repo",
                    "slug",
                    "source_language",
                    "source_language",
                    "template",
                    "url",
                    "vcs",
                    "web_url",
                ]
            ),
        )


class TranslationTest(ObjectTest):
    """Translation object tests."""

    _name = "hello/weblate/cs"
    _cls = Translation

    def check_object(self, obj):
        """Perform verification whether object is valid."""
        self.assertEqual(obj.language.code, "cs")

    def check_list(self, obj):
        """Perform verification whether listing is valid."""
        self.assertIsInstance(obj, Translation)

    def test_statistics(self):
        """Translation statistics test."""
        obj = self.get()
        data = obj.statistics()
        self.assertEqual(data.name, "Czech")

    def test_download(self):
        """Test verbatim file download."""
        obj = self.get()
        content = obj.download()
        self.assertIn(b"Plural-Forms:", content)

    def test_download_csv(self):
        """Test dowload of file converted to CSV."""
        obj = self.get()
        content = obj.download("csv")
        self.assertIn(b'"location"', content)

    def test_upload(self):
        """Test file upload."""
        obj = self.get()
        file = io.StringIO("test upload data")

        obj.upload(file)

    def test_upload_method(self):
        """Test file upload."""
        obj = self.get()
        file = io.StringIO("test upload data")

        obj.upload(file, method="translate")

    def test_upload_format(self):
        """Test file upload."""
        obj = self.get()
        file = io.StringIO("test upload data")

        obj.upload(file, format="po")

    def test_units(self):
        obj = self.get()
        units = list(obj.units())
        self.assertEqual(1, len(units))
        self.assertIsInstance(units[0], Unit)
        self.assertEqual(units[0].id, 35664)

    def test_units_search(self):
        obj = self.get()
        units = list(obj.units(q='source:="mr"'))
        self.assertEqual(1, len(units))
        self.assertIsInstance(units[0], Unit)
        self.assertEqual(units[0].id, 117)


class UnitTest(ObjectTestBaseClass):
    _name = "123"
    _cls = Unit
    patch_data = {
        "target": ["foo"],
        "state": 30,
    }

    def check_object(self, obj):
        """Perform verification whether object is valid."""
        self.assertEqual(obj.id, 123)

    def check_list(self, obj):
        """Perform verification whether listing is valid."""
        self.assertIsInstance(obj, Unit)

    def test_units_patch(self):
        obj = self.get()
        resp = obj.patch(**self.patch_data)
        self.assertIn("--patched--", resp.decode())

    def test_units_put(self):
        obj = self.get()
        resp = obj.put(**self.patch_data)
        self.assertIn("--put--", resp.decode())

    def test_units_delete(self):
        obj = self.get()
        resp = obj.delete()
        self.assertIn("--deleted--", resp.decode())


# Delete the reference, so that the abstract class is not discovered
# when running tests
del ObjectTest
del ObjectTestBaseClass
