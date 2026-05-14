# ATLAS Parity + Superiority Roadmap
> Plan para igualar y superar claude-vibecoding en UX/design + continuous skill improvement.

---

## Executive Summary

**Problem:** ATLAS es arquitectónicamente sólido (38 agentes, 5-fase pipeline) pero le faltan:
1. **Coherencia visual numérica** — mood vectors, fidelidad scoring
2. **Mecanismo de mejora continua** — learning index, auto-tuning de skills

**Solution:** Integrar capas de diseño + mejora continua sin quebrar el pipeline existente.

**Order:** Fase 0 (base estable) → Fase 1 (design tokens) → Fase 2 (skill learning) → Fase 3 (auto-tune) → Fase 4 (experimental)

---

## Part 1: Gap Analysis vs claude-vibecoding

### Design/UX Layer — What's Missing (5 diferencias clave)

| Gap | Vibecoding | ATLAS Today | Impact | Fix |
|-----|-----------|-------------|--------|-----|
| **Design Token Schema** | `brand.json` v2 con mood_vector [8 dims] | CSV files + lógica en agentes | Sin scoring de coherencia visual | Crear token registry con mood_vector |
| **Anti-Pattern Enforcement** | Numeric severity HIGH/MEDIUM/LOW + fallback forzado | Flags en agentes, no fuerza cambios | Proyectos mediocres avanzan a Phase 5 | Add severity gates en evidence-collector |
| **Reference Adaptation** | Adapta componentes 21st.dev al mood_vector | Context7 queries, sin adaptación sistemática | Componentes genéricos, no personalizados | Add mood-driven adaptation en ui-designer |
| **Preset Inheritance** | Spacing, radius, motion curves heredan del preset | Presets listados, sin reglas heredables | No hay coherencia visual entre projects | Implementar preset inheritance rules |
| **Visual Fidelity Scoring** | Numeric `VISUAL_FIDELITY: 7.2/10` basado en mood_vector comparison | Verificación subjetiva | Sin métrica de qué se logró vs qué se pedía | Add LLM mood inference → mood_vector comparison |

### Skill Improvement — What's Missing (5 diferencias clave)

| Gap | Vibecoding | ATLAS Today | Impact | Fix |
|-----|-----------|-------------|--------|-----|
| **Learning Index** | Auto-tags código por tech/library/pattern durante ejecución | Sin mecanismo de discovery cross-project | Mismo patrón re-escrito cada proyecto | Implementar learning index hook |
| **Behavioral Spec Tiers** | Motion intensity 0-10, fuerza re-spec si implementación diverge | Specs en texto, sin tiers numéricos | Sin match entre design intent e implementación | Add numeric intensity tiers → severity escalation |
| **Failure-Driven Learning** | Failures →analyzed → agent prompts mejorados automáticamente | DAG state solo trackea completion, no patterns | Errores no retroalimentan agentes | Add failure analysis hook → prompt tuning |
| **Mood Vector Audit** | Compara evidencia contra brand.json.mood_vector | Verificación manual de screenshots | Sin scoring automático de coherencia | Add mood inference en evidence-collector |
| **False-Positive Guard** | Reality-checker re-ejecuta 2-3 random PASS tasks | Mentioned pero no sistemático | False positives pueden pasar a producción | Hacer re-ejecución de PASS tasks sistemática |

---

## Part 2: Skill Repositories Evaluation

### Matriz de Decisión (7 Repos)

