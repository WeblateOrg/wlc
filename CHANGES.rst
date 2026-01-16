1.17.2
------

* Released on 16th January 2026.
* Fixes path traversal: Unsanitized API slugs in download command (CVE-2026-23535).

1.17.1
------

* Released on 13th January 2026.
* Unscoped ``key`` in configuration triggers error.

1.17.0
------

* Released on 12th January 2026.
* Configuration change might be needed to move API keys to a new location, see https://docs.weblate.org/en/latest/wlc.html#legacy-configuration.
* Dropped support for unscoped ``key`` in configuration (CVE-2026-22251).
* Tightened hostname-based SSL verification skip (CVE-2026-22250).
* Modernized packaging.
* Improved type annotations.

1.16.1
------

* Released on 10th October 2025.
* Fixed packages publishing.

1.16
----

* Released on 10th October 2025.
* Fixed downloading components based on configuration.
* Improved error reporting with Weblate 5.10 and newer.
* Improved handling of categorized components.
* Dropped support for Python 3.8 and 3.9.
* Added support for Python 3.13 and 3.14.

1.15
----

* Released on 3rd September 2024.
* Fixed installation on certain filesystems.

1.14
----

* Released on 23rd February 2024.
* Dropped support for Python 3.6 and 3.7.
* Tested against Python 3.11 and 3.12.
* Added support for categories.
* Added support for the linked_component field.

1.13
----

* Released on 24th March 2022.
* Support all wlc upload methods.
* Tested against Python 3.10.
* Allow uploading files when creating a component.
* Allow downloading at component, project, and site level.

1.12
----

* Released on 19th May 2021.
* Improved error messages when permission was denied.
* Added type hints to the codebase.

1.11
----

* Released on 17th March 2021.
* Fixed long filenames in test fixtures.
* Updated base docker image.
* Add support for specifying format when uploading files.

1.10
----

* Released on 11th February 2021.
* Added ability to create new projects, components, and translations
* Added ability to add new source strings to a component
* Added Retry mechanism to handle failed requests
* Added ability to create a new language
* Added the source_lang attribute to Components
* Added Unit class which provides access to the units api endpoints.
* Added the PATCH HTTP method to the white list in order to enable access to new api endpoints.
* Using requests.session to keep a single http request open instead of reinitializing them.
* Added timeout config variable

1.9
---

* Released on 21st December 2020.
* Added Docker image published as weblate/wlc on Docker Hub.

1.8
---

* Released on 11th September 2020.
* Compatibility with Weblate 4.3 which moves source language from component to a project.

1.7
---

* Released on 3rd September 2020.
* Fixed installation of wlc command-line.

1.6
---

* Released on 1st September 2020.
* Post payload as JSON to allow handling complex data structures.
* Added support for finding configuration file on Windows in AppData dir.
* Improved error reporting.

1.5
---

* Released on 19th June 2020.
* Fixed compatibility of some API calls with Weblate 4.1.

1.4
---

* Released on 3rd June 2020.
* Fixed compatibility of some API calls with Weblate 4.1.

1.3
---

* Released on 6th May 2020.
* Mark Python 3.8 as supported, dropped support for Python 3.5.
* Added support for shell completion.
* Improved error messages to give better understanding of actual problem.
* Fixed repr() and str() behavior on returned objects.
* Added support for filtering components and translations.
* Better report errors when accessing API.

1.2
---

* Released on 15th October 2019.
* Fix stats invocation.
* Improved timestamps handling.
* Added support for replace upload.
* Added support for project, component and translation removal.

1.1
---

* Released on 1st February, 2019.
* Fixed listing of language objects.

1.0
---

* Released on 31st January, 2019.
* Added support for more parameters on file upload.

0.10
----

* Released on 21th October, 2018.
* Fixed POST operations in the API.
* Added --debug parameter to diagnose HTTP problems.

0.9
---

* Released on 17th October, 2018.
* Switched to requests
* Added support for cleanup command.
* Added support for upload command.

0.8
---

* Released on 3rd March, 2017.
* Various code cleanups.
* Tested with Python 3.6.

0.7
---

* Released on 16th December, 2016.
* Added reset operation.
* Added statistics for project.
* Added changes listing.
* Added file downloads.

0.6
---

* Released on 20th September, 2016.
* Fixed error when invoked without command.
* Tested on Windows and OS X (in addition to Linux).

0.5
---

* Released on 11th July, 2016.
* Added locking commands.

0.4
---

* Released on 8th July, 2016.
* Moved Git repository.

0.3
---

* Released on 19th May, 2016.
* First version for general usage.
