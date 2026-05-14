# ATLAS Phase 0.5: Extensible Pattern & Conversion Framework
> Framework genérico para extraer patrones de sitios rankeados, no plantillas rígidas. Implementación mínima, validable, extensible.

---

## Executive Summary

**Principios (Ajustados):**
1. ✅ Framework extensible (no solo mental health; aplica a cualquier vertical)
2. ✅ Patrones + conversión extraídos de benchmarks, no templates rígidos
3. ✅ Gates context-aware: dependen de vertical + stage del proyecto
4. ✅ "Missing assets" ≠ "bad design" (no bloquear por lo que no existe aún)
5. ✅ Implementación mínima viable → extensible

**Output:** Registry escalable que crece con cada vertical nuevo analizado.

---

## Part 1: Framework Architecture (Extensible)

### Registry Structure

```
~/.claude/design-registry/
├── framework/
│   ├── pattern-extraction-schema.json    ← Qué extraer de ANY sitio
│   ├── vertical-config-schema.json       ← Cómo configurar una vertical
│   └── stage-gates-schema.json           ← Gates según vertical + stage
├── verticals/
│   ├── mental-health-b2c/
│   │   ├── patterns.json                 ← Patterns extraídos
│   │   ├── config.json                   ← Config de esta vertical
│   │   └── benchmarks.md                 ← Qué sitios se analizaron
│   ├── wellness-b2b/
│   │   ├── patterns.json
│   │   ├── config.json
│   │   └── benchmarks.md
│   └── [new-vertical]/                   ← Escalable a nuevas verticales
│       ├── patterns.json
│       ├── config.json
│       └── benchmarks.md
├── presets/                              ← Inheritance rules por vertical
│   ├── mental-health-b2c/
│   │   └── inheritance.md
│   └── wellness-b2b/
│       └── inheritance.md
└── projects/
    └── {project-name}/
        ├── chosen-vertical.txt           ← "mental-health-b2c"
        ├── project-stage.txt             ← "early | mid | late"
        └── applied-patterns.json         ← Patterns activos para este proyecto
```

---

## Part 2: What Gets Extracted (Pattern Schema)

### Universal Pattern Extraction Schema

**Create `framework/pattern-extraction-schema.json`:**

```json
{
  "pattern_extraction": {
    "hero_section": {
      "emotional_appeal": "string (e.g., 'empathy', 'authority', 'curiosity')",
      "emotional_ratio": "number 0-10 (warm vs clinical/technical)",
      "cta_segmentation": "string (e.g., 'single_path', 'pre_qualify', 'two_step')",
      "barrier_removal_priority": ["barrier1", "barrier2", ...],
      "conversion_signal": "what CTA text + color combo converts"
    },
    "tone": {
      "warmth": "number 0-10",
      "authority": "number 0-10",
      "urgency": "number 0-10",
      "formality": "number 0-10",
      "data_forward": "number 0-10",
      "distribution": "description of balance (e.g., '60% warm, 30% authority, 10% humor')"
    },
    "social_proof": {
      "types_used": ["testimonials", "logos", "stats", "case_studies", "reviews"],
      "effectiveness_order": ["most_effective", "...", "least_effective"],
      "specificity_level": "generic | specific | highly_specific",
      "diversity_signals": "what diversity is shown (demographics, use cases, industries)"
    },
    "visual_hierarchy": {
      "whitespace_ratio": "number 0-100 (%)",
      "section_order": ["section1_purpose", "section2_purpose", ...],
      "density_profile": "sparse | moderate | dense",
      "color_temperature": "number 0-10 (warm vs cool)",
      "color_palette": ["primary_color", "secondary", "accent"],
      "psychology_notes": "why these colors work for this vertical"
    },
    "conversion_mechanics": {
      "cta_points": ["cta1_location", "cta2_location", ...],
      "cta_texts": ["Get matched", "Check coverage", ...],
      "friction_removal": ["technique1", "technique2", ...],
      "anti_patterns_detected": ["what_failed_if_removed"]
    },
    "stage_indicators": {
      "trust_signals_used": ["early_stage", "mid_stage", "late_stage"],
      "proof_points": ["what_converts_when"],
      "timeline": "how long does conversion funnel take"
    }
  }
}
```

