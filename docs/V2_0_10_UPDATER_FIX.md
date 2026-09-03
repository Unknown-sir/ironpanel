# IronPanel v2.0.10 — Updater Fix (no username prompt on public GitHub)

## Problem

On some servers the GitHub updater (`safe_update.sh` → `update_from_github.sh`) gets
stuck at:

```
Username for 'https://github.com':
```

even for a **public** repository. Root cause is usually a leftover **global credential
helper**:

```
git config --global credential.helper 'store --file ~/.git-credentials'
```

Presence of a credential helper makes git prompt for a username (to store credentials)
on **every** HTTPS remote — public repos included. Because the helper's backing file is
empty/missing, git blocks waiting for input forever.

## Fix (in the source)

`scripts/update_from_github.sh` now wraps every network git operation so that the public
fetch/clone never prompts and never uses the leftover helper:

```bash
git_cmd(){ GIT_TERMINAL_PROMPT=0 git -c credential.helper= "$@"; }
```

- `GIT_TERMINAL_PROMPT=0` → fail instead of blocking on a username prompt.
- `-c credential.helper=` → ignore any global/system credential helper for this command.

Both the incremental path (`fetch --depth 1` + `reset --hard`) and the fresh-install
path (`clone --depth 1`) are covered.

## One-time cleanup still recommended on the server

The script fix prevents the hang, but the server's own git config should also be cleaned
once so plain `git` on the command line works the same way:

```bash
git config --global --unset credential.helper
rm -f ~/.git-credentials
```

After that (and with the new updater), updates run fully automatically with no prompt.
