# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test API resource models."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import io
from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Generic, TypeVar, cast
from unittest.mock import patch

import responses

from wlc import (
    Change,
    Component,
    Project,
    Translation,
    Unit,
    Weblate,
    WeblateException,
)

from .test_base import APITest

if TYPE_CHECKING:
    from collections.abc import Iterable

    from wlc.base import LazyObject
    from wlc.client import JSONDict

ObjectT = TypeVar("ObjectT", Project, Component, Translation, Unit)


class WeblateCreationTest(APITest):
    """Test resource creation through the client."""

    def test_add_source_string_uses_post_override(self) -> None:
        """Creation factories should dispatch through an overridden post method."""
        calls: list[tuple[str, dict[str, object]]] = []
        result = {"id": 123}

        class CustomWeblate(Weblate):
            """Client intercepting POST calls before HTTP dispatch."""

            def post(self, path: str, **kwargs: object) -> JSONDict:
                calls.append((path, kwargs))
                return result

        weblate = CustomWeblate()
        self.assertIs(
            weblate.add_source_string(
                project="hello",
                component="weblate",
                source_language="en",
                msgid="key",
                msgstr="value",
            ),
            result,
        )
        self.assertEqual(
            calls,
            [
                (
                    "translations/hello/weblate/en/units/",
                    {"key": "key", "value": ["value"]},
                )
            ],
        )
        self.assertFalse(responses.calls)

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
            name="Hello",
            slug="hello",
            website="http://example.com/",
            source_language_name="Malayalam",
            source_language_code="ml",
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

    def test_create_component_query_params(self) -> None:
        """Project wrappers should forward query parameters separately from fields."""
        fields = {
            "name": "Typed component",
            "slug": "typed",
            "file_format": "po",
            "filemask": "po/*.po",
            "repo": "local:",
        }
        params = {"include": "statistics"}
        responses.add(
            responses.POST,
            "http://127.0.0.1:8000/api/projects/typed/components/",
            json={"id": 123},
            match=[
                responses.matchers.query_param_matcher(params),
                responses.matchers.json_params_matcher(fields),
            ],
        )
        project = Project(Weblate(), "projects/typed/", slug="typed")
        self.assertEqual(project.create_component(params=params, **fields), {"id": 123})

    def test_create_component_local_files(self) -> None:
        test_file = (
            Path(__file__).parent / "test_data" / "mock" / "project-local-file.pot"
        )
        with test_file.open(encoding="utf-8") as file:
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


class ObjectTestBaseClass(APITest, ABC, Generic[ObjectT]):
    """Base class for objects testing."""

    _name: str | None = None
    _cls: type[object] | None = None

    def check_object(self, obj: ObjectT) -> None:
        """Perform verification whether object is valid."""
        raise NotImplementedError

    def get(self) -> ObjectT:
        """Return remote object."""
        name = self._name
        if name is None:
            self.fail("_name must be configured in object test cases")
        return cast("ObjectT", Weblate().get_object(name))

    def test_get(self) -> None:
        """Test getting project."""
        obj = self.get()
        expected_cls = self._cls
        if expected_cls is None:
            self.fail("_cls must be configured in object test cases")
        self.assertIsInstance(obj, expected_cls)
        self.check_object(obj)

    def check_list(self, obj: Iterable[LazyObject] | Translation | Unit) -> None:
        """Perform verification whether listing is valid."""
        raise NotImplementedError

    def test_list(self) -> None:
        """Item listing test."""
        obj = self.get()
        self.check_list(obj.list())


class ObjectTest(ObjectTestBaseClass[ObjectT], ABC):
    """Additional tests for projects, components, and translations."""

    def test_refresh(self) -> None:
        """Object refreshing test."""
        obj = self.get()
        obj.refresh()
        expected_cls = self._cls
        if expected_cls is None:
            self.fail("_cls must be configured in object test cases")
        self.assertIsInstance(obj, expected_cls)
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


