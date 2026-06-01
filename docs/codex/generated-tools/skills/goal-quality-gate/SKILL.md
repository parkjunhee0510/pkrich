---
name: goal-quality-gate
description: Use when the user gives a goal block asking Codex to verify quality gates, run lint/build/tests/audits, fix issues, and summarize problems, fixes, and remaining risk.
---

# Goal Quality Gate

Use this for long `goal:` requests that mix verification, targeted fixes, and a required summary format.

## Workflow

1. Parse the goal into an explicit checklist: commands, manual checks, constraints, and output format.
2. Read `AGENTS.md`, then `docs/codex/index.md`; open only the layer docs required by the touched files.
3. Preserve existing API interfaces, output schemas, and business logic unless the user explicitly asks for a contract change.
4. Run the smallest relevant checks first, then the full requested commands when the change is stable.
5. If a check fails, diagnose root cause before editing; fix only the scoped issue and rerun the failing check.
6. Keep generated artifact edits schema-compatible and minimal.
7. Final response order should match the goal when specified, usually: problem list, fix status, remaining risk.

## Default Checks

Use only when relevant to the goal and available in the repo:

```bash
python -m compileall main.py src tests
python -m pytest
npm run lint
npm run build
npm run test
python -m src.cli.output_health_check
```

## Guardrails

- Do not treat warnings as success if the goal asked to fix them.
- Do not skip requested checks silently; report unavailable scripts or environment blockers.
- Do not broaden refactors beyond the quality gate.
- For frontend library behavior, use Context7 before relying on framework or component docs.
