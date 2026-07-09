# Deployment audit template

Use this document as a public-safe checklist for hosting the automation system.

## Goals

- Keep secrets outside git.
- Keep runtime state local to the host.
- Run scheduled jobs with explicit source and write permissions.
- Require approval gates for outbound communication and external writes.

## Checklist

- [ ] Repository contains no logs, exported source payloads, personal notes, or customer records.
- [ ] `.env`, `.secrets/`, OAuth files, and browser profiles are ignored.
- [ ] Notion/Google credentials are scoped to least privilege.
- [ ] Calendar writes are staged or proposed before modifying the primary calendar.
- [ ] Email/outbound communication is draft-first unless explicitly approved.
- [ ] Secret and privacy scans pass before publishing.
