---
trigger: always_on
---

# Documentation

Documentation belongs inside docs/.

Do not generate documentation unless:

- setup changes
- architecture changes
- I explicitly request it

Never create markdown files in the project root except README.md.

# Testing

Tests belong inside tests/.

Do not place tests beside implementation files.

Do not generate large test suites automatically.

Generate tests only when:

- explicitly requested
- business logic is non-trivial

Keep tests focused and relevant.