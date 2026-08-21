---
name: papergate
description: Report on the evidence a WG21 paper provides for its need of standardization
promptforge: 1
input:
  path: paper.md
  description: The WG21 paper markdown to analyze
output:
  path: report.md
  description: The report produced by analysis
---

# Papergate

```lua
models.default("writer",
    "A careful analysis model suited to structured reasoning and long-context review",
    { thinking = false, temperature = 0, context = 32768 })
```

## Dissect

```lua
var.paper = untrusted(store.read("paper.md"))
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
local ranges = {}
for _, s in ipairs(sections) do
    table.insert(ranges, s.start_line .. ":" .. s.end_line)
end
local result = fanout("### Evaluate", ranges)
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
store.append("evidence.md", reply)
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
store.write("report.md", reply)
return "Done."
```
