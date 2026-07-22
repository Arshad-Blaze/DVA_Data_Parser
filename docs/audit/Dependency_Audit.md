# Dependency Audit

## requirements.txt (runtime)

| Package | Version | Used | Purpose | Status |
|---------|---------|------|---------|--------|
| polars | >=1.0,<2.0 | ✅ Yes | Core data processing | ✅ Keep |
| streamlit | >=1.28 | ✅ Yes | UI framework | ✅ Keep |
| psutil | >=5.9 | ✅ Yes | Memory/CPU monitoring | ✅ Keep |
| openpyxl | >=3.1 | ✅ Yes | Excel output | ✅ Keep |
| paramiko | >=3.0 | ✅ Yes | SSH/SFTP datasource | ✅ Keep (optional) |

## requirements-dev.txt (development)

| Package | Version | Used | Purpose | Status |
|---------|---------|------|---------|--------|
| pytest | >=8.0 | ✅ Yes | Testing | ✅ Keep |
| pytest-playwright | >=0.4 | ✅ Yes | E2E testing | ✅ Keep |
| playwright | >=1.40 | ✅ Yes | Browser automation | ✅ Keep |
| requests | >=2.31 | ❓ Partially | E2E test utilities | ⚠️ Review |
| pytest-html | >=4.0 | ✅ Yes | HTML test reports | ✅ Keep |

## pyproject.toml

Matches `requirements.txt`. `paramiko` listed as optional `[ssh]` dependency. Dev dependencies under `[project.optional-dependencies] dev`.

## pyiceberg Investigation

| Question | Answer |
|----------|--------|
| Is pyiceberg in any requirements file? | ❌ Not in requirements.txt or pyproject.toml |
| Is pyiceberg imported anywhere? | ❌ Not found in any source file |
| Does pyiceberg exist in the environment? | ❓ Not confirmed in .venv |
| Should it be removed? | ✅ No action needed — not a dependency |

## Findings

1. **DA-1: requests may be unused** — Only referenced in test files. Consider if E2E tests actually use it.
2. **DA-2: No upper bound on streamlit** — `>=1.28` could cause unexpected breaks with major version upgrades.
3. **DA-3: No type-checking packages** — No mypy, pyright, or type stubs in dev dependencies.
4. **DA-4: No linting packages** — No ruff, flake8, pylint in dev dependencies.
5. **DA-5: Python version >=3.10** — Good. Polars 1.x requires >=3.10.

## Recommendations

1. Pin streamlit to `<2.0` for stability
2. Add `ruff` or `pylint` to dev dependencies
3. Remove `requests` if E2E tests don't use it (or confirm it's needed for Playwright)
4. Add `mypy` or `pyright` for type checking
