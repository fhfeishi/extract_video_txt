# Git Logs

## 2026-06-07 - Push rejected by non-fast-forward

### Problem

Running `git push -u origin main` failed with a non-fast-forward rejection:

```text
! [rejected] main -> main (non-fast-forward)
Updates were rejected because the tip of your current branch is behind
its remote counterpart.
```

The local `main` branch and remote `origin/main` each had an initial commit. The remote branch contained a `LICENSE` file that was not present locally, so Git refused to overwrite remote history with a normal push.

### Solution

Fetched the remote branch and merged it into local `main` while allowing the two separately initialized histories to be joined:

```bash
git fetch origin
git merge origin/main --allow-unrelated-histories --no-edit
```

The merge succeeded and added the remote `LICENSE` file locally. After recording this note, commit the log update and push `main` again with upstream tracking:

```bash
git add git_logs.md
git commit -m "Document git push resolution"
git push -u origin main
```
