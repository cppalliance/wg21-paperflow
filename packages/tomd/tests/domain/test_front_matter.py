"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import pytest

from tomd.domain.front_matter import is_blank_value


@pytest.mark.parametrize("value", [None, "", "   ", "\t\n", [], (), ["", "  "]])
def test_is_blank_value_blank(value):
    assert is_blank_value(value)


@pytest.mark.parametrize("value", ["x", " x ", ["", "a"], ("a",), 0])
def test_is_blank_value_not_blank(value):
    assert not is_blank_value(value)
