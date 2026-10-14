#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for whisker.survey.registry: lookups, lock parsing, patch specs."""

from whisker.survey.registry import (
    PatchSpec,
    get_competitor,
    list_competitors,
    load_lockfile,
)


class TestRegistryLookups:
    """Registry lookup and listing tests."""

    def test_list_competitors_nonempty(self):
        competitors = list_competitors()
        assert len(competitors) >= 1

    def test_marker_is_first(self):
        competitors = list_competitors()
        assert competitors[0].name == "marker"

    def test_get_competitor_marker(self):
        spec = get_competitor("marker")
        assert spec is not None
        assert spec.name == "marker"
        assert spec.display_name == "Marker v2 (marker-pdf)"
        assert spec.pinned_version == "2.0.0"
        assert spec.adapter == "whisker.survey.adapters.marker"

    def test_get_competitor_case_insensitive(self):
        spec = get_competitor("MARKER")
        assert spec is not None
        assert spec.name == "marker"

    def test_get_competitor_unknown(self):
        spec = get_competitor("nonexistent")
        assert spec is None

    def test_get_competitor_tesseract(self):
        spec = get_competitor("tesseract")
        assert spec is not None
        assert spec.name == "tesseract"
        assert spec.display_name == "Tesseract OCR"
        assert spec.pinned_version == "5.5.0"
        assert spec.adapter == "whisker.survey.adapters.tesseract"
        assert spec.patches == []


class TestLockParsing:
    """Lockfile parsing and structure tests."""

    def test_lockfile_loads(self):
        spec = get_competitor("marker")
        assert spec is not None
        lock = load_lockfile(spec)
        assert lock["schema_version"] == 1
        assert lock["competitor"] == "marker"
        assert lock["marker_pdf_version"] == "2.0.0"

    def test_lockfile_llama_cpp(self):
        spec = get_competitor("marker")
        assert spec is not None
        lock = load_lockfile(spec)
        llama = lock["llama_cpp"]
        assert llama["release"] == "b10218"
        assert llama["asset"] == "llama-b10218-bin-win-cpu-x64.zip"
        assert len(llama["zip_sha256"]) == 64
        assert len(llama["binary_sha256"]) == 64

    def test_lockfile_gguf(self):
        spec = get_competitor("marker")
        assert spec is not None
        lock = load_lockfile(spec)
        gguf = lock["gguf"]
        assert gguf["repo"] == "datalab-to/surya-ocr-2-gguf"
        assert len(gguf["revision"]) == 40
        assert len(gguf["files"]) == 2
        for f in gguf["files"]:
            assert f["name"].endswith(".gguf")
            assert len(f["sha256"]) == 64

    def test_tesseract_lockfile(self):
        spec = get_competitor("tesseract")
        assert spec is not None
        lock = load_lockfile(spec)
        assert lock["schema_version"] == 1
        assert lock["competitor"] == "tesseract"
        assert lock["tesseract_version"] == "5.5.0"
        assert len(lock["installer"]["sha256"]) == 64
        assert len(lock["tessdata"]["sha256"]) == 64
        assert lock["artifacts"]
        relpaths = {art["relpath"] for art in lock["artifacts"]}
        assert "tesseract/tesseract.exe" in relpaths
        assert "tesseract/tessdata/eng.traineddata" in relpaths
        for art in lock["artifacts"]:
            assert art["relpath"]
            assert len(art["sha256"]) == 64
        unpacker = lock["unpacker"]
        assert len(unpacker["sevenzr"]["sha256"]) == 64
        assert len(unpacker["sevenzip_sfx"]["sha256"]) == 64
        assert lock["patches"] == []

    def test_lockfile_patches(self):
        spec = get_competitor("marker")
        assert spec is not None
        lock = load_lockfile(spec)
        patches = lock["patches"]
        assert len(patches) == 2
        ids = {p["id"] for p in patches}
        assert "surya-pattern-pcre" in ids
        assert "surya-spawn-signal" in ids


class TestPatchSpecs:
    """PatchSpec presence and structure on the registry entry."""

    def test_marker_has_patches(self):
        spec = get_competitor("marker")
        assert spec is not None
        assert len(spec.patches) == 2

    def test_patch_spec_fields(self):
        spec = get_competitor("marker")
        assert spec is not None
        for patch in spec.patches:
            assert isinstance(patch, PatchSpec)
            assert patch.id
            assert patch.version >= 1
            assert patch.file
            assert patch.description
            assert patch.retire_when

    def test_pattern_patch_details(self):
        spec = get_competitor("marker")
        assert spec is not None
        pat_patch = next(p for p in spec.patches if p.id == "surya-pattern-pcre")
        assert "prompts.py" in pat_patch.file
        assert "llama.cpp" in pat_patch.retire_when

    def test_spawn_patch_details(self):
        spec = get_competitor("marker")
        assert spec is not None
        spawn_patch = next(p for p in spec.patches if p.id == "surya-spawn-signal")
        assert "spawn.py" in spawn_patch.file
        assert "surya" in spawn_patch.retire_when.lower()