---

## Part 3: Vertical Configuration (Not Template)

### Vertical Config Schema

**Create `framework/vertical-config-schema.json`:**

```json
{
  "vertical_config": {
    "vertical_id": "mental-health-b2c",
    "name": "Mental Health Therapy (B2C)",
    "description": "Online therapy, counseling, coaching platforms",
    "benchmarks_analyzed": [
      {
        "site": "betterhelp.com",
        "ranking_signal": "top for 'therapy online'",
        "patterns_extracted": ["pattern_id1", "pattern_id2", ...]
      }
    ],
    "winning_patterns": {
      "hero": {
        "emotional_ratio": 7,
        "cta_segmentation": "pre_qualify",
        "barrier_priority": ["trust", "cost", "commitment"]
      },
      "tone": {
        "warmth": 7,
        "authority": 6,
        "urgency": 0,
        "notes": "empathy + credibility, zero pressure"
      },
      "social_proof": {
        "primary": "diverse_testimonials_with_outcomes",
        "secondary": "credentialing_stats",
        "avoid": "generic_reviews"
      },
      "visual": {
        "density": 3,
        "whitespace": 45,
        "colors": ["teal", "blue", "green"],
        "avoid_colors": ["pure_medical_white", "aggressive_red"]
      }
    },
    "stage_gates": {
      "early_stage": {
        "strict": false,
        "checks": [
          {
            "id": "tone_warmth_minimum",
            "rule": "warmth >= 5",
            "severity": "MEDIUM",
            "why": "early, might not have assets yet"
          }
        ]
      },
      "mid_stage": {
        "strict": true,
        "checks": [
          {
            "id": "testimonials_with_specificity",
            "rule": "at_least_3_testimonials_with_outcomes",
            "severity": "HIGH",
            "why": "mid-stage, should have early customer feedback"
          }
        ]
      },
      "late_stage": {
        "strict": true,
        "checks": [
          {
            "id": "full_social_proof",
            "rule": "testimonials + stats + credentialing",
            "severity": "HIGH",
            "why": "ready for launch, needs complete trust stack"
          }
        ]
      }
    },
    "missing_asset_handling": {
      "logos": "mark MISSING if <5, don't FAIL design",
      "metrics": "mark MISSING if not quantified, don't FAIL if story exists",
      "testimonials": "mark MISSING if <3, don't FAIL if process has been launched",
      "credentialing": "HIGH severity if missing (core trust), not MISSING"
    }
  }
}
```

---

## Part 4: Stage-Aware Gates

### Gate Schema

**Create `framework/stage-gates-schema.json`:**

```json
{
  "stage_gates": {
    "early_stage": {
      "project_definition": "MVP or concept, may not have all assets",
      "philosophy": "permissive (establish patterns, don't block execution)",
      "gates": [
        {
          "id": "tone_consistency",
          "rule": "emotional_ratio matches vertical config ±1",
          "severity": "MEDIUM",
          "message": "Tone is drifting from typical for this vertical",
          "action": "WARN, suggest adjustment",
          "blocking": false
        },
        {
          "id": "cta_clarity",
          "rule": "CTA text is action-oriented, not vague",
          "severity": "MEDIUM",
          "message": "CTA like 'Learn more' is too vague",
          "action": "SUGGEST: 'Get matched' or 'Check coverage'",
          "blocking": false
        }
      ]
    },
    "mid_stage": {
      "project_definition": "Beta or soft launch, some assets exist",
      "philosophy": "balanced (enforce patterns, but mark MISSING vs FAIL)",
      "gates": [
        {
          "id": "social_proof_presence",
          "rule": "has testimonials OR stats OR case study",
          "severity": "MEDIUM",
          "message": "MISSING: social proof assets",
          "action": "MISSING (not FAIL) - suggest what to collect next",
          "blocking": false
        },
        {
          "id": "trust_signal_primary",
          "rule": "primary trust signal for vertical is present",
          "severity": "HIGH",
          "example": "for B2C therapy: therapist credentialing OR insurance",
          "message": "MISSING: credentialing or coverage info",
          "action": "WARN, high priority to add",
          "blocking": false
        }
      ]
    },
    "late_stage": {
      "project_definition": "Production ready, full go-to-market",
      "philosophy": "strict (all patterns must be satisfied or explicitly waived)",
      "gates": [
        {
          "id": "full_trust_stack",
          "rule": "all primary trust signals present",
          "severity": "HIGH",
          "message": "FAIL: incomplete trust stack for production",
          "action": "FIX before launch",
          "blocking": true
        },
        {
          "id": "conversion_funnel_complete",
          "rule": "all CTA points wired, friction removed",
          "severity": "HIGH",
          "message": "FAIL: conversion funnel has gaps",
          "action": "FIX before launch",
          "blocking": true
        }
      ]
    }
  }
}
```

