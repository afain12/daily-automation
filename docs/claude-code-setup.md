# Claude Code Operating Guide — daily-automation

How to run Claude Code in this repo. Keep current; this is how future-you (and future-Claude) stay consistent across sessions.

## Configuration files — what goes where

| File | Scope | Gitignored? | Holds |
|------|-------|-------------|-------|
| `.claude/settings.json` | Project (shared) | No — commit | Trust rules, hooks, non-secret config. Document intent for future-you. |
| `.claude/settings.local.json` | Project (this machine) | Yes | `NOTION_API_TOKEN` (mirrored from `.secrets/`), `permissions.allow` patterns, `autoMode.environment` prose rules |
| `.secrets/*.env` | Project (this machine) | Yes | **Canonical source** for API tokens. Shell scripts source from here. See `.secrets/README.md`. |
| `~/.claude/settings.json` | User (all projects) | N/A | Theme, keybindings, status line, personal model defaults |

**Secrets pattern:** `.secrets/notion.env` is the canonical store. Claude Code itself reads `NOTION_API_TOKEN` from `.claude/settings.local.json` (it has no native env-file support), so the value is **mirrored** between the two files. When rotating, update both. The `.secrets/` folder also serves as the source for any manual shell scripts (`source .secrets/notion.env`).

Currently nearly everything lives in `settings.local.json` because this is a single-user, single-machine setup. If a second machine ever joins, promote the `autoMode.environment` block and the documented `permissions.allow` wildcards into a committed `.claude/settings.json`; keep only secrets (`NOTION_API_TOKEN`) in `.local.json`.

## Permission modes — when to use which

Cycle with `Shift+Tab` or launch with `claude --permission-mode <mode>`.

| Mode | When to use |
|------|-------------|
| `default` | Skill development / debugging. Prompts on first use, approve once, stays approved. |
| `acceptEdits` | Routine day-to-day editing. Auto-accepts file edits in the working directory; still prompts for Bash. |
| `auto` | Stable, known workflows (`/start-day`, `/end-day`, `/capture-meeting`). AI classifier auto-approves safe calls and blocks risky ones. Tune via `autoMode.environment`. |
| `plan` | Big structural changes. Claude reviews and proposes before touching anything. |

**Do not** set `defaultMode: "auto"` in committed settings — activate per-session instead. Committing auto mode would fire it at every session start, including ones where you're touching config or experimenting with new skills.

## Auto mode — how ours is configured

- `autoMode.environment` in `settings.local.json` describes trusted infrastructure (api.notion.com, gws, vault paths, OneDrive reads) so the classifier understands that routine Notion/Calendar/Tasks writes are the purpose of this project, not exfiltration.
- Do **not** set `autoMode.allow` or `autoMode.soft_deny` — setting either replaces the entire default list for that section, which would remove ~30 protective rules (force push, mass deletion, impersonation, credential leakage, production deploys, etc.).
- After any edit to `autoMode.environment`, run `claude auto-mode critique` to validate.
- Default `soft_deny` rules that will still prompt even in auto mode, by design:
  - **Self-Modification:** edits to `.claude/settings.local.json` always prompt.
  - **External System Writes:** modifying Notion/Tasks/Calendar items not created in the current session prompts unless the user's message specifically authorizes it.

## Skill authoring conventions

- One skill per task boundary (`start-day`, `capture-meeting`, `end-day`). Don't merge or overload.
- Each skill: `.claude/skills/{name}/SKILL.md` with frontmatter (`name`, `description`).
- Keep `SKILL.md` under ~500 lines. Long reference tables go in sibling files (`reference.md`, config in `config/*.yaml`).
- Extract reusable bash (e.g. a Notion curl wrapper) to `scripts/*.sh` next to the skill once it exceeds ~10 lines or is used by 2+ skills. Until then, inline is fine.
- Tail every curl with `--max-time 60` so a stuck API doesn't hang the skill.
- Every skill must degrade gracefully per the Error Handling Patterns in `CLAUDE.md` — if a source is down, run with what's available and report what was skipped.

## When to delegate to subagents

Use a subagent when the work produces output you don't need to keep in main context:

- **Explore agent** — scanning the vault ("find all notes mentioning Dr Ling"), reading many meeting notes, cross-referencing logs. Returns a summary, not raw files.
- **general-purpose agent** — multi-step research that would otherwise clutter context.
- **Don't delegate:** Notion writes, the main `/start-day` briefing, `/capture-meeting` routing decisions, or anything with a trust gate — those stay inline.

## Committing settings changes

- `settings.local.json` is gitignored — never stages.
- After tuning `autoMode.environment` or `permissions.allow`, note the change in the current day's log (`logs/YYYY-MM-DD.md`) so future-you knows why a rule exists.
- Test wildcard patterns before removing specific allow entries. Run a real command that matches the wildcard and confirm no prompt appears.
