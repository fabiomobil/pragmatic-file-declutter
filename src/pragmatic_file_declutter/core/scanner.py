"""File scanner for detecting and categorizing files in a directory.

Recursively scans directories to find supported image and video files.
Videos are separated for later move to videos/ folder.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

# Supported image extensions (lowercase, with dot)
IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    # Standard formats (Pillow native)
    ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp", ".gif",
    # HEIC/HEIF (requires pillow-heif)
    ".heic", ".heif",
    # RAW formats (requires rawpy)
    ".cr2", ".cr3",  # Canon
    ".nef",          # Nikon
    ".arw",          # Sony
    ".dng",          # Adobe DNG
    ".orf",          # Olympus
    ".rw2",          # Panasonic
    ".raf",          # Fujifilm
    ".pef",          # Pentax
    ".srw",          # Samsung
})

# Video extensions that will be moved to videos/ folder
VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".3gp",
    ".mts", ".m2ts", ".mpg", ".mpeg", ".vob",
})

# RAW extensions that need special handling
RAW_EXTENSIONS: frozenset[str] = frozenset({
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".raf", ".pef", ".srw",
})

# HEIC extensions that need pillow-heif
HEIC_EXTENSIONS: frozenset[str] = frozenset({
    ".heic", ".heif",
})


@dataclass
class FileInfo:
    """Information about a scanned file.

    Attributes:
        path: Absolute path to the file.
        extension: Lowercase file extension (with dot).
        size_bytes: File size in bytes.
        is_raw: True if file is a RAW format.
        is_heic: True if file is HEIC/HEIF format.
    """

    path: Path
    extension: str
    size_bytes: int
    is_raw: bool = False
    is_heic: bool = False

    @classmethod
    def from_path(cls, path: Path) -> FileInfo:
        """Create FileInfo from a file path.

        Args:
            path: Path to the file.

        Returns:
            FileInfo instance.
        """
        ext = path.suffix.lower()
        return cls(
            path=path.resolve(),
            extension=ext,
            size_bytes=path.stat().st_size,
            is_raw=ext in RAW_EXTENSIONS,
            is_heic=ext in HEIC_EXTENSIONS,
        )


@dataclass
class ScanResult:
    """Result of scanning a directory.

    Attributes:
        images: List of image files found.
        videos: List of video files found.
        corrupted: List of files that failed to load.
        skipped: List of unsupported file types.
        total_size_bytes: Total size of all scanned files.
        scan_path: The root path that was scanned.
    """

    images: list[FileInfo] = field(default_factory=list)
    videos: list[FileInfo] = field(default_factory=list)
    corrupted: list[tuple[Path, str]] = field(default_factory=list)  # (path, error_message)
    skipped: list[Path] = field(default_factory=list)
    total_size_bytes: int = 0
    scan_path: Path | None = None

    @property
    def total_images(self) -> int:
        """Total number of valid images."""
        return len(self.images)

    @property
    def total_videos(self) -> int:
        """Total number of video files."""
        return len(self.videos)

    @property
    def total_corrupted(self) -> int:
        """Total number of corrupted files."""
        return len(self.corrupted)

    @property
    def total_skipped(self) -> int:
        """Total number of skipped files."""
        return len(self.skipped)

    @property
    def total_files(self) -> int:
        """Total files processed (excluding skipped)."""
        return self.total_images + self.total_videos + self.total_corrupted

    def get_format_breakdown(self) -> dict[str, int]:
        """Get count of images by format.

        Returns:
            Dict mapping extension to count.
        """
        breakdown: dict[str, int] = {}
        for img in self.images:
            ext = img.extension
            breakdown[ext] = breakdown.get(ext, 0) + 1
        return breakdown


def _iter_files(root: Path, recursive: bool = True) -> Iterator[Path]:
    """Iterate over all files in a directory.

    Args:
        root: Root directory to scan.
        recursive: If True, scan subdirectories recursively.

    Yields:
        Path objects for each file found.
    """
    if recursive:
        for item in root.rglob("*"):
            if item.is_file():
                yield item
    else:
        for item in root.iterdir():
            if item.is_file():
                yield item


def _is_image_valid(path: Path) -> tuple[bool, str | None]:
    """Check if an image file is valid and can be opened.

    Args:
        path: Path to the image file.

    Returns:
        Tuple of (is_valid, error_message).
        error_message is None if valid.
    """
    ext = path.suffix.lower()

    # For RAW files, we'll validate later with rawpy
    # Just check if file is not empty for now
    if ext in RAW_EXTENSIONS:
        try:
            if path.stat().st_size == 0:
                return False, "Empty RAW file"
            return True, None
        except OSError as e:
            return False, str(e)

    # For HEIC, check with pillow-heif if available
    if ext in HEIC_EXTENSIONS:
        try:
            # Try to import pillow_heif
            import pillow_heif

            pillow_heif.register_heif_opener()
            with Image.open(path) as img:
                img.verify()
            return True, None
        except ImportError:
            # pillow-heif not installed, assume valid
            return True, None
        except Exception as e:
            return False, str(e)

    # Standard formats via Pillow
    try:
        with Image.open(path) as img:
            img.verify()
        return True, None
    except Exception as e:
        return False, str(e)


def scan_directory(
    root: Path,
    *,
    recursive: bool = True,
    validate_images: bool = True,
    skip_hidden: bool = True,
    skip_declutter_folder: bool = True,
) -> ScanResult:
    """Scan a directory for image and video files.

    Args:
        root: Root directory to scan.
        recursive: If True, scan subdirectories recursively.
        validate_images: If True, validate that images can be opened.
        skip_hidden: If True, skip hidden files and directories.
        skip_declutter_folder: If True, skip _pragmatic_declutter folder.

    Returns:
        ScanResult with categorized files.

    Raises:
        ValueError: If root is not a valid directory.
    """
    root = root.resolve()

    if not root.exists():
        raise ValueError(f"Directory does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Path is not a directory: {root}")

    result = ScanResult(scan_path=root)
    declutter_folder = "_pragmatic_declutter"

    for file_path in _iter_files(root, recursive=recursive):
        # Skip hidden files
        if skip_hidden and any(part.startswith(".") for part in file_path.parts):
            continue

        # Skip _pragmatic_declutter folder
        if skip_declutter_folder and declutter_folder in file_path.parts:
            continue

        ext = file_path.suffix.lower()

        # Check if video
        if ext in VIDEO_EXTENSIONS:
            try:
                info = FileInfo.from_path(file_path)
                result.videos.append(info)
                result.total_size_bytes += info.size_bytes
            except OSError as e:
                logger.warning(f"Error reading video file {file_path}: {e}")
                result.corrupted.append((file_path, str(e)))
            continue

        # Check if image
        if ext in IMAGE_EXTENSIONS:
            try:
                info = FileInfo.from_path(file_path)

                # Validate image if requested
                if validate_images:
                    is_valid, error = _is_image_valid(file_path)
                    if not is_valid:
                        result.corrupted.append((file_path, error or "Unknown error"))
                        continue

                result.images.append(info)
                result.total_size_bytes += info.size_bytes
            except OSError as e:
                logger.warning(f"Error reading image file {file_path}: {e}")
                result.corrupted.append((file_path, str(e)))
            continue

        # Skip unsupported file types
        result.skipped.append(file_path)

    # Sort images by path for consistent ordering
    result.images.sort(key=lambda x: x.path)
    result.videos.sort(key=lambda x: x.path)

    return result


def get_output_folder(base_folder: Path) -> Path:
    """Get the path to the _pragmatic_declutter output folder.

    Args:
        base_folder: The base folder where scan was performed.

    Returns:
        Path to _pragmatic_declutter folder.
    """
    return base_folder / "_pragmatic_declutter"


def get_folder_structure(base_folder: Path) -> dict[str, Path]:
    """Get all output folder paths.

    Args:
        base_folder: The base folder where scan was performed.

    Returns:
        Dict mapping folder names to paths.
    """
    output = get_output_folder(base_folder)
    return {
        "root": output,
        "duplicadas": output / "duplicadas",
        "duplicadas_identicas": output / "duplicadas" / "identicas",
        "duplicadas_similares": output / "duplicadas" / "similares",
        "duplicadas_apagar": output / "duplicadas" / "apagar",
        "misc": output / "misc",
        "misc_screenshots": output / "misc" / "screenshots",
        "misc_documents": output / "misc" / "documents",
        "misc_receipts": output / "misc" / "receipts",
        "misc_random": output / "misc" / "random",
        "organize": output / "organize",
        "videos": output / "videos",
        "corrupted": output / "corrupted",
        "no_metadata": output / "no_metadata",
        "reports": output / "_reports",
    }


def create_folder_structure(base_folder: Path) -> dict[str, Path]:
    """Create the output folder structure.

    Args:
        base_folder: The base folder where to create structure.

    Returns:
        Dict mapping folder names to created paths.
    """
    folders = get_folder_structure(base_folder)
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    return folders
