# Contributing to draftedi-core

`draftedi-core` is a MIT-licensed open-source library and contributions are welcome. This document covers everything you need to get started.

## Contributor License Agreement

DraftEDI is a commercial open-source project. The core library is MIT-licensed and always will be. We also operate a commercial SaaS platform built on this library. To keep these coexisting cleanly — both legally and long-term — we require a Contributor License Agreement (CLA) for code contributions.

**What the CLA does:** It grants DraftEDI a license to include your contribution in both the MIT library and the commercial platform. You keep full copyright over your code. The CLA doesn't transfer ownership — it grants a license.

**What it doesn't do:** It doesn't restrict what you can do with your own code. You can still publish your contribution elsewhere, use it in your own projects, do anything you'd normally do with your own work.

**How signing works:** When you open a pull request, a bot will post a comment with a one-click link. You authorize via GitHub OAuth. It takes about 30 seconds.

**Trivial patch exception:** Changes that are 15 lines or fewer, or documentation-only changes (fixing typos, improving wording), do not require a CLA. The bot will recognize these automatically.

**CLA text:** [`.github/CLA.md`](.github/CLA.md). It's short — under 500 words.

If you have questions about the CLA, open a [Discussion](https://github.com/yawway365/draftedi-core/discussions) or email jacksonyawbiz@gmail.com.

## Code of Conduct

This project follows the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md).

## Development Setup

```bash
git clone https://github.com/yawway365/draftedi-core.git
cd draftedi-core
pip install -e ".[dev]"
```

## Running Checks

```bash
pytest                    # run the test suite
ruff check src tests      # linting (100-char line length, Python 3.9 target)
mypy src                  # type checking (strict mode)
```

All three must pass before opening a PR.

## How to Contribute

### Reporting Bugs

Open an issue using the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) template. **Do not report security vulnerabilities in public issues** — use [GitHub Security Advisories](https://github.com/yawway365/draftedi-core/security/advisories/new) instead.

### Requesting Features

Open an issue using the [Feature Request](.github/ISSUE_TEMPLATE/feature_request.md) template. For large changes, open a Discussion first to align before investing in implementation.

### Submitting Pull Requests

- **Branch naming:** `feat/`, `fix/`, `docs/`, `chore/`, `test/`, `refactor/`
- **New behavior:** add tests covering the new code paths
- **Bug fixes:** add a regression test if one does not already exist
- **Type annotations:** keep `mypy` strict passing; all public functions need complete annotations
- **Zero runtime dependencies:** do not add packages to `dependencies` in `pyproject.toml`; dev-only tools go under `[dev]` extras only
- **PR description:** reference the issue it closes (`Closes #N`)
- Maintainers aim to review within 5 business days

## Commit Message Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

Types: feat, fix, docs, chore, test, refactor, ci
Example: fix(parser): handle empty segment terminator
```

## Questions

Open a [Discussion in Q&A](https://github.com/yawway365/draftedi-core/discussions/categories/q-a) for usage questions. For private matters, email jacksonyawbiz@gmail.com.
