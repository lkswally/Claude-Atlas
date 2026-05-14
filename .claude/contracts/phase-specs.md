# Phase Output Specifications

## Fase 1 — Planning
**Owner:** project-manager-senior  
**Output:**
- `tasks.md` — Lista de tareas con @acceptance-criteria
- Engram entry with topic_key = `{project}/phase-1`

**Approval:** User must say "Aprobada Fase 1"

---

## Fase 2 — Architecture
**Owner:** ux-architect, ui-designer, security-engineer  
**Output:**
- `brand.json` (si visual projects)
- `architecture.md` (stack, patterns, security)
- Engram entry with topic_key = `{project}/phase-2`

**Approval:** User must say "Aprobada Fase 2"

---

## Fase 3 — Dev + QA
**Owner:** frontend-developer, backend-architect, evidence-collector  
**Output:**
- Code in `/src/**`
- Tests in `/tests/**`
- Evidence in `evidence/` (screenshots)
- Engram entry with topic_key = `{project}/phase-3`

**Approval:** User must say "Aprobada Fase 3"

---

## Fase 4 — Certification
**Owner:** reality-checker, performance-benchmarker  
**Output:**
- Reality check report
- Metrics: CWV, performance, security scan
- Engram entry with topic_key = `{project}/phase-4`

**Approval:** User must say "Aprobada Fase 4"

---

## Fase 5 — Deploy
**Owner:** git, deployer  
**Output:**
- Git commit + push
- Deploy to production (Vercel/EAS)
- Engram entry with topic_key = `{project}/phase-5`

**Approval:** 
- User must say "Aprobada Fase 5 git"
- User must say "Aprobada Fase 5 deploy"