class ProjectTest(ObjectTest[Project]):
    """Project object tests."""

    _name = "hello"
    _cls = Project

    def check_object(self, obj: Project) -> None:
        """Perform verification whether object is valid."""
        self.assertEqual(obj.name, "Hello")

    def check_list(self, obj: Iterable[LazyObject] | Translation | Unit) -> None:
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


class ComponentTest(ObjectTest[Component]):
    """Component object tests."""

    _name = "hello/weblate"
    _cls = Component

    def test_add_source_string(self) -> None:
        obj = self.get()
        result = {"id": 1646}
        with patch.object(obj.weblate, "add_source_string", return_value=result) as add:
            self.assertIs(obj.add_source_string(msgid="key", msgstr="value"), result)

        add.assert_called_once_with(
            project="hello",
            component="weblate",
            msgid="key",
            msgstr="value",
            source_language=obj.source_language["code"],
        )

    def check_object(self, obj: Component) -> None:
        """Perform verification whether object is valid."""
        self.assertEqual(obj.name, "Weblate")
        self.assertEqual(obj.priority, 100)
        self.assertEqual(obj.agreement, "")

    def check_list(self, obj: Iterable[LazyObject] | Translation | Unit) -> None:
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
                "lock_url",
                "name",
                "new_base",
                "priority",
                "project",
                "repo",
                "repository_url",
                "changes_list_url",
                "slug",
                "source_language",
                "statistics_url",
                "template",
                "translations_url",
                "url",
                "vcs",
                "web_url",
            ],
        )

    def test_components_patch(self) -> None:
        obj = self.get()
        resp = obj.patch(priority=80)
        self.assertIn("--patched--", resp.decode())

    def test_download_preserves_repository_in_slug(self) -> None:
        """
        Download URL must rewrite only the trailing /repository/ segment.

        A global substring replacement would corrupt legal component slugs
        containing "repository" (e.g. docs_repository) and request the wrong
        component's file endpoint.
        """
        weblate = Weblate()
        slug = "docs_repository"
        base = "http://127.0.0.1:8000/api"
        obj = Component(
            weblate,
            url=f"components/hello/{slug}/",
            repository_url=f"{base}/components/hello/{slug}/repository/",
        )
        file_url = f"{base}/components/hello/{slug}/file/"
        corrupted_url = f"{base}/components/hello/docs_file/file/"
        responses.add(
            responses.GET,
            file_url,
            body=b"correct-archive",
            content_type="application/zip",
        )
        responses.add(responses.GET, corrupted_url, status=500)

        content = obj.download()

        self.assertEqual(content, b"correct-archive")
        requested = [call.request.url for call in responses.mock.calls]
        self.assertIn(file_url, requested)
        self.assertNotIn(corrupted_url, requested)


class ComponentCompatibilityTest(ObjectTest[Component]):
    """Tests a component with lack of all optional fields in a response."""

    _name = "hello/olderweblate"
    _cls = Component

    def check_object(self, obj: Component) -> None:
        """Perform verification whether object is valid."""
        self.assertEqual(obj.name, "Weblate")
        self.assertEqual(obj.priority, 100)
        self.assertEqual(obj.agreement, "")

    def check_list(self, obj: Iterable[LazyObject] | Translation | Unit) -> None:
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
                "lock_url",
                "name",
                "new_base",
                "priority",
                "project",
                "repo",
                "repository_url",
                "changes_list_url",
                "slug",
                "statistics_url",
                "template",
                "translations_url",
                "url",
                "vcs",
                "web_url",
            ],
        )


