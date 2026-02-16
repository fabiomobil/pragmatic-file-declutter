# Pragmatic File Declutter

[![CI](https://github.com/fabiomobil/pragmatic-file-declutter/actions/workflows/ci.yml/badge.svg)](https://github.com/fabiomobil/pragmatic-file-declutter/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Pragmatic desktop tool for photo & file decluttering with AI.

## What it does

Point it at a folder full of photos and it will:

1. **Find duplicates** — Identical and similar photos detected via perceptual hashing
2. **Classify** — Screenshots, documents, receipts auto-sorted into folders
3. **Organize by event** — Photos clustered by date and visual context into event folders

**Golden rule:** Files are **never deleted** — only moved. Every operation can be undone.

## Tech Stack

- **Python 3.11+** with **NiceGUI** (native desktop look)
- **CLIP** (local, GPU-accelerated) for image understanding
- **Gemini 2.0 Flash** / **GPT-4o mini** for advanced classification
- **Perceptual hashing** for duplicate detection
- **HDBSCAN** for event clustering

## Status

🚧 **Pre-alpha** — Currently building v0.1.0 (scan + deduplication)

## Roadmap

| Version | Feature |
|---------|---------|
| v0.1.0 | Scan + Deduplication |
| v0.2.0 | Classification (screenshots, documents, receipts) |
| v0.3.0 | Event clustering + timeline |
| v0.4.0 | CLIP text→image search |
| v1.0.0 | Stable photo declutter release |
| v2.0.0 | General file declutter |
| v3.0.0 | Android backup connect |
| v4.0.0 | Cloud sync (Google Photos, iCloud) |

## Development

```bash
# Clone
git clone https://github.com/fabiomobil/pragmatic-file-declutter.git
cd pragmatic-file-declutter

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
ruff format src/
```

## License

MIT
