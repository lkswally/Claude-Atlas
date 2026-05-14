# ATLAS Phase 0.5: Visual & Strategic Benchmark → Design System Codification
> Integración de patrones de mercado reales en ATLAS para producir resultados sólidos con prompts cortos.

---

## Executive Summary

**Problem:** ATLAS mejora abstract (mood vectors, skills), pero sin alineación con referentes que **ya funcionan en producción** y convierten.

**Solution:** Fase 0.5 que:
1. Extrae patrones de sitios mejor rankeados (B2C + B2B mental health)
2. Codifica esos patrones como reglas concretas en ATLAS
3. Reordena roadmap: primero benchmark enforcement, después auto-tune

**Outcome:** ATLAS produce resultados sólidos con prompts cortos porque está "preentrenado" en patrones que convierten.

---

## Part 1: Benchmark Analysis (Market Research)

### B2C Mental Health (Therapy/Counseling)

**Top Performers Analyzed:** Betterhelp, Talkspace, Ginger→Headspace

#### Common Winning Patterns

| Element | Betterhelp | Talkspace | Ginger/Headspace | **Pattern** |
|---------|-----------|-----------|-------------------|-----------|
| **Hero Headline Tone** | Emotional permission ("You deserve to be happy") | Relatable accessibility ("Space to figure things out") | Casual + clinical blend | **Empathy-first + clinical legitimacy** |
| **Hero CTA Strategy** | 3 pre-segmentation (Individual/Couples/Teen) | Single "Find a therapist" | Direct matching | **Reduce friction: segment early** |
| **Primary Trust Signal** | Therapist credentialing ("31,922 qualified") | Insurance coverage ($0 copay emphasis) | Convenience + credentials | **Remove barrier first, then trust** |
| **Social Proof Type** | Statistics (scale, quantity) | Testimonials with photos/names | Outcome data + research | **Mix: scale + lived experience** |
| **CTA Language** | "Get matched to a therapist" | "Check your coverage" then "Find a therapist" | Two-step (verify → match) | **Action-oriented, reduce uncertainty** |
| **Tone Distribution** | 70% clinical / 30% warm | 60% warm / 40% clinical | 50/50 blend | **Shift left on warmth (vs. traditional healthcare)** |
| **Visual Density** | Low (generous whitespace) | Moderate (testimonial carousel) | Low + scannable | **Whitespace signals calm** |
| **Color Palette** | Blue/white (trust/calm) | Teal/green + warm skin tones | Muted green/white | **Cool colors (blue/teal/green), avoid medical white-on-white** |
| **No Urgency Tactics** | "Cancel anytime" | "No waiting room" | Flexibility language | **Anti-scarcity; ethical approach** |
| **Conversion Barrier** | Low friction (questionnaire next) | Insurance check first | Low friction | **Remove commitment anxiety early** |

#### What FAILS if You Remove It

- ❌ **No therapist credentialing** → trust collapse (core ask is "trust this person with my mental health")
- ❌ **Dense text, small whitespace** → abandonment (anxious users flee)
- ❌ **Urgency tactics** → backlash (mental health seekers have high fraud awareness)
- ❌ **Generic testimonials** → credibility loss (must show diverse, specific outcomes)
- ❌ **Single CTA path** → higher friction (different users have different blockers)
- ❌ **Clinical-only tone** → alienation (seeks warmth + expertise, not just authority)

---

### B2B Mental Health / Corporate Wellness

**Top Performers Analyzed:** Spring Health, Lyra Health, Maven Clinic

#### Common Winning Patterns

