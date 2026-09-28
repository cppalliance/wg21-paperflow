"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""
from typing import Callable

from tomd.domain.document import PaperDocument
from tomd.domain.elements import (
    Blockquote,
    CodeBlock,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    ThematicBreak,
    WordingBlock,
)
from tomd.domain.metadata import PaperMetadata
from tomd.domain.span import (
    CodeSpan,
    EmphasisSpan,
    LinkSpan,
    StrikethroughSpan,
    StrongSpan,
    TextSpan,
    UnderlineSpan,
)
from tomd.domain.table import (
    CellAlign,
    CodeCell,
    Table,
    TableKind,
    TableRow,
    TableStrategy,
    TextCell,
)


def sample_abstract_prose_document() -> PaperDocument:
    """Construct a sample PaperDocument with multi-level ATX headings, anchors, and prose."""
    meta = PaperMetadata(
        title="Standard Wording Anchors and Abstract Demonstration",
        document="P3000R0",
        date="2026-09-28",
        intent="info",
        audience=["EWG", "LEWG"],
        extra={"author": ["Jane Doe <jane@example.com>"]},
    )
    elements = [
        Heading.from_text(2, "Abstract", id="abstract"),
        Paragraph(
            spans=[
                TextSpan("This proposal specifies an anchor-rich navigation model for "),
                StrongSpan.from_text("WG21 ISO C++"),
                TextSpan(" technical specifications. It introduces "),
                CodeSpan("std::execution"),
                TextSpan(" refinements and cross-references "),
                LinkSpan.from_text("P2300R10", url="https://wg21.link/p2300r10"),
                TextSpan(" with "),
                EmphasisSpan.from_text("zero runtime overhead"),
                TextSpan("."),
            ]
        ),
        Heading.from_text(2, "1. Introduction", id="intro"),
        Paragraph.from_text(
            "Section anchors enable direct URL linking into individual proposal headings."
        ),
        Heading.from_text(3, "1.1 Background & History", id="intro-history"),
        Paragraph.from_text(
            "Historically, WG21 papers lacked standardized stable anchor tags."
        ),
        Heading.from_text(4, "1.1.1 Legacy Incompatibilities", id="intro-legacy"),
        Paragraph.from_text(
            "Previous toolchains produced conflicting anchor names or omitted them."
        ),
    ]
    return PaperDocument(paper_id="P3000R0", metadata=meta, elements=elements)


def sample_tony_table_document() -> PaperDocument:
    """Construct a sample PaperDocument featuring a Tony Table Before/After code comparison."""
    meta = PaperMetadata(
        title="Tony Table Comparison Demonstration",
        document="P3001R0",
        date="2026-09-28",
        intent="change",
        audience=["LEWG"],
    )
    table = Table(
        headers=[
            TextCell.from_text("Before (C++23)"),
            TextCell.from_text("After (Proposed)"),
        ],
        rows=[
            TableRow(
                cells=[
                    CodeCell(
                        code=(
                            "// Manual iteration\n"
                            "for (auto it = c.begin(); it != c.end(); ++it) {\n"
                            "    process(*it);\n"
                            "}"
                        ),
                        language="cpp",
                    ),
                    CodeCell(
                        code=(
                            "// Range-based view\n"
                            "for (auto&& x : c | std::views::filter(pred)) {\n"
                            "    process(x);\n"
                            "}"
                        ),
                        language="cpp",
                    ),
                ]
            ),
            TableRow(
                cells=[
                    CodeCell(
                        code=(
                            "std::vector<int> v;\n"
                            "// Potential reallocation\n"
                            "v.push_back(42);"
                        ),
                        language="cpp",
                    ),
                    CodeCell(
                        code=(
                            "std::hive<int> h;\n"
                            "// Never reallocates elements\n"
                            "h.insert(42);"
                        ),
                        language="cpp",
                    ),
                ]
            ),
        ],
        strategy=TableStrategy.MIXED_HTML,
        kind=TableKind.TONY_TABLE,
        caption="Table 1: Side-by-side comparison",
    )
    elements = [
        Heading.from_text(2, "Code Comparison", id="comparison"),
        Paragraph.from_text(
            "The following Tony Table illustrates the syntactic delta:"
        ),
        table,
    ]
    return PaperDocument(paper_id="P3001R0", metadata=meta, elements=elements)


