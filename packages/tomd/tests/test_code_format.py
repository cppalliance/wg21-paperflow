#
# Copyright (c) 2026 Luan Fonseca (luan@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Unit tests for the per-line whitespace normalizer used in CODE sections."""

import pytest

from tomd.lib.pdf.code_format import normalize_code_line


class TestTemplateAngles:
    def test_strip_space_before_open_angle(self):
        assert (
            normalize_code_line("std::numeric_limits <From>")
            == "std::numeric_limits<From>"
        )

    def test_strip_space_before_close_angle(self):
        assert (
            normalize_code_line("std::numeric_limits<From >")
            == "std::numeric_limits<From>"
        )

    def test_strip_space_both_sides(self):
        assert (
            normalize_code_line("std::numeric_limits <From >")
            == "std::numeric_limits<From>"
        )

    def test_close_angle_immediately_before_semicolon(self):
        assert (
            normalize_code_line("vector<int >;")
            == "vector<int>;"
        )

    def test_close_angle_immediately_before_paren(self):
        # Common in calls like `foo<T>()`
        assert (
            normalize_code_line("foo<T >()")
            == "foo<T>()"
        )

    def test_template_parameter_pack(self):
        assert (
            normalize_code_line("tuple <int, double, char>")
            == "tuple<int, double, char>"
        )

    def test_do_not_touch_less_than_comparison(self):
        # `a < b` has `a` and `b` as identifiers but the next token after
        # `<` is whitespace+identifier — but only `<` (identifier+<+space+identifier).
        # We only strip when there's no space after `<`.
        assert normalize_code_line("if (a < b)") == "if (a < b)"

    def test_do_not_touch_greater_than_comparison(self):
        assert normalize_code_line("if (a > b)") == "if (a > b)"

    def test_double_close_angle_left_alone(self):
        # `>>` is a right-shift or nested template close; we don't touch
        # it as a `space before close angle` because the lookahead
        # excludes `>` following another `>`.
        assert normalize_code_line("vector<vector<int>>") == "vector<vector<int>>"


class TestAttributeBrackets:
    def test_strip_inside_attribute(self):
        assert (
            normalize_code_line("[[ maybe_unused ]] int x;")
            == "[[maybe_unused]] int x;"
        )

    def test_strip_inside_nodiscard(self):
        assert (
            normalize_code_line("[[ nodiscard ]] int f();")
            == "[[nodiscard]] int f();"
        )

    def test_unspaced_attribute_unchanged(self):
        assert (
            normalize_code_line("[[nodiscard]] int f();")
            == "[[nodiscard]] int f();"
        )


class TestQualifiedName:
    def test_strip_after_double_colon(self):
        assert normalize_code_line("L:: lowest()") == "L::lowest()"

    def test_strip_after_double_colon_chained(self):
        assert (
            normalize_code_line("std:: numeric_limits<int>")
            == "std::numeric_limits<int>"
        )

    def test_unspaced_double_colon_unchanged(self):
        assert normalize_code_line("std::vector<int>") == "std::vector<int>"


class TestFunctionCall:
    def test_strip_space_before_open_paren(self):
        assert normalize_code_line("converting_limits_throws ()") == "converting_limits_throws()"

    def test_skip_if_keyword(self):
        assert normalize_code_line("if (x > 0)") == "if (x > 0)"

    def test_skip_for_keyword(self):
        assert normalize_code_line("for (int i = 0; i < n; ++i)") == "for (int i = 0; i < n; ++i)"

    def test_skip_while_keyword(self):
        assert normalize_code_line("while (cond)") == "while (cond)"

    def test_skip_switch_keyword(self):
        assert normalize_code_line("switch (x)") == "switch (x)"

    def test_skip_catch_keyword(self):
        assert normalize_code_line("} catch (...) {") == "} catch (...) {"

    def test_skip_return_with_parens(self):
        assert normalize_code_line("return (x + y)") == "return (x + y)"

    def test_skip_sizeof_keyword(self):
        assert normalize_code_line("sizeof (T)") == "sizeof (T)"

    def test_skip_decltype_keyword(self):
        assert normalize_code_line("decltype (expr)") == "decltype (expr)"

    def test_skip_static_assert_keyword(self):
        assert normalize_code_line("static_assert (cond)") == "static_assert (cond)"


class TestCommaSpacing:
    def test_strip_space_before_comma(self):
        assert normalize_code_line("f(a , b , c)") == "f(a, b, c)"

    def test_template_arg_comma(self):
        assert (
            normalize_code_line("std::convertible_to<From , To>")
            == "std::convertible_to<From, To>"
        )


class TestStringLiteralSafety:
    def test_skip_lines_with_double_quote(self):
        line = 'std::string s = "hello < world > test";'
        assert normalize_code_line(line) == line

    def test_skip_lines_with_single_quote(self):
        line = "char c = 'x'; if (c == 'a') {}"
        assert normalize_code_line(line) == line

    def test_skip_raw_string_literal(self):
        line = 'auto s = R"(template <T>)";'
        assert normalize_code_line(line) == line


class TestIndentationPreserved:
    def test_leading_whitespace_kept(self):
        assert (
            normalize_code_line("    using L = std::numeric_limits <From >;")
            == "    using L = std::numeric_limits<From>;"
        )


class TestCompoundLine:
    def test_p4012r0_template_header(self):
        assert (
            normalize_code_line("template <typename To, typename From >")
            == "template <typename To, typename From>"
        )

    def test_p4012r0_concept_line(self):
        line = "  concept really_convertible_to = std::convertible_to <From , To>"
        expected = "  concept really_convertible_to = std::convertible_to<From, To>"
        assert normalize_code_line(line) == expected

    def test_p4012r0_attribute_line(self):
        assert (
            normalize_code_line("      [[ maybe_unused ]] To x = L::max();")
            == "      [[maybe_unused]] To x = L::max();"
        )

    def test_p4012r0_qualified_call(self):
        assert (
            normalize_code_line("      x = L:: lowest ();")
            == "      x = L::lowest();"
        )

    def test_p4012r0_call_with_args(self):
        line = "                                     and not converting_limits_throws <To, From >();"
        expected = "                                     and not converting_limits_throws<To, From>();"
        assert normalize_code_line(line) == expected


class TestEmptyAndTrivial:
    @pytest.mark.parametrize("line", ["", " ", "   ", "// comment", "/* block */"])
    def test_no_op_on_trivial(self, line):
        assert normalize_code_line(line) == line


class TestPreprocessorDirective:
    def test_skip_include_with_angle_header(self):
        assert (
            normalize_code_line("#include <stdio.h>")
            == "#include <stdio.h>"
        )

    def test_skip_indented_include(self):
        assert (
            normalize_code_line("    #include <vector>")
            == "    #include <vector>"
        )

    def test_skip_define(self):
        # `#define FOO bar (baz)` should not collapse `bar (baz)`.
        line = "#define FOO bar (baz)"
        assert normalize_code_line(line) == line


class TestLineComment:
    def test_skip_inside_trailing_comment(self):
        # Identifier-followed-by-`<...>` inside a comment is prose, not
        # template syntax; tightening it would corrupt the comment.
        assert (
            normalize_code_line("int x; // also in <proxy>")
            == "int x; // also in <proxy>"
        )

    def test_normalize_code_before_comment(self):
        # Code before the comment IS normalized; comment text is left alone.
        assert (
            normalize_code_line("vector <int> x; // see in <proxy>")
            == "vector<int> x; // see in <proxy>"
        )