| Element | Spring Health | Lyra Health | Maven Clinic | **Pattern** |
|---------|---------------|-------------|--------------|-----------|
| **Hero Dual Messaging** | Emotional + business value | Emotional + enterprise scale | Clinical specificity + ROI | **Emotional hook + business justification** |
| **Navigation Structure** | Segmented by buyer (Employer/Plan/Provider) | 6 personas with separate pathways | Vertical-specific (women's health) | **Multi-persona segmentation** |
| **Primary Trust Signal** | "Guaranteed ROI" + compliance badges | Client logos + "9/10 get better" | Peer-reviewed studies + Milliman validation | **Outcomes > features** |
| **Social Proof** | Fortune 500 logos (Highmark, Target, Microsoft) | Brand logos + specific case studies | 2,000+ employers + outcome percentages | **Both scale + specificity** |
| **CTA Hierarchy** | "Request demo" (primary), "Get started" (secondary) | "Request demo" + "Request quote" | "Book demo" + "Check eligibility" | **Demo-first for decision makers** |
| **Tone** | Professional authority + outcomes | Clinical authority + accessibility | Clinical rigor + domain expertise | **Authority + approachability** |
| **ROI Messaging** | "$4,800 annual savings per employee" | "2x faster recoveries vs traditional" | "Up to 27% lower NICU admissions" | **Quantified business impact** |
| **Compliance Signaling** | Validation Institute badge visible | HIPAA notice + security/privacy links | LegitScript seal + peer review citations | **Regulatory comfort signals** |
| **Visual Density** | Moderate (data viz, comparison tables) | Moderate (video testimonials) | Low (generous margins, card layout) | **Enterprise scanning behavior: card-based** |
| **Color Palette** | Blue/white (trust) | Blue/teal accents (healthcare standard) | True green/white (clinical + modern) | **Cool tones (blue/green); avoid warm** |
| **Verticalization vs Breadth** | Broad behavioral health | Comprehensive (therapy + coaching + psychiatry) | Vertical-specific (women's health specialization) | **Breadth + depth combo** |

#### What FAILS if You Remove It

- ❌ **No ROI numbers** → procurement fails ("why should we pay?")
- ❌ **No compliance signals** → legal/HR blocks approval (HIPAA concerns)
- ❌ **Only feature lists** → low engagement (decision makers care about outcomes, not features)
- ❌ **Single CTA** → conversion loss (different buyers have different entry points)
- ❌ **No client logo proof** → credibility gap (enterprise wants to see peers trust it)
- ❌ **Generic tone** → brand noise (must position authority for clinical credibility)

---

## Part 2: Translation to ATLAS Rules

### Design Registry Schema (Codified from Benchmark)

**Create `~/.claude/design-registry/{project}/benchmark-rules.json`:**

```json
{
  "vertical": "b2c-mental-health | b2b-wellness",
  "winning_patterns": {
    "hero": {
      "headline_tone": "empathy_first | authority_first",
      "emotional_ratio": "70% warm / 30% clinical | 50/50 | 30% warm / 70% clinical",
      "cta_segmentation": "pre-qualify | single_path | two_step",
      "barrier_removal_priority": ["trust_signal", "cost_anxiety", "commitment_anxiety"]
    },
    "tone_distribution": {
      "b2c": "60-70% warm, 30-40% clinical, 0% urgency",
      "b2b": "60% authority, 30% outcomes, 10% warmth"
    },
    "social_proof": {
      "b2c": ["statistics", "diverse_testimonials", "outcome_data"],
      "b2b": ["client_logos", "quantified_impact", "peer_review"]
    },
    "visual_hierarchy": {
      "b2c": {
        "whitespace_ratio": "40-50%",
        "sections_order": ["permission", "trust", "matching", "social_proof", "faq"],
        "no_urgency_tactics": true
      },
      "b2b": {
        "whitespace_ratio": "30-40%",
        "sections_order": ["value_prop", "trust", "outcomes", "logos", "demo_cta"],
        "data_visualization": true,
        "multi_cta_points": [3, 5]
      }
    },
    "color_palette": {
      "b2c": ["blue", "teal", "green"],
      "b2b": ["blue", "teal", "green"],
      "avoid": ["pure_medical_white", "warm_oranges", "aggressive_reds"],
      "psychology": "cool_tones_signal_calm_and_trust"
    },
    "typography": {
      "hierarchy": "weighted_sans_serif",
      "density": "scannable_not_dense",
      "readability": "anxious_users_scan_not_read"
    },
    "cta_design": {
      "b2c": {
        "primary_text": "action_oriented | barrier_removing",
        "anti_patterns": ["countdown_timers", "scarcity_language", "limited_spots"],
        "trust_language": ["cancel_anytime", "no_waiting", "flexible"]
      },
      "b2b": {
        "primary_text": "demo | contact_sales | roi_calculator",
        "multi_cta": ["primary", "secondary", "resource_download"],
        "trust_language": ["guaranteed_roi", "compliance_badge", "peer_review"]
      }
    },
    "failing_elements": {
      "b2c": ["missing_credentialing", "dense_text", "urgency_tactics", "generic_testimonials"],
      "b2b": ["no_roi_numbers", "no_compliance_signals", "single_cta", "feature_focused"]
    }
  }
}
```

### Mood Vector Calibration from Benchmark

**Add to `~/.claude/design-registry/{project}/tokens.json`:**

```json
{
  "mood_vector_calibration": {
    "b2c_mental_health": {
      "warmth": 7,           // 7/10: empathy-driven but not overly casual
      "authority": 6,         // 6/10: clinical legitimate but not sterile
      "visual_density": 3,    // 3/10: low (lots of whitespace)
      "urgency": 0,           // 0/10: zero pressure tactics
      "data_forward": 4,      // 4/10: statistics exist but human stories primary
      "modern": 6,            // 6/10: clean, contemporary, not dated
      "color_temperature": 5  // 5/10: cool (blue/teal/green)
    },
    "b2b_wellness": {
      "warmth": 4,            // 4/10: professional, less warmth
      "authority": 8,         // 8/10: high credibility, outcomes-focused
      "visual_density": 6,    // 6/10: moderate (data cards, comparison tables)
      "urgency": 3,           // 3/10: some demo CTAs, but not aggressive
      "data_forward": 8,      // 8/10: ROI, metrics, quantified outcomes primary
      "modern": 7,            // 7/10: clean enterprise design
      "color_temperature": 5  // 5/10: cool (blue/green)
    }
  }
}
```

### Preset Inheritance from Benchmark Patterns

**Create `~/.claude/design-registry/presets/b2c-therapy/inheritance.md`:**

```markdown
# B2C Mental Health Therapy Preset (Betterhelp/Talkspace Pattern)

## Inherited Visual Rules

### Typography
- Header: Bold sans-serif, weight 700-800, size 32-48px
- Body: Sans-serif weight 400, size 16-18px, line-height 1.6 (scannable)
- CTA: Sans-serif weight 600, size 16px, upper case

### Spacing
- Section vertical gap: 80-120px (generous whitespace)
- Text block margin: 60px (breathing room)
- Card padding: 40px (not cramped)
- Whitespace ratio: 40-50% of viewport

### Color
- Primary: Teal (#16a085) or Blue (#0066cc)
- Background: White (#ffffff)
- Accent: Warm skin tones (testimonials only)
- Text: Dark gray (#333333)
- Anti-pattern: Pure medical white-on-white

### Motion & Interaction
- Animations: Subtle, not flashy (anxious users avoid overstimulation)
- Transitions: 300ms ease-in-out
- Hover states: Color shift, not aggressive enlargement

### Component Rules
- Buttons: Rounded (8-12px), 48px min height (accessibility)
- Forms: Multi-step questionnaire (reduce perceived friction)
- Testimonials: Photos + names + specific outcomes (trust)
- CTAs: 2-3 variants per section (reduce cognitive load)

### Anti-Patterns
- ❌ Countdown timers
- ❌ Scarcity language ("only 5 spots left")
- ❌ Aggressive brightness contrasts
- ❌ Dense paragraph blocks (>60 chars per line)
- ❌ Single CTA path (users have different blockers)

## Mood Vector Alignment
All design decisions must score ≥6/10 on warmth + ≥6/10 on authority.
If warmth drops below 5, feels clinical/cold → FAIL evidence-collector gate.
```

**Create `~/.claude/design-registry/presets/b2b-wellness/inheritance.md`:**

```markdown
# B2B Wellness Enterprise Preset (Spring Health/Lyra Pattern)

## Inherited Visual Rules

### Typography
- Header: Bold sans-serif, weight 700, size 36-48px
- Body: Sans-serif weight 400, size 15-16px, line-height 1.5 (scannable for execs)
- CTA: Sans-serif weight 600, size 15px, sentence case (professional, not loud)

### Spacing
- Section vertical gap: 60-80px (moderate, not sparse)
- Card padding: 32px (compact but breathable)
- Whitespace ratio: 30-40% of viewport (enterprise scanning behavior)

### Color
- Primary: Blue (#0066cc) or Teal (#16a085)
- Background: White (#ffffff)
- Accent: Green (#28a745) for outcomes, verified badge colors
- Compliance badges: Muted grays + official colors
- Text: Dark gray (#333333), Medium gray (#666666) for secondary

### Data Visualization
- Charts: Clean, minimal (no 3D, no rainbow gradients)
- Comparison tables: Checkmarks/X marks with green/neutral/red
- Icons: Professional set (not playful)

### Component Rules
- Buttons: Slightly rounded (4-6px), 44px min height, primary + secondary variants
- Cards: Data visualization + metrics + outcome quotes
- Forms: ROI calculator, demo request with 3-4 fields max
- Client logos: 20+ displayed, B&W treatment for cohesion

### Anti-Patterns
- ❌ Startup playfulness (no emoji, no casual tone)
- ❌ Feature-only talk (must lead with outcomes)
- ❌ Single CTA (demo + download + contact)
- ❌ Vague metrics ("better," "improved")
- ❌ Compliance evasiveness (must display badges, HIPAA, security)

## Mood Vector Alignment
All design decisions must score ≥7/10 on authority + ≥6/10 on data_forward.
If authority drops below 6, fails procurement trust → FAIL evidence-collector gate.
```

---

## Part 3: Anti-Pattern Enforcement (Rules as Executable Gates)

### Evidence-Collector Severity Gates (New Rules)

**Add to `~/.claude/evidence-collector.md` Phase 4 checks:**

```
## B2C Mental Health (Therapy) Specific Checks

### HIGH Severity (Must Pass)
- [ ] Testimonials include photos + names + specific outcomes (not generic)
- [ ] Whitespace ratio ≥40% (proves calm/accessibility)
- [ ] CTA text is action-oriented ("Get matched," "Find therapist") not vague ("Learn more")
- [ ] Zero urgency tactics (no countdowns, scarcity, "limited spots")
- [ ] Tone score: warmth ≥6/10, authority ≥5/10 (mood_vector inference)

### MEDIUM Severity (Should Pass)
- [ ] Multi-CTA paths (≥2 entry points for different user barriers)
- [ ] Section order matches pattern (permission → trust → matching → proof)
- [ ] Color palette uses cool tones (blue/teal/green)

### LOW Severity (Nice-to-Have)
- [ ] Section spacing ≥80px (generous whitespace)
- [ ] Testimonial carousel (dynamic engagement)

---

## B2B Wellness (Corporate) Specific Checks

### HIGH Severity (Must Pass)
- [ ] ROI messaging with quantified numbers (e.g., "$4,800 annual savings per employee")
- [ ] Compliance badges visible (HIPAA, LegitScript, Validation Institute, or peer-review)
- [ ] Client logos: ≥5 named customers or unnamed Fortune 500 tier
- [ ] Multi-CTA points: ≥3 different conversion paths (demo, download, contact)
- [ ] Tone score: authority ≥7/10, data_forward ≥6/10

### MEDIUM Severity (Should Pass)
- [ ] Data visualization (charts, comparison tables, outcome metrics)
- [ ] Outcome statements are specific, not feature statements
- [ ] Segmented navigation for different personas (Employer/Provider/Plan)

### LOW Severity (Nice-to-Have)
- [ ] Video testimonials from client representatives
- [ ] Industry-specific case studies
```

---

## Part 4: Component Adaptation Rules (21st.dev Context)

### Rule: Adapt Components to Benchmark Mood

**New Rule in `ui-designer.md`:**

When selecting 21st.dev components:

**B2C Mental Health:**
1. Query 21st.dev for "therapy hero" / "counseling matching" / "testimonial cards"
2. Filter by: 
   - ✅ Warm color options (teal, soft blue)
   - ✅ Generous padding/whitespace
   - ✅ Accessible form patterns (multi-step questionnaires)
   - ❌ Avoid: Aggressive CTAs, dark moods, dense layouts
3. Adapt colors to mood_vector (warmth 7, authority 6)
4. Inherit spacing from preset (80-120px section gaps)

**B2B Wellness:**
1. Query 21st.dev for "data dashboard" / "comparison table" / "enterprise hero"
2. Filter by:
   - ✅ Professional color schemes (blue/green)
   - ✅ Data visualization components
   - ✅ Multi-CTA support
   - ❌ Avoid: Playful tone, warm colors, sparse layouts
3. Adapt to mood_vector (authority 8, data_forward 8)
4. Inherit card-based density from preset (30-40% whitespace)

---

## Part 5: Reordered Roadmap (Benchmark-First)

### New Phase 0.5: Visual Benchmark → Codification (Weeks 1-2)

**Before any design improvements, codify patterns as rules.**

#### Phase 0.5.1: Design Registry from Benchmark (1 week)
- [ ] Create `~/.claude/design-registry/{project}/benchmark-rules.json`
- [ ] Populate mood_vector_calibration (B2C vs B2B templates)
- [ ] Create preset inheritance rules for both verticals
- **Owner:** ui-designer
- **Validation:** Registry queryable, mood vectors populated, presets exist

#### Phase 0.5.2: Anti-Pattern Gates (Evidence-Collector) (1 week)
- [ ] Add HIGH/MEDIUM/LOW severity checks for B2C mental health
- [ ] Add HIGH/MEDIUM/LOW severity checks for B2B wellness
- [ ] Wire gates into Phase 4 certification flow
- [ ] Test gates on 2-3 sample projects
- **Owner:** evidence-collector + reality-checker
- **Validation:** Evidence-collector blocks NEEDS_WORK on severity violations

#### Phase 0.5.3: 21st.dev Context Filters (1 week)
- [ ] Document component selection rules by vertical
- [ ] Create filtering logic in ui-designer agent
- [ ] Add adaptation rules for mood_vector alignment
- **Owner:** ui-designer
- **Validation:** Component queries return vertical-appropriate results

---

### Then Continue: Phase A (Base Stable) → Phase B (Learning) → Phase C (Catalog)

**Reordered Timeline:**

```
WEEK 1-2:   Phase 0.5 (Visual Benchmark Codification)
            ├─ Design registry from market patterns
            ├─ Anti-pattern severity gates
            └─ 21st.dev context filters

WEEK 3-4:   Phase A (Design Token Registry, Learning Index, Vercel alignment)
WEEK 2-4:   Phase C (PARALLEL: Skills library, awesome index, domain presets)
WEEK 5-6:   Phase B Start (auto-tune, autoskill, failure analysis)
WEEK 7-9:   Phase B Finish (mood scoring, preset inheritance)
WEEK 10+:   Phase D (experimental)
```

---

## Part 6: Files to Create (Phase 0.5)

| File | Content | Owner | Timeline |
|------|---------|-------|----------|
| `~/.claude/design-registry/{project}/benchmark-rules.json` | Mood vectors, tone distribution, winning patterns | ui-designer | 3 days |
| `~/.claude/design-registry/presets/b2c-therapy/inheritance.md` | Typography, spacing, color, anti-pattern rules | ui-designer | 2 days |
| `~/.claude/design-registry/presets/b2b-wellness/inheritance.md` | Same as above, enterprise variant | ui-designer | 2 days |
| `~/.claude/evidence-collector.md` (updated) | HIGH/MEDIUM/LOW severity gates for both verticals | evidence-collector | 3 days |
| `~/.claude/agents/ui-designer.md` (updated) | Component selection filters + adaptation rules | ui-designer | 2 days |

**Total Phase 0.5: ~2 weeks** (can parallelize with Phase C)

---

## Part 7: Success Metrics (Phase 0.5)

✅ **Design Registry Operational:**
- [ ] Benchmark rules queryable via Engram
- [ ] Mood vectors populated (B2C: warmth 7, authority 6 | B2B: authority 8, data_forward 8)
- [ ] Presets inherited correctly (spacing, color, typography)

✅ **Anti-Pattern Gates Working:**
- [ ] B2C projects: warmth <6 → NEEDS_WORK in evidence-collector
- [ ] B2B projects: authority <7 → NEEDS_WORK in evidence-collector
- [ ] Test on 2 sample projects; both fail & get fixed before Phase A

✅ **21st.dev Filters Active:**
- [ ] ui-designer queries return vertical-appropriate components
- [ ] Components adapt to mood_vector before handoff to frontend-developer
- [ ] Spacing/color inheritance from preset validated

---

## Part 8: First Execution Block (To Start Immediately)

**If approved: execute Phase 0.5 Week 1 (Design Registry Creation)**

```
PHASE 0.5 WEEK 1: Design Registry from Benchmark

1. Create directory structure
   mkdir -p ~/.claude/design-registry/{project}/
   mkdir -p ~/.claude/design-registry/presets/b2c-therapy
   mkdir -p ~/.claude/design-registry/presets/b2b-wellness

2. Create benchmark-rules.json with:
   - vertical: "b2c-mental-health" | "b2b-wellness"
   - hero.headline_tone: "empathy_first" | "authority_first"
   - tone_distribution: actual percentages from benchmark
   - social_proof: types that work per vertical
   - failing_elements: what kills conversions
   
3. Populate mood_vector_calibration:
   - B2C: warmth 7, authority 6, density 3, urgency 0
   - B2B: warmth 4, authority 8, density 6, urgency 3

4. Create preset inheritance files (typography, spacing, color rules)

5. Backup & validate:
   - Registry files readable + valid JSON
   - Presets inherit correctly
   - No conflicts with existing ATLAS

6. Engagement gate: ui-designer confirms rules are usable
```

**Estimate:** 5-7 days (1 week)  
**Dependencies:** None  
**Risk:** Low (additive, no code changes)

---

## Next Step

✅ **Approval:** Review benchmark findings + Phase 0.5 plan  
✅ **If approved:** Begin Phase 0.5 Week 1 (Design Registry)  
✅ **Then proceed:** Phase A → Phase B → Phase C (as previously planned)

**No code changes yet.** This is structural alignment with market reality.