class TranslationTest(ObjectTest[Translation]):
    """Translation object tests."""

    _name = "hello/weblate/cs"
    _cls = Translation

    def check_object(self, obj: Translation) -> None:
        """Perform verification whether object is valid."""
        self.assertEqual(obj.language.code, "cs")

    def check_list(self, obj: Iterable[LazyObject] | Translation | Unit) -> None:
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
        content = obj.download(convert="csv")
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

    def test_upload_overwrite_options(self) -> None:
        obj = self.get()
        for overwrite in (True, False, None):
            for file_format in ("po", None):
                with self.subTest(overwrite=overwrite, format=file_format):
                    file = io.StringIO("test upload data")
                    with patch.object(
                        obj.weblate, "request", return_value={}
                    ) as request:
                        obj.upload(
                            file,
                            overwrite=overwrite,
                            format=file_format,
                            conflicts="ignore",
                            method="translate",
                        )

                    request.assert_called_once_with(
                        "post",
                        obj.file_url,
                        files={"file": ("file.po", file) if file_format else file},
                        data={
                            "conflicts": "replace-translated"
                            if overwrite
                            else "ignore",
                            "method": "translate",
                        },
                    )

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

    def test_exposes_hidden_fields(self) -> None:
        obj = self.get()
        self.assertEqual("cs", obj.language_code)
        self.assertTrue(obj.repository_url.endswith("/repository/"))
        self.assertTrue(obj.file_url.endswith("/file/"))
        self.assertTrue(obj.statistics_url.endswith("/statistics/"))
        self.assertTrue(obj.changes_list_url.endswith("/changes/"))
        self.assertTrue(obj.units_list_url.endswith("/units/"))


class UnitTest(ObjectTestBaseClass[Unit]):
    """Unit model testing."""

    _name = "123"
    _cls = Unit
    patch_data: ClassVar[dict[str, object]] = {
        "target": ["foo"],
        "state": 30,
    }

    def check_object(self, obj: Unit) -> None:
        """Perform verification whether object is valid."""
        self.assertEqual(obj.id, 123)

    def check_list(self, obj: Iterable[LazyObject] | Translation | Unit) -> None:
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

    def test_units_put_uses_loaded_defaults(self) -> None:
        obj = Unit(
            Weblate(),
            "http://127.0.0.1:8000/api/units/987/",
            target=["hello"],
            labels=[{"id": 1, "name": "important"}],
        )
        with patch.object(obj.weblate, "raw_request", return_value=b"") as raw_request:
            obj.put(state=30)

        raw_request.assert_called_once_with(
            "put",
            "http://127.0.0.1:8000/api/units/987/",
            data={
                "state": 30,
                "target": ["hello"],
                "labels": [{"id": 1, "name": "important"}],
            },
        )

    def test_units_put_preserves_scalar_target(self) -> None:
        obj = Unit(
            Weblate(),
            "http://127.0.0.1:8000/api/units/987/",
            target="mr",
        )
        with (
            patch.object(obj, "refresh"),
            patch.object(obj.weblate, "raw_request", return_value=b"") as raw_request,
        ):
            obj.put(state=30)

        raw_request.assert_called_once_with(
            "put",
            "http://127.0.0.1:8000/api/units/987/",
            data={
                "state": 30,
                "target": "mr",
            },
        )

    def test_units_delete(self) -> None:
        obj = self.get()
        resp = obj.delete()
        self.assertIn("--deleted--", resp.decode())

    def test_exposes_hidden_fields(self) -> None:
        obj = Unit(
            Weblate(),
            "http://127.0.0.1:8000/api/units/987/",
            labels=[{"id": 1, "name": "important"}],
            language_code="cs",
            pending=False,
            timestamp="2024-01-01T00:00:00Z",
            last_updated="2024-01-02T00:00:00Z",
        )

        self.assertEqual("cs", obj.language_code)
        self.assertEqual("important", obj.labels[0]["name"])
        self.assertFalse(obj.pending)
        self.assertIsNotNone(obj.timestamp)
        self.assertIsNotNone(obj.last_updated)


class ChangeTest(APITest):
    """Change model testing."""

    def test_exposes_identifiers(self) -> None:
        changes = list(Weblate().list_changes())

        self.assertEqual(353, changes[0].id)
        self.assertIsNone(changes[0].user)
        self.assertEqual(350, changes[1].id)
        self.assertEqual(2, changes[1].user)
        self.assertEqual(2, changes[1].author)


# Delete the reference, so that the abstract class is not discovered
# when running tests
del ObjectTest
del ObjectTestBaseClass
