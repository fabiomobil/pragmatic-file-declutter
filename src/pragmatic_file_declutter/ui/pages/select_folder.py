"""Select folder page — first page of the application.

Allows user to select a folder and see scan results before processing.
"""

from __future__ import annotations

import asyncio
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from pragmatic_file_declutter.core.scanner import ScanResult


class SelectFolderPage:
    """Page for selecting a folder and viewing scan results."""

    def __init__(self) -> None:
        """Initialize the page state."""
        self._selected_path: Path | None = None
        self._scan_result: ScanResult | None = None
        self._scanning: bool = False

        # UI elements (set during build)
        self._path_label: ui.label | None = None
        self._scan_button: ui.button | None = None
        self._results_container: ui.column | None = None
        self._progress_spinner: ui.spinner | None = None

    def build(self) -> None:
        """Build the page UI."""
        with ui.column().classes("w-full max-w-3xl mx-auto p-8 gap-6"):
            # Header
            ui.label("Pragmatic File Declutter").classes("text-3xl font-bold text-center w-full")
            ui.label("Organize your photos automatically").classes("text-gray-500 text-center w-full")

            ui.separator()

            # Folder selection
            with ui.card().classes("w-full"):
                ui.label("Step 1: Select a folder to scan").classes("text-lg font-semibold")

                with ui.row().classes("w-full items-center gap-4"):
                    self._path_label = ui.label("No folder selected").classes("flex-grow text-gray-600")

                    ui.button("Browse...", on_click=self._on_browse).props("outline")

            # Scan button
            with ui.row().classes("w-full justify-center"):
                self._scan_button = ui.button("Scan Folder", on_click=self._on_scan)
                self._scan_button.props("color=primary size=lg")
                self._scan_button.disable()

                self._progress_spinner = ui.spinner("dots", size="lg")
                self._progress_spinner.set_visibility(False)

            # Results container (hidden initially)
            self._results_container = ui.column().classes("w-full gap-4")
            self._results_container.set_visibility(False)

    async def _on_browse(self) -> None:
        """Handle browse button click."""
        # Use native folder picker
        result = await ui.run_javascript(
            """
            (async () => {
                try {
                    const handle = await window.showDirectoryPicker();
                    return handle.name;
                } catch (e) {
                    return null;
                }
            })()
            """,
            timeout=60.0,
        )

        if result:
            # For now, we'll use a text input since showDirectoryPicker
            # doesn't give us the full path for security reasons
            await self._show_path_dialog()

    async def _show_path_dialog(self) -> None:
        """Show a dialog to enter the folder path."""
        with ui.dialog() as dialog, ui.card().classes("p-4 gap-4"):
            ui.label("Enter folder path:").classes("font-semibold")
            path_input = ui.input(placeholder="C:\\Users\\...\\Photos").classes("w-96")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                async def on_confirm() -> None:
                    path_str = path_input.value
                    if not path_str:
                        ui.notify("Please enter a path", type="warning")
                        return

                    path = Path(path_str).resolve()

                    # SECURITY: Reject network paths (UNC)
                    if str(path).startswith("\\\\"):
                        ui.notify("Network paths are not supported for security reasons", type="warning")
                        return

                    # SECURITY: Warn about system directories
                    system_dirs = ["Windows", "Program Files", "Program Files (x86)", "System32"]
                    if any(sd.lower() in str(path).lower() for sd in system_dirs):
                        ui.notify("System directories cannot be scanned", type="warning")
                        return

                    if path.exists() and path.is_dir():
                        self._selected_path = path
                        if self._path_label:
                            # SECURITY: Escape path before display
                            self._path_label.text = escape(str(path))
                        if self._scan_button:
                            self._scan_button.enable()
                        dialog.close()
                    else:
                        ui.notify("Invalid folder path", type="negative")

                ui.button("OK", on_click=on_confirm).props("color=primary")

        dialog.open()

    async def _on_scan(self) -> None:
        """Handle scan button click."""
        if not self._selected_path or self._scanning:
            return

        self._scanning = True
        if self._scan_button:
            self._scan_button.disable()
        if self._progress_spinner:
            self._progress_spinner.set_visibility(True)
        if self._results_container:
            self._results_container.clear()
            self._results_container.set_visibility(False)

        try:
            # Run scan in background to not block UI
            from pragmatic_file_declutter.core.scanner import scan_directory

            loop = asyncio.get_event_loop()
            self._scan_result = await loop.run_in_executor(
                None,
                lambda: scan_directory(self._selected_path, validate_images=True),  # type: ignore[arg-type]
            )

            self._show_results()

        except Exception as e:
            # SECURITY: Escape error message to prevent XSS
            ui.notify(f"Scan failed: {escape(str(e))}", type="negative")

        finally:
            self._scanning = False
            if self._scan_button:
                self._scan_button.enable()
            if self._progress_spinner:
                self._progress_spinner.set_visibility(False)

    def _show_results(self) -> None:
        """Display scan results."""
        if not self._scan_result or not self._results_container:
            return

        result = self._scan_result

        with self._results_container:
            self._results_container.clear()

            ui.separator()
            ui.label("Scan Results").classes("text-xl font-bold")

            # Summary cards
            with ui.row().classes("w-full gap-4"):
                self._result_card("Images", str(result.total_images), "image", "blue")
                self._result_card("Videos", str(result.total_videos), "movie", "purple")
                self._result_card("Corrupted", str(result.total_corrupted), "warning", "red")
                self._result_card("Skipped", str(result.total_skipped), "block", "gray")

            # Size info
            size_mb = result.total_size_bytes / (1024 * 1024)
            ui.label(f"Total size: {size_mb:.1f} MB").classes("text-gray-600")

            # Format breakdown
            if result.total_images > 0:
                with ui.card().classes("w-full"):
                    ui.label("Image formats").classes("font-semibold")

                    breakdown = result.get_format_breakdown()
                    with ui.row().classes("flex-wrap gap-2"):
                        for ext, count in sorted(breakdown.items(), key=lambda x: -x[1]):
                            ui.badge(f"{ext}: {count}").props("outline")

            # Next steps
            if result.total_images > 1:
                ui.separator()
                with ui.row().classes("w-full justify-center"):
                    ui.button(
                        "Find Duplicates",
                        on_click=lambda: ui.notify("Coming soon in v0.1.0!", type="info"),
                    ).props("color=primary size=lg")

        self._results_container.set_visibility(True)

    def _result_card(self, label: str, value: str, icon: str, color: str) -> None:
        """Create a result summary card."""
        with ui.card().classes("flex-1 min-w-32"):
            with ui.column().classes("items-center gap-1"):
                ui.icon(icon).classes(f"text-3xl text-{color}-500")
                ui.label(value).classes("text-2xl font-bold")
                ui.label(label).classes("text-gray-500 text-sm")


def create_page() -> SelectFolderPage:
    """Create and build the select folder page.

    Returns:
        The created page instance.
    """
    page = SelectFolderPage()
    page.build()
    return page
