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
* Fixed installation of wlc command line.

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
