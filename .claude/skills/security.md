# Security Skill — Quick Reference

## Safe Path Pattern (USE EVERYWHERE)
```python
from pathlib import Path

def validate_within_root(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Path escape: {path}")
    return resolved
```

## Safe Filename Pattern
```python
import re
def sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip('. ')
```

## API Response Validation
- Always use Pydantic models to validate API responses
- Never trust raw JSON from Gemini/GPT
- Default to `category="random", confidence=0.0` on parse failure

## UI Rendering
- Always `html.escape()` filenames before rendering in NiceGUI
- Never use `ui.html()` with user-derived content
- Never use `ui.run_javascript()` with dynamic strings

## Environment Variables for Secrets
```python
import os
api_key = os.environ.get("GEMINI_API_KEY")  # ✅
api_key = "AIza..."  # ❌ NEVER
```

## Checklist Before Every PR
1. No path traversal possible?
2. No shell injection possible?
3. No XSS in UI?
4. No hardcoded secrets?
5. No eval/exec?
6. API responses validated?
7. EXIF data sanitized?
