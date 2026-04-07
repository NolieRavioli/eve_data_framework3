---
name: Bug Report
about: Report a reproducible bug in the EVE Data Framework
labels: ["Bug", "bug"]
assignees: ''
---

## Summary
<!-- One sentence describing what is broken. -->

## Steps to Reproduce
1. 
2. 
3. 

## Expected Behaviour
<!-- What should happen? -->

## Actual Behaviour
<!-- What actually happens? Include any error messages, tracebacks, or wrong output. -->

## Environment
- **Branch / commit**: <!-- e.g. `main` @ `abc1234` -->
- **Python version**: <!-- `python --version` -->
- **OS**: <!-- e.g. Windows 11, Ubuntu 24.04 -->
- **ESI spec date**: <!-- check `_publicData/esi_specs/latest.json` or the Task Manager UI -->

## Relevant Logs
<!-- Paste any relevant log output (bus log, Flask console, browser console). Redact tokens and secrets. -->
```
<paste here>
```

## Affected Layer
<!-- Check all that apply -->
- [ ] `core/` — infrastructure (DB, ESI, auth, tasks, bus)
- [ ] `collectors/` — data collection (market, structures, character)
- [ ] `applications/` — web UI / application
- [ ] `core/web/` — Flask / SSO / templates
- [ ] `utils/build/` — code generation / build tooling
- [ ] Other: <!-- describe -->

## Additional Context
<!-- Any other relevant context, screenshots, or links. -->
