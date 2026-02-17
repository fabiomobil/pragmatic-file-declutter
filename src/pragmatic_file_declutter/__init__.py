"""Pragmatic File Declutter — Pragmatic desktop tool for photo & file decluttering with AI."""

__version__ = "0.0.0"


def main() -> None:
    """Entry point for the application."""
    from pragmatic_file_declutter.ui.app import run

    run(native=True, reload=False)
