"""Image deduplication using perceptual hashing.

Uses pHash (DCT-based) and dHash (gradient-based) for robust duplicate detection.
BK-tree is used to optimize comparisons from O(n²) to ~O(n log n).

Thresholds:
- 0-5: Identical (exact or near-exact duplicates)
- 6-10: Similar (resized, slight edits)
- >10: Different images
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import imagehash
from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pragmatic_file_declutter.core.scanner import FileInfo

logger = logging.getLogger(__name__)

# Thresholds for duplicate detection (Hamming distance)
THRESHOLD_IDENTICAL = 5   # 0-5: identical
THRESHOLD_SIMILAR = 15    # 6-15: similar


@dataclass(frozen=True)
class ImageHash:
    """Combined perceptual hash of an image.

    Uses both pHash (DCT-based) and dHash (gradient-based) for better accuracy.

    Attributes:
        phash: Perceptual hash (DCT-based).
        dhash: Difference hash (gradient-based).
        path: Path to the image file.
    """

    phash: str
    dhash: str
    path: Path

    def hamming_distance(self, other: ImageHash) -> int:
        """Calculate combined Hamming distance to another hash.

        Uses the average of pHash and dHash distances for more robust comparison.

        Args:
            other: Another ImageHash to compare with.

        Returns:
            Combined Hamming distance (average of phash and dhash distances).
        """
        phash_dist = self._hex_hamming(self.phash, other.phash)
        dhash_dist = self._hex_hamming(self.dhash, other.dhash)
        return (phash_dist + dhash_dist) // 2

    @staticmethod
    def _hex_hamming(h1: str, h2: str) -> int:
        """Calculate Hamming distance between two hex strings.

        Args:
            h1: First hex string.
            h2: Second hex string.

        Returns:
            Number of differing bits.
        """
        # Convert hex to int and XOR
        val1 = int(h1, 16)
        val2 = int(h2, 16)
        xor = val1 ^ val2
        # Count set bits
        return bin(xor).count("1")


@dataclass
class DuplicateGroup:
    """A group of duplicate images.

    Attributes:
        original: The "best" image (kept as original).
        duplicates: List of duplicate images.
        similarity: Similarity level ('identical' or 'similar').
        avg_distance: Average Hamming distance within the group.
    """

    original: ImageHash
    duplicates: list[ImageHash] = field(default_factory=list)
    similarity: str = "identical"
    avg_distance: float = 0.0

    @property
    def all_images(self) -> list[ImageHash]:
        """Return all images in the group (original + duplicates)."""
        return [self.original, *self.duplicates]

    @property
    def size(self) -> int:
        """Total number of images in the group."""
        return 1 + len(self.duplicates)


class BKTree:
    """BK-tree for efficient nearest-neighbor search by Hamming distance.

    A BK-tree organizes items by their distance metric, allowing efficient
    range queries. For duplicate detection, this reduces comparisons from
    O(n²) to approximately O(n log n).
    """

    def __init__(self) -> None:
        """Initialize an empty BK-tree."""
        self._root: tuple[ImageHash, dict[int, BKTree]] | None = None
        self._size = 0

    def add(self, item: ImageHash) -> None:
        """Add an item to the tree.

        Args:
            item: ImageHash to add.
        """
        if self._root is None:
            self._root = (item, {})
            self._size = 1
            return

        node_hash, children = self._root
        distance = node_hash.hamming_distance(item)

        if distance in children:
            children[distance].add(item)
        else:
            subtree = BKTree()
            subtree._root = (item, {})
            subtree._size = 1
            children[distance] = subtree

        self._size += 1

    def find_within(self, query: ImageHash, threshold: int) -> list[tuple[ImageHash, int]]:
        """Find all items within a given Hamming distance.

        Args:
            query: The ImageHash to search for.
            threshold: Maximum Hamming distance.

        Returns:
            List of (ImageHash, distance) tuples within threshold.
        """
        results: list[tuple[ImageHash, int]] = []
        self._search(query, threshold, results)
        return results

    def _search(
        self,
        query: ImageHash,
        threshold: int,
        results: list[tuple[ImageHash, int]],
    ) -> None:
        """Recursive search helper.

        Args:
            query: The ImageHash to search for.
            threshold: Maximum Hamming distance.
            results: List to append results to.
        """
        if self._root is None:
            return

        node_hash, children = self._root
        distance = node_hash.hamming_distance(query)

        if distance <= threshold:
            results.append((node_hash, distance))

        # Only search children whose distance could be within threshold
        min_dist = max(0, distance - threshold)
        max_dist = distance + threshold

        for child_dist, subtree in children.items():
            if min_dist <= child_dist <= max_dist:
                subtree._search(query, threshold, results)

    def __len__(self) -> int:
        """Return the number of items in the tree."""
        return self._size

    def __iter__(self) -> Iterator[ImageHash]:
        """Iterate over all items in the tree."""
        if self._root is None:
            return

        node_hash, children = self._root
        yield node_hash

        for subtree in children.values():
            yield from subtree


def compute_hash(image_path: Path) -> ImageHash:
    """Compute perceptual hash for an image.

    Args:
        image_path: Path to the image file.

    Returns:
        ImageHash containing both pHash and dHash.

    Raises:
        ValueError: If the image cannot be opened or hashed.
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if needed (handles RGBA, grayscale, etc.)
            if img.mode != "RGB":
                img = img.convert("RGB")

            phash = imagehash.phash(img)
            dhash = imagehash.dhash(img)

            return ImageHash(
                phash=str(phash),
                dhash=str(dhash),
                path=image_path.resolve(),
            )
    except Exception as e:
        raise ValueError(f"Failed to hash image {image_path}: {e}") from e


