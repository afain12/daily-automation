# Notion Workspace Probe — 2026-05-20

**Run ID:** np-20260520-test
**Mode:** draft
**Data sources visible:** 12

## Role Candidates

### Master Tasks
1. **"Master Tasks"** — confidence **high** (1.00)
   - id: `528d24b8-e1e6-4ca0-a7ee-87f70a4f7980`
   - Matched: status property, due-date property, assignee people property, workspace/category select, title contains task-word, active (assumed)
   - Properties: Status (status), Due (date), Category (select), Workspace (select), Subtasks (relation), Nestmate Account (relation), Related to Meeting Notes (Related Tasks) (relation), Parent Task (relation)
2. **"Speciality Pharmacy Account Tracking"** — confidence **medium** (0.75)
   - id: `32ca3158-59b4-81d0-9877-000b8bcd5639`
   - Matched: status property, due-date property, assignee people property, active (assumed)
   - Properties: Due date (date), Status (status), Priority (select), Master Task (relation), Past due (formula), Description (rich_text), Effort level (select), Assignee (people)
3. **"Client Tracker"** — confidence **medium** (0.50)
   - id: `286a3158-59b4-8006-96ce-000b465aeb23`
   - Matched: status property, workspace/category select, active (assumed)
   - Properties: Start Date (date), Contact Person (rich_text), Contact Phone (phone_number), Status (status), Contact Email (email), Project Type (select), Client Name (title)

→ **Best guess:** "Master Tasks" — confidence 1.00

### Provider CRM
1. **"Provider CRM"** — confidence **high** (1.00)
   - id: `ae0a3158-59b4-8235-b7ca-0758daa2322a`
   - Matched: has relation property, email property, phone_number property, stage/status select, title contains CRM-word
   - Properties: Updated (last_edited_time), Next Step (rich_text), Workspace (select), Phone (phone_number), Created (created_time), Notes (rich_text), Stage (select), IPA Affiliation (rich_text)
  - (container has multiple data sources — additional id: `062feecb-7cea-4522-9283-64ba07f0c109`)
2. **"Client Tracker"** — confidence **high** (0.80)
   - id: `286a3158-59b4-8006-96ce-000b465aeb23`
   - Matched: email property, phone_number property, stage/status select, title contains CRM-word
   - Properties: Start Date (date), Contact Person (rich_text), Contact Phone (phone_number), Status (status), Contact Email (email), Project Type (select), Client Name (title)
3. **"Speciality Pharmacy Account Tracking"** — confidence **medium** (0.65)
   - id: `32ca3158-59b4-81d0-9877-000b8bcd5639`
   - Matched: has relation property, stage/status select, title contains CRM-word
   - Properties: Due date (date), Status (status), Priority (select), Master Task (relation), Past due (formula), Description (rich_text), Effort level (select), Assignee (people)
4. **"SAIPA Providers (Accounts)"** — confidence **medium** (0.60)
   - id: `c5df7c95-38e8-4267-8862-afdbada95a8b`
   - Matched: phone_number property, stage/status select, title contains CRM-word
   - Properties: Specialty 3 (select), Tax ID (number), Last Contact (date), Notes (rich_text), Provider State (select), Title (select), Specialty 1 (select), Provider Address 1 (rich_text)
5. **"Master Tasks"** — confidence **low** (0.35)
   - id: `528d24b8-e1e6-4ca0-a7ee-87f70a4f7980`
   - Matched: has relation property, stage/status select
   - Properties: Status (status), Due (date), Category (select), Workspace (select), Subtasks (relation), Nestmate Account (relation), Related to Meeting Notes (Related Tasks) (relation), Parent Task (relation)

→ **Best guess:** "Provider CRM" — confidence 1.00

### Activity Log
1. **"Activity Log"** — confidence **high** (0.85)
   - id: `3db174bf-c997-4a41-93ee-36f280e511db`
   - Matched: title contains log-word, date property, type/outcome select, outcome/next rich_text
   - Properties: Provider (relation), Created (created_time), Outcome (rich_text), Date (date), Type (select), Next Action (rich_text), Workspace (select), Nestmate Account (relation)
2. **"Communications Log"** — confidence **high** (0.85)
   - id: `a82399e1-9fab-43bd-af3e-bd869f99248a`
   - Matched: title contains log-word, date property, type/outcome select, outcome/next rich_text
   - Properties: Contact (rich_text), Follow-up date (date), Date/Time (date), Outcome / Notes (rich_text), Channel (select), Attachments (files), Owner (people), Next step (rich_text)
3. **"Speciality Pharmacy Account Tracking"** — confidence **medium** (0.55)
   - id: `32ca3158-59b4-81d0-9877-000b8bcd5639`
   - Matched: date property, type/outcome select, recently edited (<=14d)
   - Properties: Due date (date), Status (status), Priority (select), Master Task (relation), Past due (formula), Description (rich_text), Effort level (select), Assignee (people)
