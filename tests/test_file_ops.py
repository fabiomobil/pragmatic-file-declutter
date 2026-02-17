"""Tests for core/file_ops.py — safe file operations with undo capability."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pragmatic_file_declutter.core.file_ops import (
    DestinationExistsError,
    MoveRecord,
    SourceNotFoundError,
    UndoError,
    UndoStack,
    get_default_history_path,
    safe_move,
    undo_all,
    undo_last,
)


class TestMoveRecord:
    """Tests for MoveRecord dataclass."""

    def test_create_sets_timestamp(self, tmp_path: Path) -> None:
        """MoveRecord.create should set current timestamp."""
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        record = MoveRecord.create(src, dst)

        assert record.src == str(src.resolve())
        assert record.dst == str(dst.resolve())
        assert record.operation_type == "move"
        assert record.timestamp  # Should have a timestamp

    def test_immutable(self, tmp_path: Path) -> None:
        """MoveRecord should be immutable (frozen dataclass)."""
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        record = MoveRecord.create(src, dst)

        with pytest.raises(AttributeError):
            record.src = "new_path"  # type: ignore[misc]


class TestUndoStack:
    """Tests for UndoStack class."""

    def test_empty_stack(self, tmp_path: Path) -> None:
        """New stack should be empty."""
        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        assert stack.is_empty()
        assert len(stack) == 0
        assert stack.peek() is None
        assert stack.pop() is None

    def test_push_and_pop(self, tmp_path: Path) -> None:
        """Push and pop should work correctly."""
        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        record = MoveRecord.create(tmp_path / "a.txt", tmp_path / "b.txt")
        stack.push(record)

        assert len(stack) == 1
        assert not stack.is_empty()

        popped = stack.pop()
        assert popped == record
        assert stack.is_empty()

    def test_peek_does_not_remove(self, tmp_path: Path) -> None:
        """Peek should return record without removing it."""
        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        record = MoveRecord.create(tmp_path / "a.txt", tmp_path / "b.txt")
        stack.push(record)

        peeked = stack.peek()
        assert peeked == record
        assert len(stack) == 1

    def test_persistence(self, tmp_path: Path) -> None:
        """Stack should persist to JSON and reload correctly."""
        history_file = tmp_path / "history.json"
        stack1 = UndoStack(history_file)

        record1 = MoveRecord.create(tmp_path / "a.txt", tmp_path / "b.txt")
        record2 = MoveRecord.create(tmp_path / "c.txt", tmp_path / "d.txt")
        stack1.push(record1)
        stack1.push(record2)

        # Create new stack from same file
        stack2 = UndoStack(history_file)

        assert len(stack2) == 2
        assert stack2.pop() == record2
        assert stack2.pop() == record1

    def test_clear(self, tmp_path: Path) -> None:
        """Clear should remove all records."""
        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        stack.push(MoveRecord.create(tmp_path / "a.txt", tmp_path / "b.txt"))
        stack.push(MoveRecord.create(tmp_path / "c.txt", tmp_path / "d.txt"))
        stack.clear()

        assert stack.is_empty()
        assert len(stack) == 0

    def test_iteration(self, tmp_path: Path) -> None:
        """Stack should be iterable from oldest to newest."""
        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        record1 = MoveRecord.create(tmp_path / "a.txt", tmp_path / "b.txt")
        record2 = MoveRecord.create(tmp_path / "c.txt", tmp_path / "d.txt")
        stack.push(record1)
        stack.push(record2)

        records = list(stack)
        assert records == [record1, record2]

    def test_corrupted_json_file(self, tmp_path: Path) -> None:
        """Stack should handle corrupted JSON gracefully."""
        history_file = tmp_path / "history.json"
        history_file.write_text("not valid json", encoding="utf-8")

        stack = UndoStack(history_file)
        assert stack.is_empty()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Stack should create parent directories when saving."""
        history_file = tmp_path / "deep" / "nested" / "history.json"
        stack = UndoStack(history_file)

        record = MoveRecord.create(tmp_path / "a.txt", tmp_path / "b.txt")
        stack.push(record)

        assert history_file.exists()


