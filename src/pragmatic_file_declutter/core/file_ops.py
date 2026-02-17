"""Safe file operations with undo capability.

This module is the ONLY allowed way to move files in the application.
CRITICAL: Never use os.remove(), os.unlink(), shutil.rmtree(), or Path.unlink().
CRITICAL: Never use shutil.copy() or shutil.copy2() — only MOVE.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


class FileOperationError(Exception):
    """Base exception for file operation errors."""


class SourceNotFoundError(FileOperationError):
    """Raised when source file does not exist."""


class DestinationExistsError(FileOperationError):
    """Raised when destination file already exists."""


class UndoError(FileOperationError):
    """Raised when undo operation fails."""


@dataclass(frozen=True)
class MoveRecord:
    """Immutable record of a file move operation.

    Attributes:
        src: Original file path (before move).
        dst: Destination file path (after move).
        timestamp: When the operation occurred.
        operation_type: Type of operation (always 'move' for now).
    """

    src: str
    dst: str
    timestamp: str
    operation_type: str = "move"

    @classmethod
    def create(cls, src: Path, dst: Path) -> MoveRecord:
        """Create a new MoveRecord with current timestamp.

        Args:
            src: Source file path.
            dst: Destination file path.

        Returns:
            A new MoveRecord instance.
        """
        return cls(
            src=str(src.resolve()),
            dst=str(dst.resolve()),
            timestamp=datetime.now().isoformat(),
            operation_type="move",
        )


class UndoStack:
    """Persistent stack of file operations that can be undone.

    The stack is automatically saved to a JSON file after each operation.
    This ensures undo history survives application restarts.

    Attributes:
        history_file: Path to the JSON file storing the history.
    """

    def __init__(self, history_file: Path) -> None:
        """Initialize the undo stack.

        Args:
            history_file: Path to the JSON file for storing history.
        """
        self.history_file = history_file
        self._records: list[MoveRecord] = []
        self._load()

    def _load(self) -> None:
        """Load history from JSON file if it exists."""
        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text(encoding="utf-8"))
                self._records = [MoveRecord(**record) for record in data]
            except (json.JSONDecodeError, TypeError, KeyError):
                self._records = []

    def _save(self) -> None:
        """Save current history to JSON file."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(record) for record in self._records]
        self.history_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def push(self, record: MoveRecord) -> None:
        """Add a new record to the stack.

        Args:
            record: The move record to add.
        """
        self._records.append(record)
        self._save()

    def pop(self) -> MoveRecord | None:
        """Remove and return the last record from the stack.

        Returns:
            The last MoveRecord, or None if stack is empty.
        """
        if not self._records:
            return None
        record = self._records.pop()
        self._save()
        return record

    def peek(self) -> MoveRecord | None:
        """Return the last record without removing it.

        Returns:
            The last MoveRecord, or None if stack is empty.
        """
        return self._records[-1] if self._records else None

    def __len__(self) -> int:
        """Return the number of records in the stack."""
        return len(self._records)

    def __iter__(self) -> Iterator[MoveRecord]:
        """Iterate over records from oldest to newest."""
        return iter(self._records)

    def is_empty(self) -> bool:
        """Check if the stack is empty.

        Returns:
            True if no records in stack.
        """
        return len(self._records) == 0

    def clear(self) -> None:
        """Clear all records from the stack."""
        self._records.clear()
        self._save()


def safe_move(src: Path, dst: Path, undo_stack: UndoStack) -> None:
    """Safely move a file from src to dst with undo capability.

    This is the ONLY allowed way to move files in the application.
    Every move is logged to the undo stack for later reversal.

    Args:
        src: Source file path (must exist).
        dst: Destination file path (must NOT exist).
        undo_stack: Stack to record the operation for undo.

    Raises:
        SourceNotFoundError: If source file does not exist.
        DestinationExistsError: If destination file already exists.
        FileOperationError: If the move operation fails.
    """
    src = src.resolve()
    dst = dst.resolve()

    if not src.exists():
        raise SourceNotFoundError(f"Source file not found: {src}")

    if dst.exists():
        raise DestinationExistsError(f"Destination already exists: {dst}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(str(src), str(dst))
    except OSError as e:
        raise FileOperationError(f"Failed to move {src} to {dst}: {e}") from e

    record = MoveRecord.create(src, dst)
    undo_stack.push(record)


def undo_last(undo_stack: UndoStack) -> MoveRecord | None:
    """Undo the last file move operation.

    Moves the file back from dst to src.

    Args:
        undo_stack: Stack containing operation history.

    Returns:
        The undone MoveRecord, or None if stack was empty.

    Raises:
        UndoError: If the undo operation fails.
    """
    record = undo_stack.pop()
    if record is None:
        return None

    src = Path(record.src)
    dst = Path(record.dst)

    if not dst.exists():
        raise UndoError(f"Cannot undo: moved file not found at {dst}")

    if src.exists():
        raise UndoError(f"Cannot undo: original location already occupied: {src}")

    src.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(str(dst), str(src))
    except OSError as e:
        undo_stack.push(record)
        raise UndoError(f"Failed to undo move: {e}") from e

    return record


def undo_all(undo_stack: UndoStack) -> list[MoveRecord]:
    """Undo all file move operations in reverse order.

    Args:
        undo_stack: Stack containing operation history.

    Returns:
        List of undone MoveRecords.

    Raises:
        UndoError: If any undo operation fails.
    """
    undone: list[MoveRecord] = []

    while not undo_stack.is_empty():
        record = undo_last(undo_stack)
        if record is not None:
            undone.append(record)

    return undone


def get_default_history_path(base_folder: Path) -> Path:
    """Get the default path for undo history file.

    Args:
        base_folder: The base folder for declutter operations.

    Returns:
        Path to the undo history JSON file.
    """
    return base_folder / "_pragmatic_declutter" / "_reports" / "_undo_history.json"