4. **"Provider CRM"** — confidence **low** (0.45)
   - id: `ae0a3158-59b4-8235-b7ca-0758daa2322a`
   - Matched: date property, outcome/next rich_text, recently edited (<=14d)
   - Properties: Updated (last_edited_time), Next Step (rich_text), Workspace (select), Phone (phone_number), Created (created_time), Notes (rich_text), Stage (select), IPA Affiliation (rich_text)
5. **"SAIPA Providers (Accounts)"** — confidence **low** (0.40)
   - id: `c5df7c95-38e8-4267-8862-afdbada95a8b`
   - Matched: date property, type/outcome select
   - Properties: Specialty 3 (select), Tax ID (number), Last Contact (date), Notes (rich_text), Provider State (select), Title (select), Specialty 1 (select), Provider Address 1 (rich_text)
6. **"Client Tracker"** — confidence **low** (0.40)
   - id: `286a3158-59b4-8006-96ce-000b465aeb23`
   - Matched: date property, type/outcome select
   - Properties: Start Date (date), Contact Person (rich_text), Contact Phone (phone_number), Status (status), Contact Email (email), Project Type (select), Client Name (title)
7. **"Standups & Reviews"** — confidence **low** (0.40)
   - id: `64918ff0-05f6-4cf2-ab06-bc0ff3d44ca2`
   - Matched: date property, type/outcome select
   - Properties: Date (date), Created (created_time), Type (select), Title (title)
  - (container has multiple data sources — additional id: `062feecb-7cea-4522-9283-64ba07f0c109`)
8. **"Reflections"** — confidence **low** (0.30)
   - id: `233a3158-59b4-8079-9fce-000b6d5caa7b`
   - Matched: date property, outcome/next rich_text
   - Properties: Next Steps (rich_text), Follow-up Date (date), Meeting Date (date), Voice Recording (url), Key Contact (rich_text), Key Highlights (rich_text), Potential Value (select), Key Insights (rich_text)

→ **Best guess:** "Activity Log" — confidence 0.85

### Meeting Notes
1. **"Meeting Notes"** — confidence **high** (1.00)
   - id: `22ba3158-59b4-804d-9c1c-000b9fad40ae`
   - Matched: title contains meeting-word, date property, people property (attendees), summary/recap property, relation -> master tasks
   - Properties: Related Tasks (relation), Summary (rich_text), Created by (created_by), Workspace (select), Attendees (people), Category (multi_select), Date (date), Meeting name (title)
2. **"Speciality Pharmacy Account Tracking"** — confidence **medium** (0.55)
   - id: `32ca3158-59b4-81d0-9877-000b8bcd5639`
   - Matched: date property, people property (attendees), relation -> master tasks
   - Properties: Due date (date), Status (status), Priority (select), Master Task (relation), Past due (formula), Description (rich_text), Effort level (select), Assignee (people)
3. **"Master Tasks"** — confidence **medium** (0.55)
   - id: `528d24b8-e1e6-4ca0-a7ee-87f70a4f7980`
   - Matched: date property, people property (attendees), relation -> master tasks
   - Properties: Status (status), Due (date), Category (select), Workspace (select), Subtasks (relation), Nestmate Account (relation), Related to Meeting Notes (Related Tasks) (relation), Parent Task (relation)
4. **"Communications Log"** — confidence **medium** (0.55)
   - id: `a82399e1-9fab-43bd-af3e-bd869f99248a`
   - Matched: date property, people property (attendees), summary/recap property
   - Properties: Contact (rich_text), Follow-up date (date), Date/Time (date), Outcome / Notes (rich_text), Channel (select), Attachments (files), Owner (people), Next step (rich_text)
5. **"Standups & Reviews"** — confidence **medium** (0.50)
   - id: `64918ff0-05f6-4cf2-ab06-bc0ff3d44ca2`
   - Matched: title contains meeting-word, date property
   - Properties: Date (date), Created (created_time), Type (select), Title (title)
6. **"Activity Log"** — confidence **medium** (0.50)
   - id: `3db174bf-c997-4a41-93ee-36f280e511db`
   - Matched: date property, summary/recap property, relation -> master tasks
   - Properties: Provider (relation), Created (created_time), Outcome (rich_text), Date (date), Type (select), Next Action (rich_text), Workspace (select), Nestmate Account (relation)
7. **"Provider CRM"** — confidence **low** (0.35)
   - id: `ae0a3158-59b4-8235-b7ca-0758daa2322a`
   - Matched: date property, relation -> master tasks
   - Properties: Updated (last_edited_time), Next Step (rich_text), Workspace (select), Phone (phone_number), Created (created_time), Notes (rich_text), Stage (select), IPA Affiliation (rich_text)
  - (container has multiple data sources — additional id: `062feecb-7cea-4522-9283-64ba07f0c109`)

→ **Best guess:** "Meeting Notes" — confidence 1.00

## Unrelated Data Sources

Not a strong match for any canonical role (max score across roles < 0.30):

- "Insight Capture" — `797dbacc-9c4d-4356-83e3-5cea3605dde6`

## Next Steps

- Carry "Best guess" picks into `config/sources.yaml`, or wait for the future `/setup` skill to walk you through role mapping interactively.
- For any role with no high-confidence match: check sharing permissions, plan to create from template during `/setup`, or skip the dependent feature.