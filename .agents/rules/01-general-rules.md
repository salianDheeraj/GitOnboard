---
trigger: always_on
---

# General Engineering Rules

These rules apply to every task.

## Philosophy

- Build only the requested feature.
- Keep the implementation simple and maintainable.
- Avoid overengineering.
- Avoid premature optimization.
- Do not implement future features.
- Every phase should leave the project in a working state.

## Code Changes

- Modify only files related to the current task.
- Do not refactor unrelated code.
- Do not rename files unless requested.
- Do not reorganize the project structure.

## Simplicity

Prefer:

- explicit code
- straightforward logic
- readable implementations

Avoid:

- clever solutions
- unnecessary abstractions
- speculative architecture

## YAGNI

Every abstraction must solve an existing problem.

Do not introduce abstractions for anticipated future requirements.

## Existing Code

Treat the existing implementation as the source of truth.

Never create a second implementation of an existing feature.