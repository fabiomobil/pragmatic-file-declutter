"""Main application entry point for NiceGUI desktop app."""

from __future__ import annotations

from nicegui import app, ui

from pragmatic_file_declutter.ui.pages.select_folder import create_page


def run(*, native: bool = True, reload: bool = False) -> None:
    """Run the Pragmatic File Declutter application.

    Args:
        native: If True, run as native desktop app (pywebview).
        reload: If True, enable hot reload for development.
    """
    # Configure app
    app.native.window_args["resizable"] = True
    app.native.start_args["debug"] = reload

    @ui.page("/")
    def index() -> None:
        """Main page."""
        ui.colors(primary="#4F46E5")  # Indigo
        create_page()

    ui.run(
        title="Pragmatic File Declutter",
        native=native,
        reload=reload,
        window_size=(1024, 768),
        port=8765,
    )