| Repo | Core Value | Learning Mechanism | Integration Cost | Conflicts | Verdict |
|------|-----------|-------------------|------------------|-----------|---------|
| **vercel-labs/skills** | Unified skill registration + routing | Declarative SKILL.md YAML manifest | **LOW** | None | ✅ **ADOPT** (ya es tu standard) |
| **kakeami/claude-auto-tune** | Scheduled improvement loop (7d default) | Web scrape → repo analysis → proposal → approve | **MEDIUM** | None | ✅ **ADOPT** (wraps ATLAS con feedback externo) |
| **alirezarezvani/claude-skills** | Library de 263+ skills pre-built | Static modular architecture | **LOW** | None | 🔄 **ADAPT** (use como template library) |
| **VoltAgent/awesome-agent-skills** | Curated 1000+ skills de comunidad | Human curation + security scoring | **LOW** | None | 🔄 **ADAPT** (descubrimiento, no integración) |
| **runkids/skillshare** | Multi-agent skill sync (Git-like versioning) | Sync engine: local → multi-target | **MEDIUM** | None | 🟡 **DEFER** (solo si multi-agent scaling) |
| **Samurai412/autoskill** | Context-aware skill adaptation | Continuous loop: scan → detect patterns → mutate | **MEDIUM** | Moderate (duplica Phase 3 scan) | ✅ **ADOPT** (killer feature si coordinado) |
| **sentient-agi/EvoSkill** | Auto-generate skills via genetic algorithm | Iterative mutation + held-out data validation | **HIGH** | Major (compite con Phase 1) | ❌ **SKIP** (powerful pero ortogonal) |

### Killer Features por Repo

1. **vercel-labs/skills** — Standard infrastructure; asegurar consistencia
2. **kakeami/claude-auto-tune** — External feedback loop para long-running systems
3. **Samurai412/autoskill** — **Context-aware adaptation** — transforma skills estáticos → adaptativos
4. **alirezarezvani/claude-skills** — Template library para Phase 1 skill assembly

---

## Part 3: Categorization

### A. Base Estable (No tocar ATLAS core)

**Objetivo:** Sentar fundación sin quebrar nada.

1. **Vercel Skills Framework** — Asegurar ATLAS usa SKILL.md v2 YAML format
2. **Design Token Registry** — Crear `~/.claude/design-registry/` con mood_vector schema
3. **Learning Index Hook** — Hook reactive que auto-tags código (sin cambiar Phase 3)

**Timeline:** 2-3 semanas  
**Risk:** Bajo (aditivo, no modificante)

### B. Mejora Continua (Feedback loops)

**Objetivo:** Agregar capas de aprendizaje sin quebrar pipeline.

1. **claude-auto-tune Integration** — Scheduled improvement loop cada 7 días
2. **Autoskill Context Adapter** — Scan + mutation en Phase 3/4 handoff
3. **Failure Analysis Hook** — Capturar failures → analizar → sugerir prompt improvements

**Timeline:** 4-6 semanas (después de Base Estable)  
**Risk:** Medio (nuevos hooks, pero aislados)

### C. Catálogo de Skills

**Objetivo:** Enriquecer skill library sin crear dependencias.

1. **Vercel skills Library** — Load `alirezarezvani/claude-skills` como reference en Phase 1
2. **Awesome Skills** — Index `VoltAgent/awesome-agent-skills` como discovery tool
3. **Domain-Specific Templates** — Crear presets por dominio (web, mobile, game, etc.)

**Timeline:** 2-3 semanas (paralelo a Base Estable)  
**Risk:** Bajo (reference only)

### D. Experimental (Futuro)

**Objetivo:** Explorar sin comprometer.

1. **Skillshare Multi-Agent** — Si ATLAS escala a multi-tenant
2. **EvoSkill Framework** — Si ATLAS adopta failure-driven evolution como core
3. **Pixel Bridge** — Ya deferred; reevaluar cuando demand signal aparezca

**Timeline:** 3+ meses  
**Risk:** Alto (orthogonal a ATLAS goals)

---

## Part 4: Orden Más Seguro Para Igualar + Superar Vibecoding

### Fase A: Base Estable (Semana 1-3)

**Goal:** Sentar fundación numérica para diseño.

