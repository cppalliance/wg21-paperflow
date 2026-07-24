#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

import pytest
from chatsmith.pack import PackNotFoundError, resolve
from chatsmith.pack.base import FileSystemPack


def test_bundled_wg21_pack_loads() -> None:
    pack = resolve("wg21")
    assert pack.name == "wg21"
    assert "Mentographist" in pack.system_prompt()
    assert pack.reply_instruction()
    assert "interview is starting" in pack.kickoff_instruction().lower()


def test_wg21_pack_data_files() -> None:
    pack = resolve("wg21")
    assert len(pack.keyterms()) > 10
    assert pack.corpus_by_category()  # non-empty vocabulary
    assert pack.mishearings()
    # The normalizer prefix folds rules + vocabulary together.
    assert "reference vocabulary" in pack.normalize_system_prompt().lower()


def test_wg21_branding_and_services() -> None:
    pack = resolve("wg21")
    branding = pack.branding()
    assert branding.character == "Nova"  # persona stays Nova, decoupled from pkg name
    assert branding.themes.get("chips")
    services = pack.services()
    assert "default" in services  # required for pipeline routing


def test_missing_pack_raises() -> None:
    with pytest.raises(PackNotFoundError):
        resolve("does-not-exist")


def test_corpus_rejects_non_list_value(tmp_path) -> None:
    # A pack author writing a bare string instead of a list must fail loudly rather
    # than silently exploding it into per-character "terms".
    (tmp_path / "pack.toml").write_text('name = "t"\n', encoding="utf-8")
    (tmp_path / "corpus_by_category.json").write_text(
        '{"area": "not-a-list"}', encoding="utf-8"
    )
    pack = FileSystemPack(tmp_path)
    with pytest.raises(TypeError):
        pack.corpus_by_category()


def test_mishearings_rejects_non_object(tmp_path) -> None:
    # A JSON array (or any non-object) at the top level is a shape mistake and must
    # fail loudly, consistently with the corpus loader, not crash on `.items()`.
    (tmp_path / "pack.toml").write_text('name = "t"\n', encoding="utf-8")
    (tmp_path / "mishearings.json").write_text('["not", "an", "object"]', encoding="utf-8")
    pack = FileSystemPack(tmp_path)
    with pytest.raises(TypeError):
        pack.mishearings()