def sample_wording_diff_document() -> PaperDocument:
    """Construct a sample PaperDocument with proposed wording revisions and edits."""
    meta = PaperMetadata(
        title="Proposed Wording for Standard Fixes",
        document="P3002R0",
        date="2026-09-28",
        intent="change",
        audience=["LWG"],
    )
    elements = [
        Heading.from_text(2, "Proposed Wording", id="wording"),
        Paragraph.from_text("All wording modifications are relative to N4950."),
        Heading.from_text(
            3,
            "24.3.11 Class template hive [hive.overview]",
            id="hive.overview",
        ),
        Paragraph.from_text("Modify paragraph 1 as follows:"),
        Paragraph(
            spans=[
                TextSpan(
                    "A hive is a sequence container that supports constant-time insertion and erasure. "
                ),
                TextSpan("An instance of `hive` "),
                StrikethroughSpan(
                    children=(
                        TextSpan("shall allocate elements using "),
                        CodeSpan("std::allocator"),
                        TextSpan(" exclusively."),
                    )
                ),
                TextSpan(" "),
                UnderlineSpan(
                    children=(
                        TextSpan(
                            "may allocate memory using an allocator satisfying the "
                        ),
                        CodeSpan("Allocator"),
                        TextSpan(" requirements [allocator.requirements]."),
                    )
                ),
            ]
        ),
        Paragraph.from_text("Modify 24.3.11.4 [hive.modifiers] as follows:"),
        Blockquote.from_text(
            "iterator insert(const T& value);\n"
            "iterator insert(T&& value);\n"
            "\n"
            "-1- Effects: Inserts a copy or moved value into the hive.\n"
            "-2- Returns: An iterator pointing to the newly inserted element.\n"
            "-3- Complexity: Constant time.\n"
            "-4- Remarks: Does not invalidate any existing references or iterators."
        ),
        WordingBlock(
            role="wording",
            text="<ins>A hive does not provide contiguous storage guarantee [container.reqmts].</ins>",
        ),
    ]
    return PaperDocument(paper_id="P3002R0", metadata=meta, elements=elements)


def sample_poll_table_document() -> PaperDocument:
    """Construct a sample PaperDocument with Straw Poll and Feature Test Macro tables."""
    meta = PaperMetadata(
        title="Straw Polls and Feature Test Macro Matrix",
        document="P3003R0",
        date="2026-09-28",
        intent="info",
        audience=["LEWG"],
    )

    poll_table = Table(
        headers=[
            TextCell.from_text("Poll", align=CellAlign.LEFT),
            TextCell.from_text("SF", align=CellAlign.CENTER),
            TextCell.from_text("F", align=CellAlign.CENTER),
            TextCell.from_text("N", align=CellAlign.CENTER),
            TextCell.from_text("A", align=CellAlign.CENTER),
            TextCell.from_text("SA", align=CellAlign.CENTER),
            TextCell.from_text("Consensus", align=CellAlign.RIGHT),
        ],
        rows=[
            TableRow(
                cells=[
                    TextCell(
                        spans=[
                            TextSpan("Forward "),
                            CodeSpan("P3000R1"),
                            TextSpan(" to LWG for C++26?"),
                        ]
                    ),
                    TextCell.from_text("18"),
                    TextCell.from_text("7"),
                    TextCell.from_text("2"),
                    TextCell.from_text("0"),
                    TextCell.from_text("0"),
                    TextCell.from_text("Consensus"),
                ]
            ),
            TableRow(
                cells=[
                    TextCell.from_text("Rename container to colony?"),
                    TextCell.from_text("2"),
                    TextCell.from_text("4"),
                    TextCell.from_text("6"),
                    TextCell.from_text("12"),
                    TextCell.from_text("5"),
                    TextCell.from_text("No consensus"),
                ]
            ),
        ],
        strategy=TableStrategy.PIPE,
        kind=TableKind.POLL_TABLE,
        caption="Tokyo 2024 Straw Polls",
    )

    feature_table = Table(
        headers=[
            TextCell.from_text("Macro", align=CellAlign.LEFT),
            TextCell.from_text("Value", align=CellAlign.RIGHT),
            TextCell.from_text("Header", align=CellAlign.CENTER),
            TextCell.from_text("Notes", align=CellAlign.DEFAULT),
        ],
        rows=[
            TableRow(
                cells=[
                    TextCell(spans=[CodeSpan("__cpp_lib_hive")]),
                    TextCell.from_text("202606L"),
                    TextCell(spans=[CodeSpan("<hive>")]),
                    TextCell.from_text("Original proposal"),
                ]
            ),
            TableRow(
                cells=[
                    TextCell(spans=[CodeSpan("__cpp_lib_execution")]),
                    TextCell.from_text("202603L"),
                    TextCell(spans=[CodeSpan("<execution>")]),
                ]
            ),
            TableRow(
                cells=[
                    TextCell.from_text("Bitwise a | b pipeline"),
                    TextCell.from_text("202609L"),
                    TextCell(spans=[CodeSpan("<ranges>")]),
                    TextCell.from_text("Multi-line\nnote entry"),
                ]
            ),
        ],
        strategy=TableStrategy.PIPE,
        kind=TableKind.STANDARD,
    )

    elements = [
        Heading.from_text(2, "Poll Results", id="polls"),
        poll_table,
        Heading.from_text(2, "Feature Test Macros", id="macros"),
        feature_table,
    ]
    return PaperDocument(paper_id="P3003R0", metadata=meta, elements=elements)


