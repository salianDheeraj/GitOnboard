---
trigger: always_on
---

# Architecture Rules

Keep the architecture simple.

## Prefer

Modular design

Composition over inheritance

Single responsibility

Clear separation of concerns

## Avoid

Repository Pattern

Factory Pattern

Strategy Pattern

Plugin systems

Dependency Injection frameworks

Event buses

Generic base classes

Microservices

Message queues

unless explicitly requested.

## Placeholder Code

Do not create placeholder implementations.

Do not leave TODOs for future features.

Implement only working code.

## New Files

Before creating a new file:

Check whether an existing file can be extended.

Create a new file only when:

- the responsibility is genuinely different
- the existing module would become difficult to maintain

Avoid helper, manager, wrapper, misc and generic utility modules unless they already exist.