---

## Part 5: Missing Assets vs Bad Design

### Decision Matrix

**Create in evidence-collector logic:**

```
IF {pattern_element} is missing:
  - credentialing (B2C therapy) → HIGH severity WARN (core trust)
  - ROI metrics (B2B wellness) → HIGH severity WARN (procurement ask)
  - testimonials (any) + stage=early → MEDIUM severity MISSING (collect later)
  - testimonials (any) + stage=late → HIGH severity FAIL (should have)
  - logos (B2B) + stage=early → MISSING (not FAIL)
  - logos (B2B) + stage=late → HIGH severity WARN (add for credibility)
  
IF {pattern_element} is present but poor quality:
  - generic testimonial (no name/photo) → MEDIUM severity IMPROVE
  - vague CTA text ("Learn more") → MEDIUM severity IMPROVE
  - dense text (>60 chars/line) → HIGH severity FAIL (affects accessibility)
  - all caps headlines → WARN (aggressive tone might not fit)

MARK AS "MISSING_ASSET":
  - Something that should exist by stage but doesn't yet
  - Not a design flaw, a content gap
  - Actionable: "add 3 customer testimonials next"

MARK AS "DESIGN_ISSUE":
  - Pattern violates what works for this vertical
  - Something present but wrong
  - Actionable: "change CTA text from 'Learn more' to 'Get matched'"
```

---

## Part 6: Minimal Implementation (Week 1)

### What Gets Built (Not Everything)

**Phase 0.5 Week 1: Core Framework Only**

```
WEEK 1 DELIVERABLES:

1. Framework directory structure
   └─ ~3 hours

2. pattern-extraction-schema.json
   └─ Define what to extract from ANY vertical
   └─ Not vertical-specific, generic schema
   └─ ~2 hours

3. vertical-config-schema.json
   └─ How to configure a NEW vertical
   └─ Template + mental-health-b2c example
   └─ ~2 hours

4. stage-gates-schema.json
   └─ Gates that adjust by vertical + stage
   └─ WARN vs MISSING vs FAIL logic
   └─ ~2 hours

5. One complete vertical implementation
   ├─ mental-health-b2c/config.json (from benchmark research)
   ├─ mental-health-b2c/patterns.json (extracted patterns)
   ├─ mental-health-b2c/benchmarks.md (which sites, what learned)
   └─ ~4 hours

6. evidence-collector.md (updated)
   ├─ Wire gates for mental-health-b2c
   ├─ Early/mid/late stage logic
   ├─ MISSING vs FAIL decision matrix
   └─ ~3 hours

7. Backup + validation
   └─ ~1 hour

TOTAL: ~17 hours = 2-3 days
```

### What Does NOT Get Built (Phase 0.5.2+)

- ❌ wellness-b2b vertical (save for Phase 0.5.2)
- ❌ presets/inheritance rules (save for Phase 0.5.2)
- ❌ 21st.dev filters (save for Phase 0.5.3)
- ❌ ui-designer wiring (save for Phase 0.5.4)
- ❌ auto-tune, autoskill (save for Phase B)

**This week: prove framework works with ONE vertical.**

---

## Part 7: Validation Checklist (Week 1)

✅ **Framework Structure:**
- [ ] Directory tree exists as specified
- [ ] Schema files are valid JSON
- [ ] mental-health-b2c/ config readable