def sample_rich_blocks_document() -> PaperDocument:
    """Construct a sample PaperDocument with nested lists, code fences, and blockquotes."""
    meta = PaperMetadata(
        title="Nested Lists, Blockquotes, and Code Blocks",
        document="P3004R0",
        date="2026-09-28",
        intent="info",
        audience=["LEWG"],
    )

    unordered_list = ListBlock(
        items=[
            ListItem(
                spans=[
                    TextSpan(
                        "High Priority:\n"
                        "- Stable pointer guarantees across insertion\n"
                        "- Constant time element erasure"
                    )
                ]
            ),
            ListItem(
                spans=[
                    TextSpan(
                        "Medium Priority:\n"
                        "- Full bidirectional iterator conformance\n"
                        "- Custom memory allocator support"
                    )
                ]
            ),
            ListItem(
                spans=[
                    TextSpan("Low Priority: Legacy interoperability wrappers")
                ]
            ),
        ],
        ordered=False,
    )

    ordered_list = ListBlock(
        items=[
            ListItem.from_text(
                "Analyze existing benchmarks.\n"
                "Initial results indicate 2x speedup."
            ),
            ListItem.from_text(
                "Implement prototype in reference repository."
            ),
            ListItem.from_text("Submit wording to LWG review."),
        ],
        ordered=True,
    )

    synopsis_code = CodeBlock(
        code=(
            "#include <hive>\n\n"
            "template <typename T>\n"
            "class hive {\n"
            "public:\n"
            "    using value_type = T;\n"
            "};"
        ),
        language="cpp",
        title="hive_synopsis.hpp",
    )

    nested_fence_code = CodeBlock(
        code=(
            "```cpp\n"
            "// Nested markdown code fence inside block\n"
            "auto x = 42;\n"
            "```"
        ),
        language="markdown",
        title="doc_snippet.md",
    )

    design_note = Blockquote.from_text(
        "[Note 1: An implementation may choose block allocation chunk sizes based on cache line geometry.\n"
        "- end note]"
    )

    elements = [
        Heading.from_text(2, "Design & Implementation", id="design"),
        Paragraph.from_text(
            "Key design requirements are grouped into priority tiers:"
        ),
        unordered_list,
        Heading.from_text(3, "Execution Steps", id="steps"),
        ordered_list,
        ThematicBreak(),
        Heading.from_text(3, "Code Synopsis", id="synopsis"),
        synopsis_code,
        Heading.from_text(3, "Markdown Fence Escaping", id="fence-escape"),
        nested_fence_code,
        design_note,
    ]
    return PaperDocument(paper_id="P3004R0", metadata=meta, elements=elements)


