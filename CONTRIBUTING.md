# Contributing

## Git Hooks

To prevent pushing stale code that will fail the CI `Prevent Stale PRs` workflow, you should enable the local Git hooks provided in this repository.

Run the following command once in your local repository checkout:

```bash
git config core.hooksPath .githooks
```

### What this does:
When you attempt to `git push`, the `pre-push` hook will automatically run. It fetches the latest changes from `origin` (and `upstream` if configured) and checks if your current branch is missing any commits from the target branch. If your branch is behind, it will block the push and instruct you to pull or rebase your branch, preventing a stale PR from being opened or updated.