✅ **mental-health-b2c Vertical:**
- [ ] patterns.json populated from benchmark research
- [ ] config.json has stage_gates (early/mid/late)
- [ ] benchmarks.md documents sources (Betterhelp, Talkspace, etc.)

✅ **Evidence-Collector Wired:**
- [ ] WARN checks fire for tone violations
- [ ] MISSING checks don't FAIL, just flag
- [ ] FAIL checks only trigger for core trust signals late-stage

✅ **Test on Sample:**
- [ ] Apply to 1 sample mental-health project
- [ ] Verify early_stage: MISSING warnings, no FAILS
- [ ] Verify late_stage: FAIL if trust incomplete
- [ ] Confirm blocking logic works correctly

---

## Part 8: Extensibility (For Future)

**Once framework is proven (Week 2+):**

```
Add wellness-b2b vertical:
  1. Analyze Spring Health, Lyra Health, Maven Clinic
  2. Extract patterns → wellness-b2b/patterns.json
  3. Create wellness-b2b/config.json
  4. Update evidence-collector with B2B gates
  5. Test on sample B2B project

Add other verticals as needed:
  - SaaS (e.g., Stripe, Vercel landing pages)
  - E-commerce (e.g., Shopify stores)
  - Creator economy (e.g., Patreon)
  - etc.

Framework is reusable; just add new vertical/ + config.
```

---

## Part 9: Files to Create (Week 1)

| File | Content | Time | Validation |
|------|---------|------|-----------|
| `framework/pattern-extraction-schema.json` | Generic schema for extracting patterns | 2h | Valid JSON, complete |
| `framework/vertical-config-schema.json` | How to define a vertical | 2h | Template + example |
| `framework/stage-gates-schema.json` | Gates logic (WARN/MISSING/FAIL) | 2h | All 3 stages defined |
| `verticals/mental-health-b2c/patterns.json` | Extracted patterns from benchmark | 4h | All pattern fields populated |
| `verticals/mental-health-b2c/config.json` | Vertical configuration | 2h | stage_gates, missing_asset_handling |
| `verticals/mental-health-b2c/benchmarks.md` | Source documentation | 1h | Sites analyzed, patterns found |
| `evidence-collector.md` (updated) | Wire gates for Phase 4 checks | 3h | Tests pass/fail correctly |
| Backup + validation | Pre-execution backup, post-execution test | 1h | All files readable, gates work |

---

## Part 10: Roadmap (Adjusted)

```
WEEK 1:     Phase 0.5.1 (Framework + mental-health-b2c)
            └─ Prove framework extensible with 1 vertical

WEEK 2:     Phase 0.5.2 (wellness-b2b + other verticals)
            └─ Add B2B vertical, prove multi-vertical support

WEEKS 3-4:  Phase A (Design Token Registry, Learning Index, Vercel alignment)
            └─ Parallel: Phase 0.5.3 (presets + 21st.dev filters)

WEEKS 5-6:  Phase B Start (auto-tune, autoskill, failure analysis)
            └─ Only AFTER Phase 0.5 proven

WEEKS 7-9:  Phase B Finish + Phase C (catalog)
```

---

## Part 11: Success Criteria (Week 1)

✅ **Framework Proven:**
- [ ] Schemas are reusable (not tailored to mental-health-b2c)
- [ ] New vertical could be added without changing framework
- [ ] Documentation is clear enough for someone else to extend

✅ **mental-health-b2c Working:**
- [ ] Evidence-collector applies correct gates
- [ ] Early-stage projects warn but don't FAIL
- [ ] Late-stage projects FAIL on missing core trust
- [ ] MISSING_ASSET vs DESIGN_ISSUE distinction works

✅ **Ready for Expansion:**
- [ ] Framework directory structure supports 10+ verticals
- [ ] Adding wellness-b2b requires only new vertical/ + config.json
- [ ] No changes to framework schemas needed

---

## NEXT: Execution

Ready to proceed:
1. Create backup of ~/.claude/
2. Build framework files (Week 1)
3. Test on sample project
4. Validate gates work correctly
5. Proceed to Phase 0.5.2 (wellness-b2b)

**No auto-tune, no autoskill until Phase 0.5 is proven.**
