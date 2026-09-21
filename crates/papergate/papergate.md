---
name: papergate
description: Report on the evidence a WG21 paper provides for its need of standardization
promptforge: 0
models:
  # TODO(#445): pin a temperature here (0 before the port; #415 proposes
  # 0.3) once cppalliance/promptforge#69 restores it and the submodule is
  # bumped. Until then runs sample at the gateway default and verdicts
  # vary. Adding it now is a parse error (ModelRole denies unknown fields).
  writer:
    # No hard `no-thinking` keyword: the engine reports it unmet against a
    # thinking-switchable model, and the harness refuses a prompt with an
    # unmet requirement outright. Thinking follows the gateway's default.
    min_context: 32768
    description: A careful analysis model suited to structured reasoning and long-context review
output:
  path: report.md
  description: The report produced by analysis
---

# Papergate

```lua
models.default("writer")
```

## Dissect

```lua
-- The paper arrives as the run's args (the harness launch request). The
-- Evaluate arms read numbered line ranges from the store, so the paper is
-- written there before the fanout.
store.write("paper.md", args)
var.paper = untrusted(args)
sections = {}
tools.add_local("add_section", "Add a section with its line range", {
    name = {"string", "Section heading text"},
    start_line = {"integer", "1-based line number where the section begins"},
    end_line = {"integer", "1-based line number where the section ends"},
}, function(args)
    table.insert(sections, {
        name = args.name,
        start_line = args.start_line,
        end_line = args.end_line,
    })
    return "added " .. args.name
end)
```

Identify every H2 section in this paper:

{{ var.paper }}

For each section, record its name and line number range. Do not output any text.

```lua
models.loop(messages.new():user(prose))
local ranges = {}
for _, s in ipairs(sections) do
    table.insert(ranges, s.start_line .. ":" .. s.end_line)
end
-- Arms return their evidence and the join delivers it in section order;
-- the parent writes the merge. Two live arms may not write one store path.
local evidence = fanout("### Evaluate", ranges)
store.write("evidence.md", table.concat(evidence, "\n"))
```

### Evaluate

```lua
local first, last = item:match("^(%d+):(%d+)$")
var.section = untrusted(store.read_numbered("paper.md", tonumber(first), tonumber(last)))
```

You are a reviewer looking at this section of text from a C++ Standardization proposal:

{{ var.section }}

For each sentence in the section, write the sentence verbatim including its line number, as a bullet, if it meets any of the following criteria:
* describes the reason, motivation, or justification for the proposal
* provides a measurement of the usage, field experience, size of audience for the proposal
* identifies design alternatives, competing proposals or library elements, prior art
* explains the need for standardization
* identifies a coordination probem, enables interoperability
* shows why third party solutions are insufficient
* describes implementation experience, field experience, deployment experience

```lua
return models.infer(prose)
```

## Analyze

```lua
var.evidence = untrusted(store.read("evidence.md"))
```

You are the reviewer of a C++ Standardization proposal, evaluating this evidence:

{{ var.evidence }}

The justification for a proposal to have need of standardization must demonstrate why the proposal's benefits cannot be obtained simply by publishing its artifiacts. For example on github, or on a blog. Describe the extent that the evidence justifies the need for standardization (using the definition given) by providing the evidence of that need as a series of sentences, up to five sentences total. Use the best evidence. Where each of the sentence of the evidence sentence paraphrases the information that's provided in the bullets.

Use this markdown report template exactly:

Verdict: exactly one of { n/a, None, Weak, Adequate, Strong, Excellent }

{A single sentence describing the amount of evidence provided, no lists, no details}

{up to three bulleted sentences describing the best pieces of evidence}

```lua
-- The report is the declared store output and the run's final text. This
-- must stay the run's last model call: papergate reads the last assistant
-- reply of the run as the report.
local report = models.infer(prose)
store.write("report.md", report)
return report
```
