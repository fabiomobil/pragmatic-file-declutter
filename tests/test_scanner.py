"""Tests for core/scanner.py — file scanning functionality."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pragmatic_file_declutter.core.scanner import (
    HEIC_EXTENSIONS,
    IMAGE_EXTENSIONS,
    RAW_EXTENSIONS,
    VIDEO_EXTENSIONS,
    FileInfo,
    ScanResult,
    create_folder_structure,
    get_folder_structure,
    get_output_folder,
    scan_directory,
)


class TestConstants:
    """Tests for module constants."""

    def test_image_extensions_are_lowercase(self) -> None:
        """All image extensions should be lowercase with dot."""
        for ext in IMAGE_EXTENSIONS:
            assert ext.startswith(".")
            assert ext == ext.lower()

    def test_video_extensions_are_lowercase(self) -> None:
        """All video extensions should be lowercase with dot."""
        for ext in VIDEO_EXTENSIONS:
            assert ext.startswith(".")
            assert ext == ext.lower()

    def test_raw_extensions_subset_of_image(self) -> None:
        """RAW extensions should be subset of IMAGE_EXTENSIONS."""
        assert RAW_EXTENSIONS.issubset(IMAGE_EXTENSIONS)

    def test_heic_extensions_subset_of_image(self) -> None:
        """HEIC extensions should be subset of IMAGE_EXTENSIONS."""
        assert HEIC_EXTENSIONS.issubset(IMAGE_EXTENSIONS)

    def test_no_overlap_image_video(self) -> None:
        """Image and video extensions should not overlap."""
        overlap = IMAGE_EXTENSIONS & VIDEO_EXTENSIONS
        assert len(overlap) == 0


class TestFileInfo:
    """Tests for FileInfo dataclass."""

    def test_from_path_basic(self, tmp_path: Path) -> None:
        """FileInfo.from_path should extract correct information."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake image data")

        info = FileInfo.from_path(test_file)

        assert info.path == test_file.resolve()
        assert info.extension == ".jpg"
        assert info.size_bytes == len(b"fake image data")
        assert not info.is_raw
        assert not info.is_heic

    def test_from_path_raw(self, tmp_path: Path) -> None:
        """FileInfo should detect RAW files."""
        test_file = tmp_path / "photo.cr2"
        test_file.write_bytes(b"raw data")

        info = FileInfo.from_path(test_file)

        assert info.is_raw
        assert not info.is_heic

    def test_from_path_heic(self, tmp_path: Path) -> None:
        """FileInfo should detect HEIC files."""
        test_file = tmp_path / "photo.heic"
        test_file.write_bytes(b"heic data")

        info = FileInfo.from_path(test_file)

        assert info.is_heic
        assert not info.is_raw

    def test_extension_case_insensitive(self, tmp_path: Path) -> None:
        """Extension should be normalized to lowercase."""
        test_file = tmp_path / "test.JPG"
        test_file.write_bytes(b"data")

        info = FileInfo.from_path(test_file)

        assert info.extension == ".jpg"


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_empty_result(self) -> None:
        """Empty result should have zero counts."""
        result = ScanResult()

        assert result.total_images == 0
        assert result.total_videos == 0
        assert result.total_corrupted == 0
        assert result.total_skipped == 0
        assert result.total_files == 0

    def test_get_format_breakdown(self, tmp_path: Path) -> None:
        """get_format_breakdown should count images by extension."""
        result = ScanResult()

        jpg1 = tmp_path / "a.jpg"
        jpg2 = tmp_path / "b.jpg"
        png1 = tmp_path / "c.png"
        for f in [jpg1, jpg2, png1]:
            f.write_bytes(b"data")

        result.images = [
            FileInfo.from_path(jpg1),
            FileInfo.from_path(jpg2),
            FileInfo.from_path(png1),
        ]

        breakdown = result.get_format_breakdown()

        assert breakdown == {".jpg": 2, ".png": 1}


