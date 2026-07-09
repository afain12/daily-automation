# Anthropic Claude Code Best Practices (Aligned 2026-05-19)

Canonical Anthropic principles applied to this repo. When the docs update and a principle changes, this file is wrong — update it.

Source docs:
- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Skill authoring best practices](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices)
- [Sub-agents](https://code.claude.com/docs/en/sub-agents)
- [Auto-mode](https://www.anthropic.com/engineering/claude-code-auto-mode)

## Context is the constraint

> *"Most best practices are based on one constraint: Claude's context window fills up fast, and performance degrades as it fills."*

Practical implications we hold to:
- **`/clear` between unrelated tasks.** Don't kitchen-sink a session.
- **After two failed corrections, `/clear` and rewrite the prompt** incorporating what you learned. A clean session with a better prompt outperforms a long session with accumulated corrections.
- **Delegate exploration to sub-agents** ("use subagents to investigate X"). They read in a separate context and return a summary, keeping main context lean.
- **Skills > CLAUDE.md for domain content.** Skills load on demand; CLAUDE.md loads every turn.

## Skills vs CLAUDE.md vs Hooks — the load-bearing distinction

| Lever | When loaded | Use for |
|-------|-------------|---------|
| **CLAUDE.md** | Every session, always in context | Project facts Claude can't infer from code, repo etiquette, gotchas. Be ruthless about pruning — bloated CLAUDE.md causes Claude to ignore important rules. |
| **Skill (`SKILL.md`)** | Description metadata always loaded; body loads only when invoked or auto-triggered by description match | Domain knowledge or workflows relevant *sometimes*. Long reference material costs almost nothing until needed. |
| **Sub-agent (`.claude/agents/<name>.md`)** | Loaded only when delegated to | Side tasks that would flood main context with file reads, search results, or logs you won't reference again. |
| **Hook (`.claude/settings.json`)** | Triggered by tool events | Things that MUST happen every time with zero exceptions. Hooks are deterministic; CLAUDE.md is advisory. |

**Rule of thumb for CLAUDE.md entries:** *"Would removing this cause Claude to make mistakes?"* If not, cut it or convert to a skill / hook.

## Explore → Plan → Implement → Commit

For multi-file or uncertain changes, use **plan mode** first:
1. **Explore** (plan mode): Claude reads files, answers questions, no writes.
2. **Plan**: ask for a detailed implementation plan; press `Ctrl+G` to edit it.
3. **Implement** (default mode): switch out and code against the plan.
4. **Commit**: descriptive message, PR if needed.

**Skip planning** when you could describe the diff in one sentence — typos, log lines, single-line fixes.

## Verification beats trust

> *"Provide verification criteria. This is the single highest-leverage thing you can do."*

For every non-trivial change: provide tests, screenshots, expected outputs, or a linter command. The current skill set already enforces this via trust gates + telemetry; new skills should preserve it.

## Auto mode is for trusted workflows, not config edits

- **Default**: prompts on first use of a tool, then remembered.
- **`acceptEdits`**: auto-accepts file edits in the working dir; still prompts on Bash.
- **`auto`**: classifier auto-approves safe calls and blocks risky ones. Use for stable workflows like `/start-day`, `/end-day`, `/capture-meeting`.
- **`plan`**: required for structural changes.

Auto mode automatically drops blanket shell/interpreter rules from `permissions.allow` on activation, and escalates to human review after 3 consecutive or 20 total denials.

**Do NOT** set `autoMode.allow` or `autoMode.soft_deny` in settings — doing so replaces the ~30 default protective rules (force push, mass deletion, impersonation, credential leakage). Tune `autoMode.environment` only.

**Do NOT** set `defaultMode: "auto"` in committed settings. Activate per-session.

## Common failure patterns to avoid

| Failure | Fix |
|---------|-----|
| **Kitchen-sink session** — one task → unrelated → back to first → context full of noise | `/clear` between unrelated tasks |
| **Correcting over and over** — same issue, repeated corrections | After 2 failed corrections, `/clear` + better initial prompt |
| **Over-specified CLAUDE.md** — too long, important rules get lost | Ruthlessly prune. If a rule's already followed, delete it or convert to hook |
| **Trust-then-verify gap** — plausible code that doesn't handle edges | Always provide verification (tests, screenshots, scripts). If you can't verify, don't ship |
| **Infinite exploration** — unscoped investigation reads hundreds of files | Scope narrowly OR delegate to subagent so exploration doesn't consume main context |

## Skill authoring conventions (Anthropic)

1. **Filename:** uppercase `SKILL.md` per Anthropic convention.
2. **Frontmatter:** `name` (lowercase-numbers-hyphens, max 64 chars, no "anthropic"/"claude") and `description` (≤1024 chars, third-person, includes both *what* and *when*).
3. **Body:** ≤ 500 lines. Split overflow into sibling files referenced one level deep.
4. **Use `disable-model-invocation: true`** on skills with side effects you want to trigger manually (the `*-team` experiments have this — Claude won't auto-pick them over the baseline).
5. **Use `allowed-tools`** to pre-approve specific Bash patterns the skill needs (e.g., `Bash(curl https://api.notion.com/*)`, `Bash(gws *)`, `Bash(scripts/*)`).
6. **Still complete all 16 AAC spec sections** before building (project rule — complements but doesn't replace the Anthropic conventions above).

## Skill & agent file layout (this repo)

- **`.claude/skills/<name>/SKILL.md`** — project skills (authoritative).
- **`.claude/agents/<name>.md`** — custom subagent definitions. Use when the same worker shape recurs across multiple skills. Per Anthropic: *"Define a custom subagent when you keep spawning the same kind of worker with the same instructions."*
- **`.agents/skills/`** — external dependency skills pulled via `skills-lock.json`. Don't edit; they get overwritten on update.

## Working with sub-agents

Use a sub-agent when a side task would flood your main conversation with output you won't reference again. Each sub-agent runs in its own context with its own tools.

In this repo:
- **`Explore`** (read-only) for all source-pull workers in `*-team` skills.
- **`general-purpose`** only when a worker needs Edit/Write (rare — coordinator usually owns writes).
- **Custom subagents in `.claude/agents/`** for recurring worker shapes. Start with `.claude/agents/notion-puller.md` and add more as patterns repeat.