#### A.1: Design Token Registry
- [ ] Crear `~/.claude/design-registry/{project}/tokens.json` schema
- [ ] Schema incluye: `mood_vector [8 dims]`, `palette_hash`, `typography`, `spacing_scale`, `motion_curves`
- [ ] Persistencia en Engram: `topic_key = "{project}/design-tokens"`
- [ ] Agentes leen via `mem_search("design-tokens", "{project}")`
- **Owner:** ui-designer  
- **Cost:** 3 días  
- **Validation:** Design registry queryable, mood_vector persiste cross-session

#### A.2: Vercel Skills Framework Alignment
- [ ] Audit de todos los `agents/**/*.md` — asegurar SKILL.md frontmatter
- [ ] Validar `name`, `description`, `models`, `tools` fields
- [ ] Update settings.json allowlist si necesario
- **Owner:** orquestador  
- **Cost:** 2 días  
- **Validation:** Claude Code CLI reconoce todos los skills sin warnings

#### A.3: Learning Index Hook
- [ ] Crear `~/.claude/hooks/learning-index-hook.js`
- [ ] Hookea Phase 3 output: parsea código → auto-tags (tech: React/Vue/Go, library: Tailwind/GSAP, pattern: compound-component/render-props)
- [ ] Persiste en `~/.claude/learning-index/{tech}/{pattern}.md`
- [ ] Engram entry: `topic_key = "learning-index/{tech}/{pattern}"`
- **Owner:** evidence-collector  
- **Cost:** 3 días  
- **Validation:** Learning index populated después de Phase 3; queries en Engram retornan matches

---

### Fase B: Mejora Continua (Semana 4-9)

**Goal:** Agregar feedback loops de aprendizaje.

#### B.1: Auto-Tune Integration
- [ ] Integrar `kakeami/claude-auto-tune` como skill separado
- [ ] Schedule 7-day loop: web-scrape → analyze repos → generate CLAUDE.md proposals
- [ ] Approval gate: user must say "Aprobada auto-tune" antes de auto-apply
- [ ] Persiste cambios aprobados en Engram: `topic_key = "atlas/auto-tune-proposals"`
- **Owner:** orquestador  
- **Cost:** 5 días  
- **Validation:** Auto-tune runs, genera proposals, waits for approval

#### B.2: Autoskill Context Adapter
- [ ] Integrar `Samurai412/autoskill` en Phase 3/4 boundary
- [ ] MODE 0: Scan codebase durante Phase 3 → detect patterns
- [ ] MODE 2: Post-Phase 4 evidence → mutation triggers → update agent prompts
- [ ] Coordinate con existing Phase 3 scanning (no duplicar)
- **Owner:** evidence-collector + reality-checker  
- **Cost:** 5 días  
- **Validation:** Autoskill detects patterns, proposes mutations, agent prompts updated

#### B.3: Failure Analysis Hook
- [ ] Crear `~/.claude/hooks/failure-analysis-hook.js`
- [ ] Captura FAIL/NEEDS_WORK outputs → análisis → suggest prompt improvements
- [ ] Persis recomendaciones en Engram: `topic_key = "failure-analysis/{agent}/{category}"`
- [ ] Evidence-collector puede consultar durante Phase 4 re-implementation
- **Owner:** reality-checker  
- **Cost:** 4 días  
- **Validation:** Failures logged → suggestions queryable en Engram

#### B.4: Mood Vector Scoring en Evidence-Collector
- [ ] LLM inference: "¿Cuál es el mood vector de este screenshot?" → return [7, 3, 8, ...]
- [ ] Compare contra `design-registry/{project}/tokens.json.mood_vector`
- [ ] Report `VISUAL_FIDELITY: avg` score
- [ ] Si score <6: flag como NEEDS_WORK en reality-checker
- **Owner:** evidence-collector  
- **Cost:** 3 días  
- **Validation:** Evidence-collector reports `VISUAL_FIDELITY: 7.2/10`; realidad-checker usa para gate

