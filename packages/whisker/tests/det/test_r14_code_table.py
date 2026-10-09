#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""R14 and the labeled fence-group table form (issue #443)."""

from __future__ import annotations

from whisker.det.llm_readability import (
    STATUS_FAIL,
    STATUS_NOT_APPLICABLE,
    STATUS_PASS,
)
from whisker.det.llm_readability.profile import resolved_core_only
from whisker.det.llm_readability.validate import (
    document_facts,
    evaluate,
    table_units_from_markdown,
)
from whisker.tables import parse_code_table_groups

_FIGURE2_HTML = """\
<!-- tomd:mixed-table -->
<table>
<tr><th>Name</th><th>Value</th></tr>
<tr>
<td><pre><code>template &lt;class P&gt;</code></pre></td>
<td><pre><code>int &amp; value</code></pre></td>
</tr>
</table>
"""

_FIGURE2_FENCE = (
    "<!-- tomd:mixed-table -->\n"
    "*Name*\n"
    "*Value*\n"
    "\n"
    "**Abstraction**\n"
    "```cpp\n"
    "template <class P>\n"
    "```\n"
    "```cpp\n"
    "int& value\n"
    "```\n"
)


def _r14(md: str, source_format: str):
    units = table_units_from_markdown(md)
    report = evaluate(
        resolved_core_only(),
        units,
        source_format=source_format,
        markdown=md,
    )
    return units, report


def test_r14_pdf_html_table_fails():
    _units, report = _r14(_FIGURE2_HTML, "pdf")
    result = report.result("R14")
    assert result.status == STATUS_FAIL
    assert result.findings
    assert any("table index" in finding.message or "index" in finding.message
               for finding in result.findings)


def test_r14_html_source_does_not_fail():
    _units, report = _r14(_FIGURE2_HTML, "html")
    assert report.result("R14").status == STATUS_NOT_APPLICABLE


def test_r14_fence_group_does_not_fail():
    units, report = _r14(_FIGURE2_FENCE, "pdf")
    assert report.result("R14").status == STATUS_PASS
    assert any(unit.fmt == "code_group" for unit in units)
    assert report.table_count == len(units)
    grids = parse_code_table_groups(_FIGURE2_FENCE)
    assert grids == [[
        ["", "Name", "Value"],
        ["Abstraction", "template <class P>", "int& value"],
    ]]


def test_ins_del_entities_do_not_count():
    wording = (
        "<table><tr><td>"
        "<ins>&lt;int&gt;</ins>"
        "<del>&gt; &amp; &quot;</del>"
        "</td></tr></table>"
    )
    assert document_facts((), markdown=wording).html_entity_count == 0
    outside = "prose &lt; &gt; &amp; &quot;"
    assert document_facts((), markdown=outside).html_entity_count == 0
    bare = "<table><tr><td>&lt; &gt; &amp; &quot;</td></tr></table>"
    assert document_facts((), markdown=bare).html_entity_count == 4


def test_code_table_group_round_trip():
    body = "void f() {\n    return;\n}"
    md = (
        "<!-- tomd:mixed-table -->\n"
        "*Header*\n"
        "\n"
        "**Row**\n"
        "```cpp\n"
        f"{body}\n"
        "```\n"
    )
    assert parse_code_table_groups(md) == [[
        ["", "Header"],
        ["Row", body],
    ]]
