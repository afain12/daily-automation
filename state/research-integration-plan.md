# Research Agent Integration — Decision Doc

**Status:** Plan locked, not yet installed. Resume from "Install order" section.
**Decided:** 2026-04-28
**Origin:** Aaron wants a `/research <topic>` flow that does deep research → NotebookLM audio episode for commute learning. PCMH was the example topic.

## Stack (locked)

| Layer | Choice | Why |
|-------|--------|-----|
| Research engine | `google-gemini/gemini-skills@gemini-interactions-api` | Deep Research agents support, free Gemini API tier, stays in Google ecosystem we already use (`gws`), no Homebrew/browser deps |
| Audio output | `joeseesun/anything-to-notebooklm@anything-to-notebooklm` | Only candidate that actually generates the two-host English MP3 podcast. Inputs: URLs/PDFs/MD/text → MP3 |
| Orchestration | New project skill `.claude/skills/research/skill.md` | Owns trust gates, output routing, department tagging |

## Rejected candidates (and why)

- **199-biotechnologies/claude-deep-research-skill** — requires `search-cli` via Homebrew. Aaron is on Windows 11. Hard blocker.
- **pleaseprompto/notebooklm-skill** — Q&A on existing notebooks only. Does NOT generate audio overviews. Wrong tool.
- **langchain-ai/deepagents@web-research** — docs too thin to verify behavior; skip unless Gemini path fails.
- **tavily-ai/skills@research** — works fine, but adds another vendor + API key. Fallback only if Gemini path fails.

## Install order (resume here tomorrow)

1. Confirm Google AI Studio API key exists (or provision free-tier one)
2. `npx skills add google-gemini/gemini-skills -s gemini-interactions-api` (lands in skills-lock.json)
3. `npx skills add joeseesun/anything-to-notebooklm -s anything-to-notebooklm`
4. Create `.secrets/gemini.env` per existing `.secrets/notion.env` pattern; mirror `GEMINI_API_KEY` to `.claude/settings.local.json`
5. One-time `notebooklm login` (interactive Chrome window — must run outside auto mode)
6. Write `.claude/skills/research/skill.md` orchestrator (see "Wrapper requirements" below)
7. Smoke test: `/research "PCMH recognition pathway"` (IPA-relevant) and `/research "value-based care models for urgent care"` (Nestmate-relevant). Verify English two-host audio works (joeseesun is Chinese-dev focused — English path is supported but unproven).

## Wrapper requirements (`.claude/skills/research/skill.md`)

Five things the off-the-shelf skills don't handle that our project patterns require:

1. **Trust gate / staged writes.** Brief lands as `.context/research-{topic}-{date}.json`. Approve → PATCH to Notion → `mv` to `.context/applied/`. Per `feedback_context_cleanup.md` — never silently re-PATCH.
2. **Output routing.**
   - Brief → `vault/research/{topic}-{date}.md` (new folder, add to CLAUDE.md project structure table)
   - MP3 → `vault/audio/` (or push to a Drive folder so it shows in Drive mobile app for commute)
   - Follow-up "Listen on commute" task → Notion Master Tasks
   - Episode link + 1-line summary → Activity Log entry
3. **Department tagging.** Reuse `config/sources.yaml` keyword classifier. PCMH/credentialing → United IPA, cardiac monitoring → Dock Pro, urgent care/account → Nestmate, panel/specimen → Lab. Sets Workspace field on the Notion task.
4. **Existing-skill hooks.**
   - `/capture-meeting`: detect "research X" mentions in meeting notes, queue to a backlog file
   - `/start-day`: surface "ready research briefs not yet listened to" (check `vault/research/` for files w/o a matching `vault/audio/*.mp3`)
   - `/end-day`: log episodes consumed today (read MP3 mtimes or add a checkbox in daily note)
5. **Auto-mode classifier.** Browser automation will trip the classifier. Pre-authenticate NotebookLM once out-of-band, add Playwright Chrome path to `autoMode.environment` as trusted research workflow. Document in CLAUDE.md.

## Open questions for Aaron

- Do you have a Google AI Studio API key, or do we provision?
- MP3 destination preference: `vault/audio/` (offline) vs Drive folder (syncs to phone Drive app)?
- Department keyword for "research" itself — should research tasks land under the topic's department, or get an "Other / Personal" learning bucket?

## Files this will touch when implemented

- `skills-lock.json` (+2 entries)
- `.secrets/gemini.env` (new)
- `.claude/settings.local.json` (GEMINI_API_KEY mirror, autoMode.environment note)
- `.claude/skills/research/skill.md` (new)
- `config/sources.yaml` (research keyword section if needed)
- `CLAUDE.md` (new vault/research/ + vault/audio/ in project structure, /research in skills table)
- `vault/research/` and `vault/audio/` (new folders)
