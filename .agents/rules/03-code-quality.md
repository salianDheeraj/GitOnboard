---
trigger: always_on
---

# Code Quality

Write production-quality code.

## Readability

Prefer readability over reducing lines of code.

Use descriptive names.

Avoid deeply nested logic.

Keep functions focused.

Keep modules cohesive.

## Duplication

Do not duplicate code.

Do not duplicate implementations.

Modify existing code whenever possible.

Never create:

parser_v2.py

parser_new.py

parser_fixed.py

graph2.py

old_parser.py

There should be exactly one active implementation.

## Comments

Write comments only when the intent is not obvious.

Do not comment obvious code.

## Module Size

Keep modules reasonably sized.

Split modules only when they become difficult to understand.

Do not split modules prematurely.