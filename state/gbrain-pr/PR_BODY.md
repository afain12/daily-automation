## Summary

`gbrain put` and `gbrain report` crash on Windows with `ENOENT: no such file or directory, open '/dev/stdin'` whenever stdin is piped/redirected/here-string'd. Windows (Git Bash, MSYS, PowerShell, cmd) doesn't expose `/dev/stdin` as a real filesystem path, so `readFileSync('/dev/stdin', ...)` always fails.

Fix: pass file descriptor `0` instead of the path string. Both Node and Bun's `readFileSync` accept an fd as the first arg, and the behavior is identical to opening `/dev/stdin` on Unix. One-character change, two files.

## Repro (Windows Git Bash, Bun-installed gbrain 0.18.2)

```bash
$ echo "hello" | gbrain put test-page
ENOENT: no such file or directory, open '/dev/stdin'

$ gbrain put test-page <<< "hello"
ENOENT: no such file or directory, open '/dev/stdin'

$ gbrain put test-page < /tmp/x.txt
ENOENT: no such file or directory, open '/dev/stdin'
```

All three stdin patterns fail. The only workaround is `--content "..."`, which is awkward for multi-line markdown.

## After patch

```bash
$ echo "hello" | gbrain put test-page
{
  "slug": "test-page",
  "status": "created_or_updated",
  "chunks": 1,
  ...
}
```

## Files changed

- `src/cli.ts:137` — stdin for content params on any operation with `cliHints.stdin`
- `src/commands/report.ts:44` — stdin for `gbrain report --content` fallback

## Test plan

- [x] macOS unchanged (fd 0 == `/dev/stdin` on Unix; identical bytes returned)
- [x] Linux unchanged (same)
- [x] Windows Git Bash: `echo x | gbrain put slug` now succeeds
- [ ] Windows PowerShell: `"x" | gbrain put slug` should also work
- [ ] CI matrix should include a Windows runner for stdin coverage (not in this PR)

## Notes

This is the minimum viable fix. A separate PR could add a Windows CI job to prevent regression.
