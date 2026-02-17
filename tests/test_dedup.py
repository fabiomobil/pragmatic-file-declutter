"""Tests for core/dedup.py — image deduplication functionality."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pragmatic_file_declutter.core.dedup import (
    THRESHOLD_IDENTICAL,
    THRESHOLD_SIMILAR,
    BKTree,
    DeduplicationResult,
    DuplicateGroup,
    ImageHash,
    compute_hash,
    compute_hashes,
    deduplicate,
    find_duplicates,
)
from pragmatic_file_declutter.core.scanner import FileInfo


class TestImageHash:
    """Tests for ImageHash dataclass."""

    def test_hamming_distance_identical(self) -> None:
        """Identical hashes should have distance 0."""
        h1 = ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("a.jpg"))
        h2 = ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("b.jpg"))

        assert h1.hamming_distance(h2) == 0

    def test_hamming_distance_different(self) -> None:
        """Different hashes should have positive distance."""
        h1 = ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("a.jpg"))
        h2 = ImageHash(phash="ffffffffffffffff", dhash="ffffffffffffffff", path=Path("b.jpg"))

        # All bits different = 64 bits per hash, average = 64
        assert h1.hamming_distance(h2) == 64

    def test_hamming_distance_partial(self) -> None:
        """Partially different hashes should have intermediate distance."""
        # 1 = 0001 in binary = 1 bit different
        h1 = ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("a.jpg"))
        h2 = ImageHash(phash="0000000000000001", dhash="0000000000000001", path=Path("b.jpg"))

        # 1 bit different in each hash, average = 1
        assert h1.hamming_distance(h2) == 1

    def test_frozen_dataclass(self) -> None:
        """ImageHash should be immutable."""
        h = ImageHash(phash="0000", dhash="0000", path=Path("a.jpg"))

        with pytest.raises(AttributeError):
            h.phash = "1111"  # type: ignore[misc]


class TestDuplicateGroup:
    """Tests for DuplicateGroup dataclass."""

    def test_all_images(self) -> None:
        """all_images should return original + duplicates."""
        orig = ImageHash(phash="0000", dhash="0000", path=Path("orig.jpg"))
        dup1 = ImageHash(phash="0001", dhash="0001", path=Path("dup1.jpg"))
        dup2 = ImageHash(phash="0002", dhash="0002", path=Path("dup2.jpg"))

        group = DuplicateGroup(original=orig, duplicates=[dup1, dup2])

        assert group.all_images == [orig, dup1, dup2]

    def test_size(self) -> None:
        """size should return total count."""
        orig = ImageHash(phash="0000", dhash="0000", path=Path("orig.jpg"))
        dup = ImageHash(phash="0001", dhash="0001", path=Path("dup.jpg"))

        group = DuplicateGroup(original=orig, duplicates=[dup])

        assert group.size == 2


class TestBKTree:
    """Tests for BKTree class."""

    def test_empty_tree(self) -> None:
        """Empty tree should have length 0."""
        tree = BKTree()
        assert len(tree) == 0

    def test_add_single(self) -> None:
        """Adding one item should work."""
        tree = BKTree()
        h = ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("a.jpg"))
        tree.add(h)

        assert len(tree) == 1

    def test_add_multiple(self) -> None:
        """Adding multiple items should work."""
        tree = BKTree()

        for i in range(10):
            h = ImageHash(phash=f"{i:016x}", dhash=f"{i:016x}", path=Path(f"{i}.jpg"))
            tree.add(h)

        assert len(tree) == 10

    def test_find_within_exact(self) -> None:
        """find_within should find exact matches."""
        tree = BKTree()
        h1 = ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("a.jpg"))
        h2 = ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("b.jpg"))
        tree.add(h1)
        tree.add(h2)

        results = tree.find_within(h1, threshold=0)

        assert len(results) == 2
        paths = {r[0].path for r in results}
        assert paths == {Path("a.jpg"), Path("b.jpg")}

    def test_find_within_threshold(self) -> None:
        """find_within should respect threshold."""
        tree = BKTree()
        h1 = ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("a.jpg"))
        h2 = ImageHash(phash="0000000000000001", dhash="0000000000000001", path=Path("b.jpg"))  # distance 1
        h3 = ImageHash(phash="ffffffffffffffff", dhash="ffffffffffffffff", path=Path("c.jpg"))  # distance 64
        tree.add(h1)
        tree.add(h2)
        tree.add(h3)

        results = tree.find_within(h1, threshold=5)

        assert len(results) == 2
        paths = {r[0].path for r in results}
        assert paths == {Path("a.jpg"), Path("b.jpg")}

    def test_iteration(self) -> None:
        """Tree should be iterable."""
        tree = BKTree()
        hashes = [
            ImageHash(phash=f"{i:016x}", dhash=f"{i:016x}", path=Path(f"{i}.jpg"))
            for i in range(5)
        ]
        for h in hashes:
            tree.add(h)

        result = list(tree)
        assert len(result) == 5


class TestComputeHash:
    """Tests for compute_hash function."""

    def test_compute_hash_valid_image(self, tmp_path: Path) -> None:
        """compute_hash should work on valid images."""
        img_path = tmp_path / "test.jpg"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_path)

        result = compute_hash(img_path)

        assert result.path == img_path.resolve()
        assert len(result.phash) == 16  # 64-bit hash as hex
        assert len(result.dhash) == 16

    def test_compute_hash_rgba(self, tmp_path: Path) -> None:
        """compute_hash should handle RGBA images."""
        img_path = tmp_path / "test.png"
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        img.save(img_path)

        result = compute_hash(img_path)

        assert result.path == img_path.resolve()

    def test_compute_hash_grayscale(self, tmp_path: Path) -> None:
        """compute_hash should handle grayscale images."""
        img_path = tmp_path / "test.png"
        img = Image.new("L", (100, 100), color=128)
        img.save(img_path)

        result = compute_hash(img_path)

        assert result.path == img_path.resolve()

    def test_compute_hash_invalid_raises(self, tmp_path: Path) -> None:
        """compute_hash should raise on invalid images."""
        bad_path = tmp_path / "bad.jpg"
        bad_path.write_bytes(b"not an image")

        with pytest.raises(ValueError, match="Failed to hash"):
            compute_hash(bad_path)

    def test_identical_images_same_hash(self, tmp_path: Path) -> None:
        """Identical images should produce same hash."""
        img = Image.new("RGB", (100, 100), color="blue")

        path1 = tmp_path / "img1.jpg"
        path2 = tmp_path / "img2.jpg"
        img.save(path1)
        img.save(path2)

        h1 = compute_hash(path1)
        h2 = compute_hash(path2)

        assert h1.phash == h2.phash
        assert h1.dhash == h2.dhash
        assert h1.hamming_distance(h2) == 0

    def test_different_images_different_hash(self, tmp_path: Path) -> None:
        """Different images should produce different hashes."""
        # Use images with actual patterns, not solid colors
        img1 = Image.new("RGB", (100, 100))
        img2 = Image.new("RGB", (100, 100))

        # Create distinct patterns
        for x in range(100):
            for y in range(100):
                img1.putpixel((x, y), (x * 2 % 256, y * 2 % 256, 0))
                img2.putpixel((x, y), (0, x * 2 % 256, y * 2 % 256))

        path1 = tmp_path / "pattern1.jpg"
        path2 = tmp_path / "pattern2.jpg"
        img1.save(path1)
        img2.save(path2)

        h1 = compute_hash(path1)
        h2 = compute_hash(path2)

        assert h1.hamming_distance(h2) > 0


class TestComputeHashes:
    """Tests for compute_hashes function."""

    def test_compute_hashes_batch(self, tmp_path: Path) -> None:
        """compute_hashes should process multiple images."""
        images = []
        for i in range(3):
            path = tmp_path / f"img{i}.jpg"
            img = Image.new("RGB", (50, 50), color=(i * 50, 0, 0))
            img.save(path)
            images.append(FileInfo.from_path(path))

        hashes, failed = compute_hashes(images)

        assert len(hashes) == 3
        assert len(failed) == 0

    def test_compute_hashes_with_failures(self, tmp_path: Path) -> None:
        """compute_hashes should handle failures gracefully."""
        good = tmp_path / "good.jpg"
        bad = tmp_path / "bad.jpg"

        img = Image.new("RGB", (50, 50))
        img.save(good)
        bad.write_bytes(b"not an image")

        images = [FileInfo.from_path(good), FileInfo.from_path(bad)]
        hashes, failed = compute_hashes(images)

        assert len(hashes) == 1
        assert len(failed) == 1
        assert failed[0][0] == bad

    def test_compute_hashes_progress(self, tmp_path: Path) -> None:
        """compute_hashes should call progress callback."""
        path = tmp_path / "img.jpg"
        img = Image.new("RGB", (50, 50))
        img.save(path)

        progress_calls: list[tuple[int, int]] = []

        def on_progress(current: int, total: int) -> None:
            progress_calls.append((current, total))

        compute_hashes([FileInfo.from_path(path)], on_progress=on_progress)

        assert progress_calls == [(1, 1)]


class TestFindDuplicates:
    """Tests for find_duplicates function."""

    def test_no_duplicates(self, tmp_path: Path) -> None:
        """find_duplicates should return empty for unique images."""
        hashes = [
            ImageHash(phash=f"{i:016x}", dhash=f"{i:016x}", path=tmp_path / f"{i}.jpg")
            for i in [0, 0xffff, 0xffff0000]  # Very different hashes
        ]

        identical, similar = find_duplicates(hashes)

        assert len(identical) == 0
        assert len(similar) == 0

    def test_identical_duplicates(self) -> None:
        """find_duplicates should find identical images."""
        hashes = [
            ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("a.jpg")),
            ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("b.jpg")),
            ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("c.jpg")),
        ]

        identical, similar = find_duplicates(hashes)

        assert len(identical) == 1
        assert identical[0].size == 3
        assert identical[0].similarity == "identical"
        assert len(similar) == 0

    def test_similar_duplicates(self) -> None:
        """find_duplicates should find similar images."""
        # Create hashes with distance ~7 (similar but not identical)
        hashes = [
            ImageHash(phash="0000000000000000", dhash="0000000000000000", path=Path("a.jpg")),
            ImageHash(phash="00000000000000ff", dhash="00000000000000ff", path=Path("b.jpg")),  # 8 bits diff
        ]

        identical, similar = find_duplicates(hashes)

        assert len(identical) == 0
        assert len(similar) == 1
        assert similar[0].similarity == "similar"

    def test_empty_input(self) -> None:
        """find_duplicates should handle empty input."""
        identical, similar = find_duplicates([])

        assert identical == []
        assert similar == []

    def test_single_image(self) -> None:
        """find_duplicates should handle single image."""
        hashes = [ImageHash(phash="0000", dhash="0000", path=Path("a.jpg"))]

        identical, similar = find_duplicates(hashes)

        assert identical == []
        assert similar == []


class TestDeduplicationResult:
    """Tests for DeduplicationResult dataclass."""

    def test_empty_result(self) -> None:
        """Empty result should have zero counts."""
        result = DeduplicationResult()

        assert result.total_identical == 0
        assert result.total_similar == 0
        assert result.total_duplicates == 0
        assert result.total_unique == 0

    def test_counts(self) -> None:
        """Result should calculate correct counts."""
        result = DeduplicationResult(
            identical_groups=[
                DuplicateGroup(
                    original=ImageHash(phash="0", dhash="0", path=Path("a.jpg")),
                    duplicates=[
                        ImageHash(phash="0", dhash="0", path=Path("b.jpg")),
                        ImageHash(phash="0", dhash="0", path=Path("c.jpg")),
                    ],
                ),
            ],
            similar_groups=[
                DuplicateGroup(
                    original=ImageHash(phash="1", dhash="1", path=Path("d.jpg")),
                    duplicates=[
                        ImageHash(phash="1", dhash="1", path=Path("e.jpg")),
                    ],
                ),
            ],
            unique_images=[
                ImageHash(phash="f", dhash="f", path=Path("f.jpg")),
            ],
        )

        assert result.total_identical == 2
        assert result.total_similar == 1
        assert result.total_duplicates == 3
        assert result.total_unique == 1


class TestDeduplicate:
    """Tests for deduplicate function."""

    def test_full_pipeline(self, tmp_path: Path) -> None:
        """deduplicate should run full pipeline."""
        # Create 2 identical images with a pattern
        img_same = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                img_same.putpixel((x, y), (x * 2 % 256, y * 2 % 256, 0))

        # Create a different image with distinct pattern
        img_diff = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                img_diff.putpixel((x, y), (0, 255 - x * 2 % 256, 255 - y * 2 % 256))

        path1 = tmp_path / "same1.jpg"
        path2 = tmp_path / "same2.jpg"
        path3 = tmp_path / "diff.jpg"

        img_same.save(path1)
        img_same.save(path2)
        img_diff.save(path3)

        file_infos = [
            FileInfo.from_path(path1),
            FileInfo.from_path(path2),
            FileInfo.from_path(path3),
        ]

        result = deduplicate(file_infos)

        assert result.total_scanned == 3
        assert result.total_identical == 1  # 1 duplicate (not counting original)
        assert len(result.unique_images) == 1

    def test_empty_input(self) -> None:
        """deduplicate should handle empty input."""
        result = deduplicate([])

        assert result.total_scanned == 0
        assert result.total_duplicates == 0

    def test_single_image(self, tmp_path: Path) -> None:
        """deduplicate should handle single image."""
        path = tmp_path / "single.jpg"
        img = Image.new("RGB", (50, 50))
        img.save(path)

        result = deduplicate([FileInfo.from_path(path)])

        assert result.total_scanned == 1
        assert result.total_duplicates == 0

    def test_progress_callback(self, tmp_path: Path) -> None:
        """deduplicate should call progress callback."""
        # Need at least 2 images to trigger full pipeline
        path1 = tmp_path / "img1.jpg"
        path2 = tmp_path / "img2.jpg"
        img = Image.new("RGB", (50, 50))
        img.save(path1)
        img.save(path2)

        progress_calls: list[tuple[str, int, int]] = []

        def on_progress(stage: str, current: int, total: int) -> None:
            progress_calls.append((stage, current, total))

        deduplicate([FileInfo.from_path(path1), FileInfo.from_path(path2)], on_progress=on_progress)

        # Should have at least hashing stage
        stages = [call[0] for call in progress_calls]
        assert "hashing" in stages