def sample_full_proposal_document() -> PaperDocument:
    """Construct a complete sample PaperDocument modeling the P0447R26 std::hive proposal."""
    meta = PaperMetadata(
        title="std::hive: An Unordered Contiguous-Block Container for C++26",
        document="P0447R26",
        date="2026-09-28",
        intent="change",
        audience=["LEWG", "LWG"],
        reply_to="matt.bentley.k-17@outlook.com",
        extra={
            "author": [
                "Matthew Bentley <matt.bentley.k-17@outlook.com>",
                "Jane Doe <jane@example.com>",
            ]
        },
    )

    abstract_para = Paragraph(
        spans=[
            TextSpan("This paper proposes "),
            CodeSpan("std::hive"),
            TextSpan(" (formerly "),
            EmphasisSpan.from_text("colony"),
            TextSpan(") as a new standard container. It guarantees "),
            StrongSpan.from_text("pointer stability"),
            TextSpan(
                " and fast element removal without shifting subsequent elements."
            ),
        ]
    )

    motivation_list = ListBlock(
        items=[
            ListItem.from_text("Stable pointers across insertions"),
            ListItem.from_text("Constant time erasure with tombstone tracking"),
            ListItem.from_text("No relocation of existing elements"),
        ],
        ordered=False,
    )

    comparison_table = Table(
        headers=[
            TextCell.from_text("Before (C++23)"),
            TextCell.from_text("After (Proposed)"),
        ],
        rows=[
            TableRow(
                cells=[
                    CodeCell(
                        code=(
                            "// Vector with pointer invalidation\n"
                            "std::vector<Item> items;\n"
                            "items.push_back(item);"
                        ),
                        language="cpp",
                    ),
                    CodeCell(
                        code=(
                            "// Hive with pointer stability\n"
                            "std::hive<Item> items;\n"
                            "items.insert(item);"
                        ),
                        language="cpp",
                    ),
                ]
            )
        ],
        strategy=TableStrategy.PIPE,
        kind=TableKind.TONY_TABLE,
        caption="Table 1: Usage comparison",
    )

    synopsis_code = CodeBlock(
        code=(
            "template <typename T, typename Alloc = std::allocator<T>>\n"
            "class hive {\n"
            "public:\n"
            "    iterator insert(const T& val);\n"
            "    iterator erase(const_iterator it);\n"
            "};"
        ),
        language="cpp",
        title="hive.hpp",
    )

    note_quote = Blockquote.from_text(
        "[Note 1: Iterators are bidirectional and not random access.\n"
        "- end note]"
    )

    wording_para = Paragraph(
        spans=[
            TextSpan("Modify 24.3 [containers.summary] paragraph 1 as follows: "),
            StrikethroughSpan.from_text("The library provides sequence containers."),
            TextSpan(" "),
            UnderlineSpan.from_text(
                "The library provides sequence containers, including hive."
            ),
        ]
    )

    wording_block = WordingBlock(
        role="wording",
        text="<ins>A hive fulfills all requirements of a SequenceContainer.</ins>",
    )

    poll_table = Table(
        headers=[
            TextCell.from_text("Motion", align=CellAlign.LEFT),
            TextCell.from_text("SF", align=CellAlign.CENTER),
            TextCell.from_text("F", align=CellAlign.CENTER),
            TextCell.from_text("N", align=CellAlign.CENTER),
            TextCell.from_text("A", align=CellAlign.CENTER),
            TextCell.from_text("SA", align=CellAlign.CENTER),
            TextCell.from_text("Outcome", align=CellAlign.RIGHT),
        ],
        rows=[
            TableRow(
                cells=[
                    TextCell.from_text("Send P0447R26 to LWG for C++26?"),
                    TextCell.from_text("24"),
                    TextCell.from_text("6"),
                    TextCell.from_text("0"),
                    TextCell.from_text("0"),
                    TextCell.from_text("0"),
                    TextCell.from_text("Unanimous"),
                ]
            )
        ],
        strategy=TableStrategy.PIPE,
        kind=TableKind.POLL_TABLE,
    )

    references_list = ListBlock(
        items=[
            ListItem(
                spans=[
                    LinkSpan.from_text(
                        "P0447R26: Introduction of std::hive",
                        url="https://wg21.link/p0447r26",
                    )
                ]
            ),
            ListItem(
                spans=[
                    LinkSpan.from_text(
                        "P2300R10: std::execution",
                        url="https://wg21.link/p2300r10",
                    )
                ]
            ),
        ],
        ordered=True,
    )

    elements = [
        Heading.from_text(2, "Abstract", id="abstract"),
        abstract_para,
        Heading.from_text(2, "1. Introduction", id="intro"),
        Paragraph.from_text(
            "Standard sequence containers require tradeoffs between pointer validity "
            "and cache friendliness. While vector forces reallocations, hive uses "
            "segmented contiguous blocks."
        ),
        Heading.from_text(3, "1.1 Key Characteristics", id="intro-key"),
        motivation_list,
        Heading.from_text(2, "2. Code Comparison", id="comparison"),
        comparison_table,
        Heading.from_text(2, "3. Design Synopsis", id="synopsis"),
        synopsis_code,
        note_quote,
        ThematicBreak(),
        Heading.from_text(2, "4. Proposed Wording", id="wording"),
        wording_para,
        wording_block,
        Heading.from_text(2, "5. Polls & Consensus", id="polls"),
        poll_table,
        Heading.from_text(2, "6. References", id="references"),
        references_list,
    ]
    return PaperDocument(paper_id="P0447R26", metadata=meta, elements=elements)


ALL_SAMPLE_DOCUMENT_BUILDERS: tuple[Callable[[], PaperDocument], ...] = (
    sample_abstract_prose_document,
    sample_tony_table_document,
    sample_wording_diff_document,
    sample_poll_table_document,
    sample_rich_blocks_document,
    sample_full_proposal_document,
)
