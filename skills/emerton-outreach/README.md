# emerton-outreach (Claude Skill)

A Claude Skill that drafts BD outreach (a shared email + one 1-to-1 LinkedIn message per
contact) from an Excel file, in Emerton's formal style. It runs **inside Claude** — no
API key, no server.

## Contents

```
emerton-outreach/
├── SKILL.md                      # what Claude reads first (when-to-use + workflow)
├── references/
│   ├── drafting_rules.md         # the binding spec (tone, perspective, no fabrication…)
│   ├── input_known_clients.md    # CRM deal export schema (re-engagement)
│   └── input_new_prospects.md    # cold-leads schema
└── scripts/
    └── parse_deals.py            # optional: Excel -> clean JSON (skips junk, dedups)
```

## Install (per person, for now)

1. Zip the folder so the folder is the archive root:
   ```bash
   cd skills && zip -r emerton-outreach.skill emerton-outreach
   ```
2. In Claude (desktop / Cowork): **Customize → Skills → "+"**, then upload
   `emerton-outreach.skill`. Uploaded skills are private to your account.

(Docs: https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)

## Use

In a Claude/Cowork chat, attach a contacts Excel (a `Deal_Reminders`-style export for
known clients, or a new-prospects list) and say *"Draft outreach from this file."*
Claude will ask for the sender name + default language, then produce a review document
(email + LinkedIn per contact, with confidence/flags). Always review before sending.

## Editing

Edit the Markdown files directly and commit. `SKILL.md` stays short; the detailed rules
live in `references/`. Re-zip and re-upload to pick up changes.

## Later: share with the team

Once it's working well, this can be promoted to a **plugin/marketplace** so the team
installs it straight from this repo and gets updates automatically. Not set up yet —
keeping it a plain folder for now.
