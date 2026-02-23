# Contributing to draftedi-core

`draftedi-core` is an MIT-licensed open-source library and contributions are welcome. This document covers everything you need to get started: signing the CLA, setting up a development environment, running checks, and opening a pull request.

## Contributor License Agreement

You will be asked to sign a CLA (Contributor License Agreement) when you open your first pull request. The CLA ensures contributor IP is properly assigned to the project. **PRs cannot be merged without a completed CLA.** The process is handled automatically via a bot comment on your PR.

## Development setup

```
git clone https://github.com/yawway365/draftedi-core.git
cd draftedi-core
pip install -e ".[dev]"
```

## Running checks

```
pytest                    # 170 tests
ruff check src tests      # linting (100-char line length, Python 3.9 target)
mypy src                  # type checking (strict mode)
```

All three must pass before opening a PR.

## Pull request guidelines

- **New behavior:** add tests that cover the new code paths.
- **Bug fixes:** add a regression test if one does not already exist.
- **Type annotations:** keep `mypy` strict passing. All public functions must have complete type annotations.
- **Linting:** keep `ruff` passing. Line length is 100 characters. Target Python 3.9 for compatibility.
- **Zero runtime dependencies:** do not add packages to the `dependencies` list in `pyproject.toml`. Dev-only tools go under `[dev]` extras only.
- **PR description:** describe what your PR does and why. A sentence or two is enough for small changes; more context is welcome for larger ones.

## Reporting bugs

Open an issue at https://github.com/yawway365/draftedi-core/issues.

Include:

- Python version
- `draftedi` version
- Minimal reproducible example
- What you expected vs. what happened

## Questions

Open a discussion or issue on GitHub.
