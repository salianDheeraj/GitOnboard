# Custom Rules

## WSL File Deletion
When working in a WSL environment (`\\wsl.localhost\Ubuntu\...`) via PowerShell, avoid using `Remove-Item` for deleting directories, as it often fails with nested paths and symlinks. Instead, drop into the native Linux environment using `wsl -d Ubuntu -e bash -c "rm -rf <path>"` to ensure reliable deletion.
