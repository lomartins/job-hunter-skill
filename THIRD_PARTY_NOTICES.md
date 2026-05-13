# Third-Party Notices

This file aggregates the licenses and copyright notices of third-party software bundled or required by the `job-hunter` plugin. Direct dependencies are listed below; transitive dependencies inherit through these.

Run `uv tree --no-dev` for a complete resolved list, and `uv pip licenses` (or `pip-licenses`) to dump a machine-readable manifest before any release.

## Direct dependencies

| Package | License | Project URL |
|---------|---------|-------------|
| typer | MIT | https://github.com/fastapi/typer |
| rich | MIT | https://github.com/Textualize/rich |
| httpx | BSD-3-Clause | https://github.com/encode/httpx |
| playwright | Apache-2.0 | https://github.com/microsoft/playwright-python |
| sqlmodel | MIT | https://github.com/fastapi/sqlmodel |
| pydantic | MIT | https://github.com/pydantic/pydantic |
| pydantic-settings | MIT | https://github.com/pydantic/pydantic-settings |
| apscheduler | MIT | https://github.com/agronholm/apscheduler |
| tenacity | Apache-2.0 | https://github.com/jd/tenacity |
| selectolax | MIT | https://github.com/rushter/selectolax |
| python-dotenv | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| pluggy | MIT | https://github.com/pytest-dev/pluggy |
| pyyaml | MIT | https://github.com/yaml/pyyaml |
| feedparser | BSD-2-Clause | https://github.com/kurtmckee/feedparser |
| platformdirs | MIT | https://github.com/platformdirs/platformdirs |

## Dev dependencies

| Package | License |
|---------|---------|
| pytest | MIT |
| pytest-asyncio | Apache-2.0 |
| pytest-playwright | Apache-2.0 |
| vcrpy | MIT |
| ruff | MIT |
| mypy | MIT |
| detect-secrets | Apache-2.0 |
| freezegun | Apache-2.0 |

## Bundled assets

`skills/job-hunter/assets/adapters/*.yaml` — Apache-2.0 (Luisa Martins). The selectors and labels in these files are factual descriptions of public web forms; no IP from ATS vendors is claimed.

`skills/job-hunter/assets/field_labels.yaml` — Apache-2.0. The dictionary is hand-curated from common BR/EN application form labels.

## Process for adding a dependency

1. Add to `pyproject.toml` with an upper-bound version constraint.
2. Run `uv lock` to update `uv.lock`.
3. Add a row to this file with the dependency's license.
4. Bump `version` in `.claude-plugin/marketplace.json` and `skills/job-hunter/SKILL.md`.