def compute_hashes(
    file_infos: list[FileInfo],
    *,
    on_progress: None | (callable[[int, int], None]) = None,
) -> tuple[list[ImageHash], list[tuple[Path, str]]]:
    """Compute hashes for a list of images.

    Args:
        file_infos: List of FileInfo objects to hash.
        on_progress: Optional callback(current, total) for progress updates.

    Returns:
        Tuple of (successful_hashes, failed_items).
        failed_items is list of (path, error_message).
    """
    hashes: list[ImageHash] = []
    failed: list[tuple[Path, str]] = []
    total = len(file_infos)

    for i, info in enumerate(file_infos):
        try:
            hash_obj = compute_hash(info.path)
            hashes.append(hash_obj)
        except ValueError as e:
            logger.warning(f"Failed to hash {info.path}: {e}")
            failed.append((info.path, str(e)))

        if on_progress:
            on_progress(i + 1, total)

    return hashes, failed


class UnionFind:
    """Union-Find data structure for grouping similar images transitively."""

    def __init__(self) -> None:
        """Initialize empty Union-Find."""
        self._parent: dict[Path, Path] = {}
        self._rank: dict[Path, int] = {}

    def find(self, x: Path) -> Path:
        """Find root of x with path compression."""
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])
        return self._parent[x]

    def union(self, x: Path, y: Path) -> None:
        """Union two sets by rank."""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self._rank[rx] < self._rank[ry]:
            rx, ry = ry, rx
        self._parent[ry] = rx
        if self._rank[rx] == self._rank[ry]:
            self._rank[rx] += 1


def find_duplicates(
    hashes: list[ImageHash],
    *,
    identical_threshold: int = THRESHOLD_IDENTICAL,
    similar_threshold: int = THRESHOLD_SIMILAR,
) -> tuple[list[DuplicateGroup], list[DuplicateGroup]]:
    """Find duplicate images using BK-tree and Union-Find for transitive grouping.

    Args:
        hashes: List of ImageHash objects to compare.
        identical_threshold: Max distance for identical duplicates (default 5).
        similar_threshold: Max distance for similar duplicates (default 10).

    Returns:
        Tuple of (identical_groups, similar_groups).
    """
    if len(hashes) < 2:
        return [], []

    # Build BK-tree and hash lookup
    tree = BKTree()
    hash_by_path: dict[Path, ImageHash] = {}
    for h in hashes:
        tree.add(h)
        hash_by_path[h.path] = h

    # Use Union-Find to group transitively
    uf_identical = UnionFind()
    uf_similar = UnionFind()

    # Track distances for each pair
    distances: dict[tuple[Path, Path], int] = {}

    # Find all pairs and union them
    for img_hash in hashes:
        matches = tree.find_within(img_hash, similar_threshold)

        for other, dist in matches:
            if other.path == img_hash.path:
                continue

            # Store distance (use sorted tuple for consistency)
            pair = tuple(sorted([img_hash.path, other.path], key=str))
            distances[pair] = dist  # type: ignore[index]

            if dist <= identical_threshold:
                uf_identical.union(img_hash.path, other.path)
            elif dist <= similar_threshold:
                uf_similar.union(img_hash.path, other.path)

    # Build groups from Union-Find
    identical_groups: list[DuplicateGroup] = []
    similar_groups: list[DuplicateGroup] = []

    # Collect identical groups
    identical_roots: dict[Path, list[ImageHash]] = {}
    for h in hashes:
        root = uf_identical.find(h.path)
        if root != h.path or any(uf_identical.find(other.path) == root for other in hashes if other.path != h.path):
            if root not in identical_roots:
                identical_roots[root] = []
            identical_roots[root].append(h)

    for root, members in identical_roots.items():
        if len(members) < 2:
            continue

        # Sort by file size (largest first = original)
        members.sort(key=lambda h: h.path.stat().st_size if h.path.exists() else 0, reverse=True)

        # Calculate average distance
        total_dist = 0
        count = 0
        for i, m1 in enumerate(members):
            for m2 in members[i + 1:]:
                pair = tuple(sorted([m1.path, m2.path], key=str))
                if pair in distances:
                    total_dist += distances[pair]  # type: ignore[index]
                    count += 1

        avg_dist = total_dist / count if count > 0 else 0

        group = DuplicateGroup(
            original=members[0],
            duplicates=members[1:],
            similarity="identical",
            avg_distance=avg_dist,
        )
        identical_groups.append(group)

    # Collect similar groups (exclude those already in identical)
    assigned_to_identical = {h.path for g in identical_groups for h in g.all_images}

    similar_roots: dict[Path, list[ImageHash]] = {}
    for h in hashes:
        if h.path in assigned_to_identical:
            continue
        root = uf_similar.find(h.path)
        if root != h.path or any(
            uf_similar.find(other.path) == root
            for other in hashes
            if other.path != h.path and other.path not in assigned_to_identical
        ):
            if root not in similar_roots:
                similar_roots[root] = []
            similar_roots[root].append(h)

    for root, members in similar_roots.items():
        if len(members) < 2:
            continue

        members.sort(key=lambda h: h.path.stat().st_size if h.path.exists() else 0, reverse=True)

        total_dist = 0
        count = 0
        for i, m1 in enumerate(members):
            for m2 in members[i + 1:]:
                pair = tuple(sorted([m1.path, m2.path], key=str))
                if pair in distances:
                    total_dist += distances[pair]  # type: ignore[index]
                    count += 1

        avg_dist = total_dist / count if count > 0 else 0

        group = DuplicateGroup(
            original=members[0],
            duplicates=members[1:],
            similarity="similar",
            avg_distance=avg_dist,
        )
        similar_groups.append(group)

    return identical_groups, similar_groups


