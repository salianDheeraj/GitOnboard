---
trigger: always_on
---

# Never Do These Things

Never place backend code outside backend/.

Never place frontend code outside frontend/.

Never place tests outside tests/.

Never place documentation outside docs/ (except README.md).

Never use pip. Always use uv.

Never create duplicate implementations.

Never create placeholder code.

Never create parser_v2.py, graph_new.py, auth_old.py or similar files.

Never rewrite unrelated code.

Never perform large refactors while implementing a feature.

Never introduce new architectural patterns without a clear need.

Never create unnecessary files, folders, or abstractions.

Never leave the project in a partially implemented or broken state.

Always keep the application runnable after completing a task.