#### B.5: Preset Inheritance Rules
- [ ] Crear `~/.claude/design-registry/presets/{mood}/inheritance.md`
- [ ] Rules: si mood=bold → spacing_scale=1.5x, border_radius=lg, motion=fast
- [ ] Ui-designer consulta al crear design-system
- [ ] Anti-patterns merge: preset anti-patterns + design-intelligence anti-patterns
- **Owner:** ui-designer  
- **Cost:** 3 días  
- **Validation:** Design system hereda preset rules; no override manual

---

### Fase C: Catálogo de Skills (Paralelo a A + B, Semana 2-4)

**Goal:** Enriquecer skill library sin integración profunda.

#### C.1: Skills Reference Library
- [ ] Symlink `alirezarezvani/claude-skills` → `~/.claude/skill-reference/`
- [ ] Frontend-developer puede consultar templates durante Phase 1
- [ ] Project-manager-senior puede usar como ejemplos en task breakdown
- **Owner:** project-manager-senior  
- **Cost:** 1 día  
- **Validation:** Skills reference queryable, no errores de path

#### C.2: Awesome Skills Curation Index
- [ ] Create `~/.claude/awesome-skills-index.md` (snapshot de VoltAgent)
- [ ] Manual review: mark HIGH/MEDIUM/LOW quality per skill
- [ ] Link to original repos
- [ ] Project-manager-senior consulta durante Phase 1 si need reference
- **Owner:** project-manager-senior  
- **Cost:** 1 día (initial); 0.5 días monthly update  
- **Validation:** Index existe, curated, links válidos

#### C.3: Domain-Specific Presets
- [ ] Crear templates: web-app.md, mobile-app.md, game.md, api.md
- [ ] Cada template: preset mood, típicos agents, design system expectations, skills combo
- **Owner:** ui-designer  
- **Cost:** 2 días  
- **Validation:** Presets existentes, usables en Phase 1

---

### Fase D: Experimental (Semana 10+)

**Goal:** Explorar avanzado sin apresurarse.

#### D.1: Skillshare (Si Multi-Tenant)
- [ ] Integrar cuando ATLAS soporte múltiples usuarios/proyectos
- [ ] Evaluación post-Fase C

#### D.2: EvoSkill (Si Failure-Driven Adoption)
- [ ] Integrar solo si ATLAS adopta "failure → evolution" como estrategia core
- [ ] Requiere benchmark suite + held-out validation data
- [ ] Evaluación post-Fase B

---

## Part 5: Implementation Map

### Que Crea Ahora (Mínimo Para Igualar Vibecoding)

| Item | Ubicación | Dueño | Tiempo | Tipo |
|------|-----------|-------|--------|------|
| Design Token Registry Schema | `~/.claude/design-registry/` | ui-designer | 3d | Base |
| Learning Index Hook | `~/.claude/hooks/learning-index-hook.js` | evidence-collector | 3d | Base |
| Vercel Skills Alignment Audit | agents/**/*.md | orquestador | 2d | Base |
| claude-auto-tune Skill | `agents/auto-tune.md` + integration | orquestador | 5d | Mejora |
| Autoskill Adapter | Phase 3/4 integration | evidence-collector | 5d | Mejora |
| Failure Analysis Hook | `~/.claude/hooks/failure-analysis-hook.js` | reality-checker | 4d | Mejora |
| Mood Vector Scoring | evidence-collector logic | evidence-collector | 3d | Mejora |
| Preset Inheritance | `design-registry/presets/` | ui-designer | 3d | Mejora |
| Skills Reference Library | symlink `alirezarezvani/claude-skills` | frontend-developer | 1d | Catálogo |
| Awesome Skills Index | `~/.claude/awesome-skills-index.md` | project-manager-senior | 1d | Catálogo |
| Domain Presets | `design-registry/presets/{domain}/` | ui-designer | 2d | Catálogo |