@dataclass
class DeduplicationResult:
    """Result of running deduplication on a set of images.

    Attributes:
        identical_groups: Groups of identical duplicates.
        similar_groups: Groups of similar duplicates.
        unique_images: Images with no duplicates.
        failed_hashes: Images that failed to hash.
        total_scanned: Total number of images scanned.
    """

    identical_groups: list[DuplicateGroup] = field(default_factory=list)
    similar_groups: list[DuplicateGroup] = field(default_factory=list)
    unique_images: list[ImageHash] = field(default_factory=list)
    failed_hashes: list[tuple[Path, str]] = field(default_factory=list)
    total_scanned: int = 0

    @property
    def total_identical(self) -> int:
        """Total number of identical duplicate images (excluding originals)."""
        return sum(len(g.duplicates) for g in self.identical_groups)

    @property
    def total_similar(self) -> int:
        """Total number of similar duplicate images (excluding originals)."""
        return sum(len(g.duplicates) for g in self.similar_groups)

    @property
    def total_duplicates(self) -> int:
        """Total number of duplicate images found."""
        return self.total_identical + self.total_similar

    @property
    def total_unique(self) -> int:
        """Total number of unique images."""
        return len(self.unique_images)

    @property
    def space_recoverable(self) -> int:
        """Estimated bytes recoverable by removing duplicates.

        Note: This is approximate since we use the first duplicate's size.
        """
        total = 0
        for group in self.identical_groups:
            for dup in group.duplicates:
                try:
                    total += dup.path.stat().st_size
                except OSError:
                    pass
        return total


def deduplicate(
    file_infos: list[FileInfo],
    *,
    identical_threshold: int = THRESHOLD_IDENTICAL,
    similar_threshold: int = THRESHOLD_SIMILAR,
    on_progress: None | (callable[[str, int, int], None]) = None,
) -> DeduplicationResult:
    """Run full deduplication pipeline on a list of images.

    Args:
        file_infos: List of FileInfo objects to deduplicate.
        identical_threshold: Max distance for identical duplicates.
        similar_threshold: Max distance for similar duplicates.
        on_progress: Optional callback(stage, current, total) for progress.
            Stages: "hashing", "comparing"

    Returns:
        DeduplicationResult with all duplicate groups and statistics.
    """
    result = DeduplicationResult(total_scanned=len(file_infos))

    if len(file_infos) < 2:
        return result

    # Stage 1: Compute hashes
    def hash_progress(current: int, total: int) -> None:
        if on_progress:
            on_progress("hashing", current, total)

    hashes, failed = compute_hashes(file_infos, on_progress=hash_progress)
    result.failed_hashes = failed

    if len(hashes) < 2:
        result.unique_images = hashes
        return result

    # Stage 2: Find duplicates
    if on_progress:
        on_progress("comparing", 0, len(hashes))

    identical, similar = find_duplicates(
        hashes,
        identical_threshold=identical_threshold,
        similar_threshold=similar_threshold,
    )

    result.identical_groups = identical
    result.similar_groups = similar

    # Find unique images (not in any group)
    assigned: set[Path] = set()
    for group in identical + similar:
        assigned.add(group.original.path)
        for dup in group.duplicates:
            assigned.add(dup.path)

    result.unique_images = [h for h in hashes if h.path not in assigned]

    if on_progress:
        on_progress("comparing", len(hashes), len(hashes))

    return result
