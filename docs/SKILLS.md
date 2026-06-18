# ATLAS — Skills Reference

Skills are reusable knowledge units that Claude applies to specific task types. They're declared in `.claude/skills.registry.yaml` and consulted by agents to determine which specialized approach to use.

---

## What Are Skills?

A skill is a named set of instructions that activates when a specific context is detected.

Example:
- Task requires UI design → activate `ui-ux-pro-max` skill
- Task requires brand work → activate `branding` skill
- Task requires QA → activate `qa-strict` skill

Skills are distinct from agents:
- **Agents** are who does the work (ux-architect, evidence-collector)
- **Skills** are how they do it (with ui-ux-pro-max, with qa-strict)

---

## Current Skills (10)

### design
**Domain:** design

| Skill | Applies when | Effect |
|-------|-------------|--------|
| `ui-ux-pro-max` | ui-designer receives a design task in design_strict mode | Activates the full design enforcement cascade: references required, editorial compliance, anti-generic detection |
| `reference-driven-design` | any design task with `brand.references` present | Enforces 2–5 visual references with rationale ≥10 chars, `take[]` non-empty |
| `editorial-compliance` | ui-designer in design_strict mode | Requires asymmetric sections, typography mix, references cited, boilerplate avoided |

### branding
**Domain:** branding

| Skill | Applies when | Effect |
|-------|-------------|--------|
| `brand-identity` | brand-agent activated | Full brand creation flow: palette, typography, tone, personality, visual language |
| `nothing-design` | user requests "Nothing design" or "Nothing style" | Activates Nothing Design System tokens, components, and anti-patterns |

### qa
**Domain:** qa

| Skill | Applies when | Effect |
|-------|-------------|--------|
| `qa-strict` | evidence-collector in QA loop | Requires visual screenshots, 3 viewports, explicit PASS/FAIL, no partial evidence |
| `visual-fidelity` | reality-checker in Phase 4 | Palette comparison, typography check, mood alignment, anti-pattern detection |

### orchestration
**Domain:** orchestration

| Skill | Applies when | Effect |
|-------|-------------|--------|
| `phase-gate-enforcement` | orchestrator advancing phases | Verifies all required Engram drawers exist before advancing |
| `anti-loop-detection` | orchestrator detecting repeated delegations | Triggers `escalation_needed` after 3 identical delegations |
| `light-boot` | orchestrator resuming an existing project | Loads minimal state first (phase, task/total, stack) to save ~400–1900 tokens |

---

## How Agents Use Skills

Agents consult the skills registry via `tools/skills_registry.py`:

```python
from tools.skills_registry import find_skills

# Find skills applicable to a UI design task
skills = find_skills(domain="design", agent="ui-designer")
# Returns: [{"id": "ui-ux-pro-max", "applies_when": "...", "instructions": "..."}]
```

Usage is logged to `.claude/logs/skills-registry-usage.jsonl`:
```bash
python tools/skills_registry.py stats
python tools/skills_registry.py stats --since=7   # last 7 days
```

---

## Adding a New Skill

1. Open `.claude/skills.registry.yaml`
2. Add your skill under the appropriate domain:

```yaml
skills:
  my-domain:
    - id: my-skill-id
      name: My Skill Name
      description: What this skill does
      applies_when: "specific condition when this activates"
      agents: [agent-name-1, agent-name-2]
      instructions: |
        Detailed instructions for how to apply this skill.
        Can be multi-line.
      version: "1.0"
```

3. Test that the registry loads:
```bash
python tools/skills_registry.py list
python -c "from tools.skills_registry import validate_registry; validate_registry()"
```

4. Add a usage hint in the agent file that should use this skill.

---

## Skill Versioning

Each skill has a `version` field. When you update a skill's behavior significantly, increment the version. The skills registry logs include version information so you can track which version was applied in which session.

---

## Skill Enforcement

In `design_strict` mode, the dispatcher enforces that `design_intelligence.queried=true` in the Return Envelope — meaning the agent must have consulted the skills registry before returning. The cascade:

```
1C.1 → Check design_intelligence.queried
1L.2 → Check design_quality (HIGH findings reject)
1L.3 → Check references (2-5 entries with rationale)
1L.4 → Check editorial compliance (5 sub-fields)
```

This prevents agents from returning work without applying the relevant skills.

---

## Skill vs. Reference

| | Skill | Reference |
|---|---|---|
| Location | `skills.registry.yaml` | `~/.claude/agents/*-reference.md` |
| Purpose | Activation logic + brief instructions | Deep technical knowledge |
| Loaded by | Python registry API | Agent reads the file directly |
| Example | `ui-ux-pro-max` skill | `react-patterns-reference.md` |

Skills tell agents *when* and *how* to activate a behavior. References give agents the *knowledge* to execute it.
