# Contributing

## Git Hooks

To prevent pushing stale code that will fail the CI `Prevent Stale PRs` workflow, you should enable the local Git hooks provided in this repository.

Run the following command once in your local repository checkout:

```bash
git config core.hooksPath .githooks
```

### What this does:
When you attempt to `git push`, the `pre-push` hook will automatically run. It fetches the latest changes from `origin` (and `upstream` if configured) and checks if your current branch is missing any commits from the target branch. If your branch is behind, it will block the push and instruct you to pull or rebase your branch, preventing a stale PR from being opened or updated.

## Architecture Guidelines

If you are adding new backend features, please keep the following in mind:
- **Background Tasks**: Long-running operations should be offloaded to `BackgroundTasks` or the `AnalysisWorker` queue.
- **Real-Time Updates**: If your background task has a user-facing loading state, track its status in the `TaskStatus` database model and use `task_manager.notify(...)` to instantly push the update via SSE to the frontend.
- **Database**: All persistent state should live in the PostgreSQL database using SQLAlchemy models, not in local JSON files.
