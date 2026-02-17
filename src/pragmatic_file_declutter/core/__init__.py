"""Core business logic for Pragmatic File Declutter."""

from pragmatic_file_declutter.core.file_ops import (
    DestinationExistsError,
    FileOperationError,
    MoveRecord,
    SecurityError,
    SourceNotFoundError,
    UndoError,
    UndoStack,
    get_default_history_path,
    safe_move,
    undo_all,
    undo_last,
)
from pragmatic_file_declutter.core.scanner import (
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

__all__ = [
    # file_ops
    "DestinationExistsError",
    "FileOperationError",
    "MoveRecord",
    "SecurityError",
    "SourceNotFoundError",
    "UndoError",
    "UndoStack",
    "get_default_history_path",
    "safe_move",
    "undo_all",
    "undo_last",
    # scanner
    "IMAGE_EXTENSIONS",
    "RAW_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "FileInfo",
    "ScanResult",
    "create_folder_structure",
    "get_folder_structure",
    "get_output_folder",
    "scan_directory",
    # dedup
    "THRESHOLD_IDENTICAL",
    "THRESHOLD_SIMILAR",
    "BKTree",
    "DeduplicationResult",
    "DuplicateGroup",
    "ImageHash",
    "compute_hash",
    "compute_hashes",
    "deduplicate",
    "find_duplicates",
]
