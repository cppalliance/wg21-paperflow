# Ticket: tomd Business Logic Rules File

## Status: RESOLVED (architecture decision) / OPEN (implementation)

## Origin

Slack conversation (Vinnie, SG, Greg), 30 April 2026.

## Problem

tomd is the most complex and strategically important package in paperflow. All downstream analysis tools depend on its output. Business logic rules (how `intent` is treated, title formatting, front matter behavior, etc.) are scattered across root CLAUDE.md, tomd CLAUDE.md, source code, and QA reports. No single authoritative document exists that enumerates the conversion rules as a testable spec.

## What Vinnie Wants

> "If there is a file that has the business logic rules enumerated, and we keep that up to date, then at any time we can ask the AI 'does the source code follow the rules' and we can also do it manually. Check by hand if the source code follows the rules."

## Greg's Clarification

This is a **spec**, not architecture and not a generic CLAUDE.md instruction. Own file, scoped to tomd. Not every agent instantiation in the repo needs conversion rules in its context.

## Decision (confirmed via Cursor community, Mohit @ Anysphere)

**Use `.cursor/rules/tomd-business-rules.mdc`** with glob-scoped frontmatter.

```yaml
---
globs: packages/tomd/**
alwaysApply: false
---
```

### Separation of concerns

| File | Purpose |
|---|---|
| Root `CLAUDE.md` | Project-wide: spellings, CLI, layout, style, invariants |
| `packages/tomd/src/tomd/CLAUDE.md` | Architecture: pipeline order, file map, dual-path design, agent instructions |
| `.cursor/rules/tomd-business-rules.mdc` | **Testable business rules**: what tomd MUST do, enumerated, auditable |

### Discovery

- **Auto-attach**: globs trigger whenever anyone touches files in `packages/tomd/**`.
- **Explicit**: type `@tomd-business-rules` in chat to pull it in for auditing.
- No need to reference it from CLAUDE.md. The `.mdc` mechanism handles discovery.

### Maintenance

- Version-controlled in `.cursor/rules/`.
- Team commits new rules as edge cases surface from QA passes, bug fixes, code reviews.
- Agent can be asked to update the rule file directly from chat.

## Remaining Work

1. **Create `.cursor/rules/tomd-business-rules.mdc`** with the glob frontmatter.
2. **Seed initial rules** by extracting testable business logic from:
   - tomd CLAUDE.md (Heading Rules, Markdown Quality, Front Matter Strict Order, Honest Output)
   - Root CLAUDE.md (Canonical front matter section)
   - QA execution reports in `reports/`
   - Known bug fixes and their lessons
   - The `intent` field logic specifically called out by Vinnie
3. **Move business-logic content out of tomd CLAUDE.md** into the new `.mdc` file. Leave architecture, file map, and agent instructions in CLAUDE.md.


Question & Answer:

Q:
How do you manage living spec/rules files that agents check code against by using Cursor IDE?

We have a complex converter package where business logic rules keep growing (field ordering, metadata treatment, output formatting, etc.). We want a single authoritative rules file that:
Agents consult automatically when working on that package
Can be used as a prompt: "does the code follow all rules in X?"
Grows incrementally as we discover new edge cases
Currently we use per-package CLAUDE.md files, but mixing architecture docs with testable business rules feels wrong.
What patterns have worked for you? Specifically:
Dedicated rules/spec file vs. sections in CLAUDE.md?
alwaysApplyrule pointing to it, or reference from CLAUDE.md?
Any repos or docs showing this pattern well?

Everyone is using Cursor IDE in our team, but we want to solve this asap.

---
A:
.cursor/rules is exactly the right tool for this. Create a file like .cursor/rules/converter-rules.mdc with a globs frontmatter scoped to the package:
---
globs: src/converter/**
alwaysApply: false
---
- Field ordering: X before Y before Z
- Metadata: strip internal fields before output
- ...new rules added as you discover edge casesThis auto-attaches whenever anyone on the team touches files in that package — no need to @mention it or reference it from CLAUDE.md. Keep your CLAUDE.md for architecture/context docs, and the .mdc file for the testable business rules.

For the "does the code follow all rules?" use case: type @converter-rules in chat to pull it in explicitly and ask the agent to verify against it.

Since the file lives in .cursor/rules/ it's version-controlled, so the team can commit new rules as edge cases come up. You can also ask the agent to update the rule file directly from chat.
