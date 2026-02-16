# Skill: File Safety

## ABSOLUTE RULES
1. **NEVER delete files** — no `os.remove()`, `os.unlink()`, `shutil.rmtree()`, `Path.unlink()`
2. **NEVER copy files** — no `shutil.copy()`, `shutil.copy2()`, `shutil.copytree()`
3. **ONLY move files** — `shutil.move()` is the ONLY allowed file operation
4. **ALWAYS log to undo stack** before any move
5. **ALWAYS verify** source exists AND destination doesn't exist

## Safe Move Pattern
```python
import shutil
from pathlib import Path
from datetime import datetime

def safe_move(src: Path, dst: Path, undo_stack: UndoStack) -> None:
    """Move a file safely with undo support."""
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {src}")
    if dst.exists():
        raise FileExistsError(f"Destination already exists: {dst}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    undo_stack.push(MoveRecord(src=src, dst=dst, timestamp=datetime.now()))
```

## Undo Stack
- Stored as JSON at `_pragmatic_declutter/_undo_history.json`
- Each entry: `{"src": "...", "dst": "...", "timestamp": "...", "operation": "move"}`
- Undo reverses the move: `shutil.move(dst, src)`
- Stack persists between sessions

## Grep for Violations
If reviewing code, search for these forbidden patterns:
- `os.remove`, `os.unlink`, `Path.unlink`, `shutil.rmtree`
- `shutil.copy`, `shutil.copy2`, `shutil.copytree`
