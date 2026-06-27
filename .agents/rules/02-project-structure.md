---
trigger: always_on
---

# Repository Structure

The repository structure is fixed.

project-root/

backend/
frontend/
tests/
docs/
scripts/
data/

pyproject.toml
uv.lock
README.md
.gitignore
.env.example

## Rules

Never create source code in the root directory.

Never create documentation in the root directory.

Never create tests in the root directory.

Only configuration files belong in the root.

## Backend

All backend code belongs inside backend/.

## Frontend

All frontend code belongs inside frontend/.

## Documentation

All documentation belongs inside docs/.

README.md is the only markdown file allowed in the project root.

## Tests

All tests belong inside tests/.

Never place tests beside implementation files.

## Scripts

Automation scripts belong inside scripts/.

Never create new top-level folders without approval.