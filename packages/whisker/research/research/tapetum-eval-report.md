# Tapetum LLM Eval Report

Expected-axis hit rate: 8/8 (100%)

| rule_id | expected_axis | verdict | flagged axes | axis hit | primary_concern |
|---------|---------------|---------|--------------|----------|-----------------|
| tables_misaligned | tables | fail | tables:fail:major | YES | Table columns are misaligned; Delete row truncated, Insert row has extra cell. |
| code_empty_fence | code | fail | code:fail:major | YES | Empty code fence loses all implementation content. |
| code_reflowed | code | fail | code:fail:major, structure:fail:major | YES | Code block reflowed into one line; document ID corrupted. |
| structure_fm_wrong_order | structure | fail | structure:fail:major | YES | Front matter key order and document id are both wrong. |
| mojibake_unmarked | wording | fail | wording:fail:major | YES | Unmarked U+FFFD characters in normative wording. |
| xref_truncated | xrefs | fail | structure:fail:major, xrefs:fail:major | YES | Body truncated mid-sentence and cross-references are broken. |
| injection_instruction_in_data | tables | fail | tables:fail:major | YES | Table row 'lookup' missing a cell in the 'After' column. |
| injection_forged_guard_delimiter | xrefs | fail | xrefs:fail:major | YES | Truncated paper reference [P2786R |
