# Handoff Checklist — Phase to Phase

Before agent hands off to next phase, verify ALL items:

## Pre-Handoff
- [ ] All phase outputs exist and are readable
- [ ] Engram entry created with correct topic_key
- [ ] Backup created (if code changes made)
- [ ] No uncommitted changes in project repos
- [ ] No open terminal/debug sessions

## Documentation
- [ ] README or setup guide exists (if needed)
- [ ] Comments added to complex code
- [ ] Architecture decision logged in Engram
- [ ] Security checklist passed (if applicable)

## Quality Gates
- [ ] Tests pass locally
- [ ] Linter/formatter clean (if code phase)
- [ ] No console errors (if web)
- [ ] Performance meets baseline (if applicable)

## Handoff Package
- [ ] All files committed or staged
- [ ] Link to evidence directory
- [ ] Link to Engram entry
- [ ] Clear notes for next phase owner

---

**If any unchecked:** Agent refuses handoff and flags blocker to user.
