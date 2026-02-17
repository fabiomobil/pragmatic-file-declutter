"""Select folder page — first page of the application.

Allows user to select a folder, scan for images, and find duplicates.
"""

from __future__ import annotations

import asyncio
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from pragmatic_file_declutter.core.dedup import DeduplicationResult, DuplicateGroup
    from pragmatic_file_declutter.core.scanner import ScanResult


class SelectFolderPage:
    """Page for selecting a folder, scanning, and finding duplicates."""

    def __init__(self) -> None:
        """Initialize the page state."""
        self._selected_path: Path | None = None
        self._scan_result: ScanResult | None = None
        self._dedup_result: DeduplicationResult | None = None
        self._scanning: bool = False
        self._deduplicating: bool = False

        # UI elements
        self._path_label: ui.label | None = None
        self._scan_button: ui.button | None = None
        self._results_container: ui.column | None = None
        self._progress_spinner: ui.spinner | None = None
        self._progress_label: ui.label | None = None
        self._dedup_container: ui.column | None = None

    def build(self) -> None:
        """Build the page UI."""
        with ui.column().classes("w-full max-w-4xl mx-auto p-8 gap-6"):
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

            # Scan button and progress
            with ui.row().classes("w-full justify-center items-center gap-4"):
                self._scan_button = ui.button("Scan Folder", on_click=self._on_scan)
                self._scan_button.props("color=primary size=lg")
                self._scan_button.disable()

                self._progress_spinner = ui.spinner("dots", size="lg")
                self._progress_spinner.set_visibility(False)

                self._progress_label = ui.label("")
                self._progress_label.set_visibility(False)

            # Results container
            self._results_container = ui.column().classes("w-full gap-4")
            self._results_container.set_visibility(False)

            # Dedup results container
            self._dedup_container = ui.column().classes("w-full gap-4")
            self._dedup_container.set_visibility(False)

    async def _on_browse(self) -> None:
        """Handle browse button click using native Windows folder picker."""
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        folder_path = filedialog.askdirectory(
            title="Select folder to scan",
            mustexist=True,
        )

        root.destroy()

        if folder_path:
            path = Path(folder_path).resolve()

            # SECURITY: Reject network paths
            if str(path).startswith("\\\\"):
                ui.notify("Network paths are not supported", type="warning")
                return

            # SECURITY: Reject system directories
            system_dirs = ["Windows", "Program Files", "Program Files (x86)", "System32"]
            if any(sd.lower() in str(path).lower() for sd in system_dirs):
                ui.notify("System directories cannot be scanned", type="warning")
                return

            if path.exists() and path.is_dir():
                self._selected_path = path
                if self._path_label:
                    self._path_label.text = escape(str(path))
                if self._scan_button:
                    self._scan_button.enable()
                # Reset previous results
                self._scan_result = None
                self._dedup_result = None
                if self._results_container:
                    self._results_container.set_visibility(False)
                if self._dedup_container:
                    self._dedup_container.set_visibility(False)

    async def _on_scan(self) -> None:
        """Handle scan button click."""
        if not self._selected_path or self._scanning:
            return

        self._scanning = True
        self._set_progress(True, "Scanning folder...")

        try:
            from pragmatic_file_declutter.core.scanner import scan_directory

            loop = asyncio.get_event_loop()
            self._scan_result = await loop.run_in_executor(
                None,
                lambda: scan_directory(self._selected_path, validate_images=True),  # type: ignore[arg-type]
            )
            self._show_scan_results()

        except Exception as e:
            ui.notify(f"Scan failed: {escape(str(e))}", type="negative")

        finally:
            self._scanning = False
            self._set_progress(False)

    def _set_progress(self, visible: bool, message: str = "") -> None:
        """Show/hide progress indicator."""
        if self._scan_button:
            self._scan_button.set_enabled(not visible)
        if self._progress_spinner:
            self._progress_spinner.set_visibility(visible)
        if self._progress_label:
            self._progress_label.text = message
            self._progress_label.set_visibility(visible and bool(message))

    def _show_scan_results(self) -> None:
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

            # Find Duplicates button
            if result.total_images > 1:
                ui.separator()
                with ui.row().classes("w-full justify-center"):
                    ui.button(
                        "Find Duplicates",
                        on_click=self._on_find_duplicates,
                    ).props("color=primary size=lg icon=search")

        self._results_container.set_visibility(True)

    async def _on_find_duplicates(self) -> None:
        """Handle find duplicates button click."""
        if not self._scan_result or self._deduplicating:
            return

        self._deduplicating = True
        self._set_progress(True, "Computing image hashes...")

        try:
            from pragmatic_file_declutter.core.dedup import deduplicate

            def run_dedup() -> DeduplicationResult:
                def on_progress(stage: str, current: int, total: int) -> None:
                    # Update progress in UI thread
                    pass  # Progress updates would need ui.timer for async update

                return deduplicate(
                    self._scan_result.images,  # type: ignore[union-attr]
                    on_progress=on_progress,
                )

            loop = asyncio.get_event_loop()
            self._dedup_result = await loop.run_in_executor(None, run_dedup)

            self._show_dedup_results()

        except Exception as e:
            import traceback
            traceback.print_exc()
            ui.notify(f"Deduplication failed: {escape(str(e))}", type="negative")

        finally:
            self._deduplicating = False
            self._set_progress(False)

    def _show_dedup_results(self) -> None:
        """Display deduplication results."""
        if not self._dedup_result or not self._dedup_container:
            return

        result = self._dedup_result

        with self._dedup_container:
            self._dedup_container.clear()

            ui.separator()
            ui.label("Duplicate Detection Results").classes("text-xl font-bold")

            # Summary
            with ui.row().classes("w-full gap-4"):
                self._result_card(
                    "Identical",
                    str(result.total_identical),
                    "file_copy",
                    "red",
                )
                self._result_card(
                    "Similar",
                    str(result.total_similar),
                    "compare",
                    "orange",
                )
                self._result_card(
                    "Unique",
                    str(result.total_unique),
                    "check_circle",
                    "green",
                )

            # Results message
            if result.total_duplicates == 0:
                with ui.card().classes("w-full bg-green-50 p-4"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("check_circle").classes("text-green-500 text-4xl")
                        with ui.column().classes("gap-1"):
                            ui.label("No duplicates found!").classes("text-green-700 text-lg font-semibold")
                            ui.label("All your images are unique.").classes("text-green-600")
            else:
                # Summary message
                with ui.card().classes("w-full bg-amber-50 p-4"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("warning").classes("text-amber-500 text-4xl")
                        with ui.column().classes("gap-1"):
                            ui.label(f"Found {result.total_duplicates} duplicate images").classes("text-amber-700 text-lg font-semibold")
                            if result.space_recoverable > 0:
                                space_mb = result.space_recoverable / (1024 * 1024)
                                ui.label(f"You could save {space_mb:.1f} MB by removing them").classes("text-amber-600")
                # Show identical groups
                if result.identical_groups:
                    ui.label("Identical Duplicates").classes("text-lg font-semibold mt-4")
                    ui.label("These images are exact or near-exact copies").classes("text-gray-500 text-sm")

                    for i, group in enumerate(result.identical_groups):
                        self._show_duplicate_group(group, i, "identical")

                # Show similar groups
                if result.similar_groups:
                    ui.label("Similar Images").classes("text-lg font-semibold mt-4")
                    ui.label("These images look similar but may have differences").classes("text-gray-500 text-sm")

                    for i, group in enumerate(result.similar_groups):
                        self._show_duplicate_group(group, i, "similar")

        self._dedup_container.set_visibility(True)

    def _show_duplicate_group(self, group: DuplicateGroup, index: int, group_type: str) -> None:
        """Show a group of duplicate images."""
        color = "red" if group_type == "identical" else "orange"

        with ui.card().classes(f"w-full border-l-4 border-{color}-500"):
            # Header
            with ui.row().classes("w-full items-center gap-2 mb-2"):
                ui.icon("photo_library").classes(f"text-{color}-500")
                ui.label(f"Group {index + 1}").classes("font-semibold")
                ui.badge(f"{group.size} images").props(f"color={color}")
                if group.avg_distance > 0:
                    ui.label(f"(similarity: {100 - group.avg_distance * 10:.0f}%)").classes("text-gray-500 text-sm")

            # Images side by side
            with ui.row().classes("flex-wrap gap-3"):
                # Show original first
                self._show_image_card(group.original.path, is_original=True)

                # Then duplicates
                for dup in group.duplicates:
                    self._show_image_card(dup.path, is_original=False)

    def _show_image_card(self, path: Path, is_original: bool) -> None:
        """Show a card for a single image."""
        with ui.card().classes("w-48"):
            # Thumbnail
            try:
                ui.image(str(path)).classes("w-full h-32 object-cover rounded")
            except Exception:
                with ui.row().classes("w-full h-32 bg-gray-200 items-center justify-center rounded"):
                    ui.icon("broken_image").classes("text-gray-400 text-3xl")

            # Info
            with ui.column().classes("p-2 gap-1"):
                filename = path.name
                if len(filename) > 20:
                    filename = filename[:17] + "..."
                ui.label(escape(filename)).classes("text-sm font-medium truncate")

                # Size
                try:
                    size_kb = path.stat().st_size / 1024
                    ui.label(f"{size_kb:.0f} KB").classes("text-xs text-gray-500")
                except OSError:
                    pass

                # Badge
                if is_original:
                    ui.badge("KEEP", color="green").props("outline")
                else:
                    ui.badge("DUPLICATE", color="red").props("outline")

    def _result_card(self, label: str, value: str, icon: str, color: str) -> None:
        """Create a result summary card."""
        with ui.card().classes("flex-1 min-w-32"):
            with ui.column().classes("items-center gap-1"):
                ui.icon(icon).classes(f"text-3xl text-{color}-500")
                ui.label(value).classes("text-2xl font-bold")
                ui.label(label).classes("text-gray-500 text-sm")


def create_page() -> SelectFolderPage:
    """Create and build the select folder page."""
    page = SelectFolderPage()
    page.build()
    return page
