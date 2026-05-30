# gbrain stdin Windows fix — PR submission steps

The fix and PR materials are prepped. Run these commands yourself (auto-mode
blocks the assistant from forking external repos):

```bash
# 1. Fork + clone
mkdir -p ~/git && cd ~/git
gh repo fork garrytan/gbrain --clone --remote --fork-name gbrain
cd gbrain

# 2. Branch
git checkout -b fix/stdin-windows-fd0

# 3. Apply the patch
git am ~/daily-automation/state/gbrain-pr/0001-fix-stdin-windows.patch
# If `git am` complains about the placeholder hashes, instead just edit the
# two files manually:
#   src/cli.ts:137              '/dev/stdin', 'utf-8'  →  0, 'utf-8'
#   src/commands/report.ts:44   '/dev/stdin', 'utf-8'  →  0, 'utf-8'
# then: git add -u && git commit -m "fix(cli): use stdin fd 0 instead of /dev/stdin path for Windows compat"

# 4. Push + open PR
git push -u origin fix/stdin-windows-fd0
gh pr create --repo garrytan/gbrain \
  --title "fix(cli): use stdin fd 0 instead of /dev/stdin path for Windows compat" \
  --body-file ~/daily-automation/state/gbrain-pr/PR_BODY.md
```

## Files in this dir

- `0001-fix-stdin-windows.patch` — git-am-able patch (placeholder hashes; will
  apply with `git am --3way` or just hand-edit per the README above)
- `PR_BODY.md` — the markdown body for the GitHub PR
- `README.md` — this file
