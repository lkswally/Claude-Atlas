# ATLAS — Vision

## The One-Sentence Version

ATLAS exists to make it possible for a single developer to build production-quality software at the pace of a team — without sacrificing discipline, security, or maintainability.

---

## The Problem We're Solving

AI code generation is accelerating rapidly. But the bottleneck is no longer writing code — it's **coordinating a coherent development process**.

Claude can write excellent code. But by itself, it:

- Forgets what it decided last session
- Has no concept of "the architecture decided in Phase 2 constrains what Phase 3 can do"
- Will write code and skip QA if you don't explicitly ask for it
- Has no security enforcement — it will run whatever command you tell it to
- Has no way to know if the system it's building is actually working

Raw Claude is a powerful individual contributor with no memory and no discipline. ATLAS gives it both.

---

## The Mission

> **Make disciplined AI-assisted software development accessible to individual developers.**

Not by dumbing down the process. By encoding the discipline into the system itself.

A junior developer using ATLAS should produce software with the same structural guarantees as a senior engineer leading a 5-person team — because the process enforces what a senior engineer would enforce.

---

## Core Principles

### 1. The system enforces what you can't remember to check

Security hooks don't ask Claude to be careful. They block destructive commands at the OS level. Phase gates don't ask the orchestrator to check if architecture is done. They refuse to advance until the artifacts exist. Contracts don't ask agents to format their output correctly. They reject malformed envelopes.

**Discipline is structural, not behavioral.**

### 2. Memory is not optional

A system that forgets everything after each session is not a system — it's a stateless function. ATLAS writes every significant decision to Engram with a permanent topic key. Every critical path has a disk fallback. The Boot Sequence recovers from Engram before doing anything else.

**If it's not in memory, it didn't happen.**

### 3. Fail-open, always

Every feature in ATLAS has an escape hatch. Every hook is fail-open. Every tool exits gracefully on bad input. No ATLAS addition should ever cause Claude to stop working.

**The system should make good things easier. It should never make anything impossible.**

### 4. Declarative over imperative

Policies are YAML. Agent behaviors are markdown. Hard rules are JSON. Architecture decisions are markdown files with a defined schema. The system is readable and auditable without running it.

**If you can't understand the system by reading its configuration, the configuration is wrong.**

### 5. Observability is not an afterthought

The healthcheck runs 25 checks. Every capability resolution is logged to a JSONL file. Every agent invocation is tracked. The dependency graph shows you the full tree from Agent to Binary. The self-auditor detects architectural drift.

**You should always know exactly what state the system is in.**

---

## Non-Negotiables

These will not change regardless of what features are added:

1. **The orchestrator never does real work.** It only coordinates. An orchestrator that starts writing code has failed.

2. **Evidence-collector must pass before git runs.** No exceptions. No time pressure justifies skipping QA.

3. **block-no-verify.js cannot be weakened.** Security hooks can be extended but not relaxed. If a pattern is blocked, it stays blocked.

4. **Every capability must have a policy.** A capability without a declared policy is a contract violation detectable by the healthcheck.

5. **Agent files are not documentation.** They are executable specifications. Every field in the frontmatter is enforced. Every section is followed.

---

## What Success Looks Like

**v1.0.0 Stable** means:
- A developer who has never heard of ATLAS can clone it, install it, and run their first project in under 30 minutes
- The system self-heals from Engram after any compaction event
- All 25 checks in the healthcheck are green on a fresh install
- The QA suite (218+ tests) runs clean with no manual intervention
- Three external developers have used ATLAS to build a real project and reported their experience

**Long term:**
- ATLAS becomes a reference architecture for AI-assisted software development
- The capability/policy/provider pattern becomes reusable across other AI systems
- The discipline model (phase gates, contracts, hooks, observability) gets documented well enough that others can build on it

---

## What ATLAS Deliberately Avoids

- **Being a SaaS or platform.** ATLAS runs locally. No data leaves your machine except what you push to GitHub.
- **Locking you into specific MCPs.** The capability abstraction exists precisely so you can swap providers.
- **Replacing human judgment.** The orchestrator asks for confirmation before git push and deploy. The reality-checker asks a human to approve before Phase 5 begins.
- **Growing a UI.** ATLAS is a CLI/conversation system. A visual dashboard is nice-to-have, not a priority.
- **Becoming a framework.** ATLAS is a configuration layer. You don't import it. You install it.
