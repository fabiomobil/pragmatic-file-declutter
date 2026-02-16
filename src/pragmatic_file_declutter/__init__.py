"""Pragmatic File Declutter — Pragmatic desktop tool for photo & file decluttering with AI."""

__version__ = "0.0.0"


def main() -> None:
    """Entry point for the application."""
    from nicegui import ui

    ui.label("Pragmatic File Declutter — Coming soon!")
    ui.run(native=True, title="Pragmatic File Declutter", window_size=(1280, 800))