**Total:** ~32 días hábiles (4-5 semanas si paralelo)

---

## Part 6: Comparison vs Vibecoding (Post-Implementation)

### Design/UX Parity

After Phase A + B:

| Aspect | Vibecoding | ATLAS Post-Plan | Match |
|--------|-----------|-----------------|-------|
| Design Token Schema | mood_vector [8 dims] | Design registry + mood_vector | ✅ Yes |
| Anti-Pattern Enforcement | Numeric severity + gates | Severity gates en evidence-collector | ✅ Yes |
| Reference Adaptation | Mood-driven component adaptation | autoskill context adapter | ✅ Yes |
| Preset Inheritance | Explicit spacing/motion/font rules | Preset inheritance rules | ✅ Yes |
| Visual Fidelity Scoring | Numeric VISUAL_FIDELITY: avg | mood_vector comparison scoring | ✅ Yes |

### Skill Improvement Superiority

After Phase A + B + C:

| Aspect | Vibecoding | ATLAS Post-Plan | Better |
|--------|-----------|-----------------|--------|
| Learning Index | Auto-tag código | Learning index hook | ✅ ATLAS same |
| Failure-Driven Learning | Mentioned, no explicit mechanism | Failure analysis hook | 🟢 **ATLAS Better** |
| Behavioral Spec Tiers | Motion intensity tiers | Numeric intensity tiers | ✅ ATLAS same |
| False-Positive Guards | Random re-exec of PASS tasks | Explicit re-exec policy | ✅ ATLAS same |
| Continuous Improvement | Implicit in design-intelligence | claude-auto-tune explicit loop | 🟢 **ATLAS Better** |
| Context-Aware Skills | Limited | autoskill adapter | 🟢 **ATLAS Better** |

---

## Part 7: Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Learning Index bloats Engram | Medium | Performance | Shard by tech/pattern; lazy-load |
| Autoskill mutations break agents | Medium | Critical | Test mutations on held-out data first |
| Mood vector LLM inference inaccurate | High | False positives | Cross-validate with human review; adjust thresholds |
| Auto-tune proposals conflict with Phase 0 intent | Low | Scope creep | Explicit user approval gate; version control in Engram |
| Phase 3 scanning duplicates (ATLAS + autoskill) | High | Wasted compute | Coordinate hooks; make scanning pluggable |

---

## Timeline (Recommended)

```
Week 1-2:   Phase A (Design Token Registry, Vercel alignment, Learning Index)
Week 3-4:   Phase C (parallel: Skills reference, awesome index, domain presets)
Week 5-6:   Phase B (Auto-tune, autoskill, failure analysis)
Week 7-9:   Phase B (Mood vector scoring, preset inheritance, testing)
Week 10+:   Phase D (experimental, if wanted)
```

---

## Success Criteria

✅ **Parity with vibecoding:**
- [ ] Design token registry operational + Engram queryable
- [ ] mood_vector scoring in evidence-collector (VISUAL_FIDELITY: >=6)
- [ ] Preset inheritance rules applied in ui-designer
- [ ] Learning index hook auto-tagging code

✅ **Superiority over vibecoding:**
- [ ] claude-auto-tune scheduled improvement loop running
- [ ] autoskill adaptive mutations improving agent prompts
- [ ] failure-analysis hook generating suggestions for re-implementation
- [ ] Skill reference library + awesome skills index available

✅ **No breaking changes:**
- [ ] All 5 phases still work as documented
- [ ] Rollback plan documented for each major addition
- [ ] Engram database grows but remains performant
- [ ] No modifications to existing 38 agents (only new hooks/skills)

---

## Next Steps

1. **Review & Approve** this roadmap
2. **If approved**: Start Phase A (Week 1) with backup strategy
3. **Parallel work**: Phase C (Week 2) while A in progress
4. **Iterate on feedback** from Phase A before starting Phase B

**Roadmap Status:** Ready for approval. No changes made yet.
