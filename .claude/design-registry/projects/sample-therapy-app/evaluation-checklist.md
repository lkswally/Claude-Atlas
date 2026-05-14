# TherapyMatch Sample Project — Evaluation Checklist

**Project**: sample-therapy-app  
**Vertical**: mental-health-b2c  
**Stage**: mid_stage  
**Date**: 2026-05-14  

---

## Project Status Snapshot

This sample project represents a **beta-stage mental health platform** with early customers but incomplete assets. Used to validate framework gates work correctly.

### Assets Present ✅

| Asset | Status | Notes |
|-------|--------|-------|
| **Hero Section** | ✅ Present | Emotional ratio ~6 (slightly clinical) |
| **CTA Segmentation** | ✅ Present | Pre-qualify with "Individual" / "Couples" paths |
| **Therapist Profiles** | ✅ Present | Show name, photo, some credentials |
| **First Customer Testimonials** | ⚠️ Partial | 1 real testimonial (Sarah M., anxiety), no photo, outcome generic |
| **Insurance Information** | ✅ Present | "We accept most plans", but no $0 copay clarity |
| **Flexible Scheduling Language** | ✅ Present | "Message at your pace" mentioned |
| **Privacy/Safety Copy** | ✅ Present | "HIPAA compliant, secure messaging" |
| **Layout Whitespace** | ⚠️ Partial | ~38% whitespace (target 45%) |
| **Color Palette** | ✅ Present | Blue + green, no red/orange |

### Assets Missing ❌

| Asset | Expected | Gap |
|-------|----------|-----|
| **Therapist Credentialing Stats** | List licenses, experience years, # of therapists | NOT present |
| **Diverse Testimonials** | 3-5 testimonials with photos, names, specific outcomes | Only 1, no photo |
| **Outcome Metrics** | "95% of patients found a match in 48 hours" etc. | NOT present |
| **Credibility Badges** | Partner logos, accreditations, ratings | NOT present |
| **Full Conversion Funnel Wiring** | CTA → Questionnaire → Matching → Booking | Partially wired |

---

## Framework Gate Validation

### Early Stage Gates (permissive)
Should all **PASS** (non-blocking warnings only):

| Check | Rule | Status | Severity | Blocking |
|-------|------|--------|----------|----------|
| `tone_warmth_baseline` | emotional_ratio >= 5 | ✅ PASS (6) | MEDIUM | No |
| `cta_clarity` | CTA is action-oriented | ✅ PASS ("Get matched") | MEDIUM | No |
| `hero_permission_language` | Uses permission language | ⚠️ WARN (minimal) | LOW | No |

**Early Stage Outcome**: PASS (framework should not block progression)

---

### Mid Stage Gates (balanced)
Should **WARN** on high-severity missing assets but **NOT FAIL**:

| Check ID | Rule | Current State | Expected | Status | Severity | Blocking | Message |
|----------|------|---------------|----------|--------|----------|----------|---------|
| `tone_warmth_mid` | emotional_ratio >= 6 | 6 | ≥6 | ✅ PASS | MEDIUM | No | — |
| `credentialing_presence` | therapist credentials mentioned | Partial (names only) | licenses, experience | ⚠️ WARN | HIGH | No | WARN - credentialing is CORE trust signal. Add therapist qualifications prominently. |
| `testimonials_presence` | ≥1 real testimonial with name, photo, outcome | 1 (no photo, generic outcome) | ≥1 with specifics | ⚠️ WARN | MEDIUM | No | MISSING_ASSET - You need real customer stories. Current: 1 testimonial lacking photo. Actionable: Add profile photo, specify "helped manage anxiety during work transitions". |
| `zero_urgency_tactics` | No urgency/scarcity language | ✅ Clean | Zero | ✅ PASS | HIGH | No | — |
| `whitespace_density` | whitespace_ratio >= 35% | 38% | ≥35% | ✅ PASS | MEDIUM | No | — |

**Mid Stage Outcome**: WARN (assets missing, but design patterns correct + non-blocking)

---

### Late Stage Gates (strict)
Would **FAIL** if evaluated at this stage (because assets are incomplete):

| Check ID | Rule | Current | Expected | Status | Severity | Blocking |
|----------|------|---------|----------|--------|----------|----------|
| `tone_warmth_late` | emotional_ratio >= 7 | 6 | ≥7 | ❌ FAIL | HIGH | YES |
| `credentialing_full` | licenses, specialties, experience clearly stated | Partial | Full display required | ❌ FAIL | HIGH | YES |
| `testimonials_diverse` | 3-5 diverse testimonials | 1 | 3-5 required | ❌ FAIL | HIGH | YES |
| `zero_urgency_final` | zero pressure tactics | ✅ Pass | Zero | ✅ PASS | HIGH | YES |
| `conversion_funnel` | hero CTA → questionnaire → matching → booking | 70% wired | 100% | ❌ FAIL | HIGH | YES |
| `flexibility_language` | "cancel anytime", "message at pace" | ✅ Present | Present | ✅ PASS | MEDIUM | No |

**Late Stage Outcome**: FAIL (not production-ready, needs credentialing + testimonials + warmth increase)

---

## Framework Validation Results

### ✅ What Works

1. **Stage-aware gates distinguish correctly**
   - Early stage: permissive (allows WIP)
   - Mid stage: balanced (warns on gaps, doesn't block)
   - Late stage: strict (blocks production without critical assets)

2. **Missing assets vs design issues are clear**
   - Missing: "Collect 3 diverse testimonials with photos" (actionable)
   - Design: "Emotional ratio too clinical" (actionable)
   - Framework correctly labels each

3. **Severity labels drive priority**
   - HIGH missing assets (credentialing, testimonials) surface early
   - MEDIUM improvements (whitespace) are suggestions, not blockers
   - LOW optimizations (permission language) are suggestions

4. **Vertical-specific patterns apply**
   - Urgency = 0 is enforced (mental health requires zero pressure)
   - Credentialing is core trust signal (matched Betterhelp/Talkspace patterns)
   - Testimonials with photos/names/outcomes (matched all 3 benchmarks)

### ⚠️ Refinements Needed

1. **Clear actionable next steps**: When a gate WARNs, output should say exactly what to do
   - Current: "Add therapist qualifications prominently"
   - Better: "Add to therapist cards: License (e.g., LMFT), Specialty (e.g., Anxiety), Years (e.g., 7)"

2. **Asset collection guidance**: Framework should suggest where to collect missing assets
   - Example: "Testimonials from where: Exit surveys? Email? Interviews?"

3. **Evidence standards**: Framework should be specific about "diverse" testimonials
   - Example: "Diverse = ages 20-65+, genders M/F/NB, use cases Individual/Couples/Parent"

---

## Conclusion

**Sample project validation**: ✅ **SUCCESSFUL**

The framework correctly:
- ✅ Applies stage-appropriate strictness
- ✅ Distinguishes missing assets from design issues
- ✅ Prioritizes by severity (HIGH credentialing > MEDIUM testimonials > LOW language)
- ✅ Provides actionable guidance per vertical pattern
- ✅ Allows mid-stage projects to proceed while documenting gaps
- ✅ Prevents late-stage launch without critical trust signals

**Next steps for Phase 0.5 Week 2**: Framework is ready. Can proceed to wellness-b2b vertical configuration.