class TestSafeMove:
    """Tests for safe_move function."""

    def test_successful_move(self, tmp_path: Path) -> None:
        """safe_move should move file and record in undo stack."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("hello", encoding="utf-8")

        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        safe_move(src, dst, stack)

        assert not src.exists()
        assert dst.exists()
        assert dst.read_text(encoding="utf-8") == "hello"
        assert len(stack) == 1

    def test_creates_destination_directories(self, tmp_path: Path) -> None:
        """safe_move should create parent directories for destination."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "deep" / "nested" / "dest.txt"
        src.write_text("hello", encoding="utf-8")

        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        safe_move(src, dst, stack)

        assert dst.exists()

    def test_source_not_found_error(self, tmp_path: Path) -> None:
        """safe_move should raise SourceNotFoundError if source missing."""
        src = tmp_path / "nonexistent.txt"
        dst = tmp_path / "dest.txt"

        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        with pytest.raises(SourceNotFoundError):
            safe_move(src, dst, stack)

        assert len(stack) == 0

    def test_destination_exists_error(self, tmp_path: Path) -> None:
        """safe_move should raise DestinationExistsError if dest exists."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("hello", encoding="utf-8")
        dst.write_text("existing", encoding="utf-8")

        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        with pytest.raises(DestinationExistsError):
            safe_move(src, dst, stack)

        # Source should still exist
        assert src.exists()
        assert len(stack) == 0


class TestUndoLast:
    """Tests for undo_last function."""

    def test_undo_successful(self, tmp_path: Path) -> None:
        """undo_last should move file back to original location."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("hello", encoding="utf-8")

        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        safe_move(src, dst, stack)
        record = undo_last(stack)

        assert record is not None
        assert src.exists()
        assert not dst.exists()
        assert stack.is_empty()

    def test_undo_empty_stack(self, tmp_path: Path) -> None:
        """undo_last should return None for empty stack."""
        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        result = undo_last(stack)
        assert result is None

    def test_undo_moved_file_missing(self, tmp_path: Path) -> None:
        """undo_last should raise UndoError if moved file is missing."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("hello", encoding="utf-8")

        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        safe_move(src, dst, stack)
        dst.unlink()  # Simulate file being deleted externally

        with pytest.raises(UndoError, match="not found"):
            undo_last(stack)

    def test_undo_original_location_occupied(self, tmp_path: Path) -> None:
        """undo_last should raise UndoError if original location occupied."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("hello", encoding="utf-8")

        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        safe_move(src, dst, stack)
        src.write_text("new file", encoding="utf-8")  # Occupy original location

        with pytest.raises(UndoError, match="occupied"):
            undo_last(stack)


class TestUndoAll:
    """Tests for undo_all function."""

    def test_undo_all_successful(self, tmp_path: Path) -> None:
        """undo_all should undo all operations in reverse order."""
        src1 = tmp_path / "source1.txt"
        dst1 = tmp_path / "dest1.txt"
        src2 = tmp_path / "source2.txt"
        dst2 = tmp_path / "dest2.txt"
        src1.write_text("file1", encoding="utf-8")
        src2.write_text("file2", encoding="utf-8")

        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        safe_move(src1, dst1, stack)
        safe_move(src2, dst2, stack)

        undone = undo_all(stack)

        assert len(undone) == 2
        assert src1.exists()
        assert src2.exists()
        assert not dst1.exists()
        assert not dst2.exists()
        assert stack.is_empty()

    def test_undo_all_empty_stack(self, tmp_path: Path) -> None:
        """undo_all should return empty list for empty stack."""
        history_file = tmp_path / "history.json"
        stack = UndoStack(history_file)

        undone = undo_all(stack)
        assert undone == []


class TestGetDefaultHistoryPath:
    """Tests for get_default_history_path function."""

    def test_returns_correct_path(self, tmp_path: Path) -> None:
        """Should return correct path under _pragmatic_declutter/_reports."""
        base = tmp_path / "photos"
        result = get_default_history_path(base)

        expected = base / "_pragmatic_declutter" / "_reports" / "_undo_history.json"
        assert result == expected
