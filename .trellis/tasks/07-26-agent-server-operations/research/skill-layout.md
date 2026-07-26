# Repository Skill Layout

## Observed environment

- The current session exposes repository skills from
  `.agents/skills/<skill-name>/SKILL.md`.
- Existing Trellis skills already use that path.
- The official `skill-creator` requires a folder named after the lowercase
  hyphenated skill, a frontmatter-only `name` and `description`, and recommends
  `agents/openai.yaml`.
- The official initializer and validator are available at
  `/home/fezer/.codex/skills/.system/skill-creator/scripts/`.

## Decision

Use `.agents/skills/mediaops-server/` as the only canonical source. Initialize
it with the official helper, include `scripts` and `references`, then run
`quick_validate.py`. Do not create `skills/mediaops-server` or install a second
copy under the user-level Codex directory.

## Discovery behavior

Codex discovers the skill when a session starts in this repository. A session
that predates skill creation may need to be restarted before the new skill
appears in its available-skill catalog.
