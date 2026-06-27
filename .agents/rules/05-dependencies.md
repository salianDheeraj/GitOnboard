---
trigger: always_on
---

# Dependency Rules

This project uses uv.

Always use:

uv add

uv remove

uv sync

uv run

uv lock

Never use:

pip install

pip freeze

requirements.txt

virtualenv

python -m venv

## Libraries

Prefer the Python standard library.

Before adding a dependency ask:

Can this be implemented cleanly using the existing dependencies?

Only introduce libraries that provide significant value.

Every new dependency must be justified.