class TestScanDirectory:
    """Tests for scan_directory function."""

    def test_scan_empty_directory(self, tmp_path: Path) -> None:
        """Scanning empty directory should return empty result."""
        result = scan_directory(tmp_path)

        assert result.total_images == 0
        assert result.total_videos == 0
        assert result.scan_path == tmp_path

    def test_scan_nonexistent_raises(self, tmp_path: Path) -> None:
        """Scanning nonexistent directory should raise ValueError."""
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(ValueError, match="does not exist"):
            scan_directory(nonexistent)

    def test_scan_file_raises(self, tmp_path: Path) -> None:
        """Scanning a file (not directory) should raise ValueError."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        with pytest.raises(ValueError, match="not a directory"):
            scan_directory(file_path)

    def test_scan_finds_images(self, tmp_path: Path) -> None:
        """Scanner should find supported image files."""
        # Create a valid JPEG
        jpg = tmp_path / "photo.jpg"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(jpg)

        png = tmp_path / "image.png"
        img.save(png)

        result = scan_directory(tmp_path)

        assert result.total_images == 2
        extensions = {info.extension for info in result.images}
        assert extensions == {".jpg", ".png"}

    def test_scan_finds_videos(self, tmp_path: Path) -> None:
        """Scanner should find video files."""
        mp4 = tmp_path / "video.mp4"
        mov = tmp_path / "clip.mov"
        mp4.write_bytes(b"fake video")
        mov.write_bytes(b"fake video")

        result = scan_directory(tmp_path)

        assert result.total_videos == 2

    def test_scan_skips_unsupported(self, tmp_path: Path) -> None:
        """Scanner should skip unsupported file types."""
        txt = tmp_path / "readme.txt"
        pdf = tmp_path / "doc.pdf"
        exe = tmp_path / "app.exe"
        for f in [txt, pdf, exe]:
            f.write_bytes(b"data")

        result = scan_directory(tmp_path)

        assert result.total_skipped == 3
        assert result.total_images == 0
        assert result.total_videos == 0

    def test_scan_recursive(self, tmp_path: Path) -> None:
        """Scanner should find files in subdirectories."""
        subdir = tmp_path / "subdir" / "nested"
        subdir.mkdir(parents=True)

        jpg = subdir / "deep.jpg"
        img = Image.new("RGB", (50, 50), color="blue")
        img.save(jpg)

        result = scan_directory(tmp_path, recursive=True)

        assert result.total_images == 1

    def test_scan_non_recursive(self, tmp_path: Path) -> None:
        """Non-recursive scan should only find files in root."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        root_jpg = tmp_path / "root.jpg"
        nested_jpg = subdir / "nested.jpg"

        img = Image.new("RGB", (50, 50))
        img.save(root_jpg)
        img.save(nested_jpg)

        result = scan_directory(tmp_path, recursive=False)

        assert result.total_images == 1
        assert result.images[0].path == root_jpg.resolve()

    def test_scan_skips_hidden_files(self, tmp_path: Path) -> None:
        """Scanner should skip hidden files by default."""
        hidden = tmp_path / ".hidden.jpg"
        visible = tmp_path / "visible.jpg"

        img = Image.new("RGB", (50, 50))
        img.save(hidden)
        img.save(visible)

        result = scan_directory(tmp_path, skip_hidden=True)

        assert result.total_images == 1
        assert result.images[0].path == visible.resolve()

    def test_scan_includes_hidden_when_disabled(self, tmp_path: Path) -> None:
        """Scanner should include hidden files when skip_hidden=False."""
        hidden = tmp_path / ".hidden.jpg"
        visible = tmp_path / "visible.jpg"

        img = Image.new("RGB", (50, 50))
        img.save(hidden)
        img.save(visible)

        result = scan_directory(tmp_path, skip_hidden=False)

        assert result.total_images == 2

    def test_scan_skips_declutter_folder(self, tmp_path: Path) -> None:
        """Scanner should skip _pragmatic_declutter folder."""
        declutter = tmp_path / "_pragmatic_declutter" / "duplicadas"
        declutter.mkdir(parents=True)

        inside = declutter / "dup.jpg"
        outside = tmp_path / "normal.jpg"

        img = Image.new("RGB", (50, 50))
        img.save(inside)
        img.save(outside)

        result = scan_directory(tmp_path, skip_declutter_folder=True)

        assert result.total_images == 1
        assert result.images[0].path == outside.resolve()

    def test_scan_detects_corrupted(self, tmp_path: Path) -> None:
        """Scanner should detect corrupted image files."""
        corrupted = tmp_path / "corrupted.jpg"
        corrupted.write_bytes(b"not a real image")

        valid = tmp_path / "valid.jpg"
        img = Image.new("RGB", (50, 50))
        img.save(valid)

        result = scan_directory(tmp_path, validate_images=True)

        assert result.total_images == 1
        assert result.total_corrupted == 1
        assert result.corrupted[0][0] == corrupted

    def test_scan_skip_validation(self, tmp_path: Path) -> None:
        """Scanner should not validate when validate_images=False."""
        fake = tmp_path / "fake.jpg"
        fake.write_bytes(b"not a real image")

        result = scan_directory(tmp_path, validate_images=False)

        # File should be counted as image (not validated)
        assert result.total_images == 1
        assert result.total_corrupted == 0

    def test_scan_calculates_total_size(self, tmp_path: Path) -> None:
        """Scanner should calculate total size of all files."""
        jpg = tmp_path / "photo.jpg"
        img = Image.new("RGB", (100, 100))
        img.save(jpg)

        mp4 = tmp_path / "video.mp4"
        mp4.write_bytes(b"x" * 1000)

        result = scan_directory(tmp_path)

        jpg_size = jpg.stat().st_size
        mp4_size = 1000
        assert result.total_size_bytes == jpg_size + mp4_size


class TestFolderStructure:
    """Tests for folder structure functions."""

    def test_get_output_folder(self, tmp_path: Path) -> None:
        """get_output_folder should return correct path."""
        result = get_output_folder(tmp_path)
        assert result == tmp_path / "_pragmatic_declutter"

    def test_get_folder_structure(self, tmp_path: Path) -> None:
        """get_folder_structure should return all expected folders."""
        folders = get_folder_structure(tmp_path)

        assert "root" in folders
        assert "duplicadas" in folders
        assert "duplicadas_identicas" in folders
        assert "duplicadas_similares" in folders
        assert "duplicadas_apagar" in folders
        assert "misc" in folders
        assert "misc_screenshots" in folders
        assert "misc_documents" in folders
        assert "misc_receipts" in folders
        assert "misc_random" in folders
        assert "organize" in folders
        assert "videos" in folders
        assert "corrupted" in folders
        assert "no_metadata" in folders
        assert "reports" in folders

    def test_create_folder_structure(self, tmp_path: Path) -> None:
        """create_folder_structure should create all folders."""
        folders = create_folder_structure(tmp_path)

        for name, path in folders.items():
            assert path.exists(), f"Folder {name} was not created"
            assert path.is_dir(), f"Folder {name} is not a directory"

    def test_create_folder_structure_idempotent(self, tmp_path: Path) -> None:
        """create_folder_structure should be idempotent."""
        create_folder_structure(tmp_path)
        create_folder_structure(tmp_path)  # Should not raise

        folders = get_folder_structure(tmp_path)
        for path in folders.values():
            assert path.exists()
