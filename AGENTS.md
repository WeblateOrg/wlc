<!--
Copyright © Michal Čihař <michal@weblate.org>

SPDX-License-Identifier: GPL-3.0-or-later
-->

# Repository Guidelines

## Project Structure & Module Organization

`wlc/` contains the package: `main.py` handles the CLI, `client.py` HTTP, `config.py` configuration, and `models.py` API resources. The root `wl` launches source; `pyproject.toml` defines the installed command. Tests and fixtures are in `tests/`. Completion, packaging, and CI files live in `completion/`, the root, and `.github/`.

## Build, Test, and Development Commands

- `uv sync --all-extras --dev` installs the Python 3.10+ environment.
- `uv run py.test --cov=wlc tests` runs the full test suite with coverage.
- `uv run py.test tests/test_config.py -k default_load` runs focused tests.
- `uv run prek run --all-files` runs formatting, lint, metadata, and secret checks. Prefer it over direct Ruff; hooks supply Ruff.
- `uv run mypy --show-column-numbers wlc`, `uv run --all-extras ty check`, and `uv run pylint wlc/ tests/` mirror CI static checks.
- `uv build` creates distributions in `dist/`; `docker build -t weblate/wlc .` builds the image.

## Coding Style & Naming Conventions

Use four spaces in Python and two in YAML/TOML. Ruff targets Python 3.10. Use `snake_case` for functions/modules, `PascalCase` for classes, and uppercase constants. Add type hints, future annotations, and `TYPE_CHECKING` imports when useful. Use readable suppressions such as `# ruff: ignore[blind-except]`, not rule codes. New code is GPL-3.0-or-later; copy neighboring copyright and SPDX headers.

## Testing Guidelines

Tests use pytest, `unittest.TestCase`, and `responses` HTTP mocks. Name files `test_<area>.py` and methods `test_<behavior>`. Update fixtures in `tests/test_data/api/` when endpoint interactions change. Every bug fix or behavior change should have a regression test; maintain 100% project coverage.

## Documentation Updates

Canonical user documentation lives in `WeblateOrg/weblate`: `docs/wlc.rst` covers the CLI and configuration, while `docs/python.rst` covers the library API. Make all user-facing documentation changes there using its Sphinx/reStructuredText conventions. Keep this repository's `README.md` to essential summaries and links to the published documentation.

## Commit & Pull Request Guidelines

Always use Conventional Commits, e.g. `fix: avoid ...`, `docs: clarify ...`, or `chore(deps): update ...`. Include a concise commit body describing the motivation. For resolved issues, add a `Fixes #123` clause. Keep changes focused. PRs should link issues, include tests and documentation, and pass tests, type checks, and hooks. Include before/after output for CLI changes.

## Security & Configuration

Never commit API keys. With credentials configured, non-local HTTP requires explicit opt-in; prefer HTTPS. Treat URLs, redirects, downloads, paths, and symlinks as security boundaries. Mock APIs with loopback URLs and synthetic credentials.

Check `THREAT_MODEL.md` when changing configuration discovery or precedence, credential sources, HTTP or TLS policy, proxies, URL normalization, redirects, uploads, downloads, filesystem writes, output rendering, the public Python API, or container behavior. Update `THREAT_MODEL.md` in the same change whenever its “Conditions that change this model” apply, including when a claimed security property changes or a vulnerability report exposes a model gap.
