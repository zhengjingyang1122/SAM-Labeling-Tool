"""
High cohesion, low coupling `Actions` class.

This module defines an ``Actions`` class that acts as a thin façade
between the Qt user interface and the underlying domain controllers.
The intent is to minimise the amount of business logic contained
directly within the GUI layer by delegating responsibilities to
specialised controllers.  In particular, camera‑related behaviours
are delegated to ``CameraController`` and segmentation behaviours to
``SegmentationController``.  This results in a more cohesive and
testable codebase where each controller is responsible for a single
concern.

Prior to this refactor the ``Actions`` class contained hundreds of
lines of mixed logic for camera control, segmentation model
management, file I/O and Qt interactions.  By extracting those
concerns into the controllers we reduce coupling between the GUI and
the infrastructure and make it easier to evolve each feature in
isolation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import QFileDialog

from .camera_controller import CameraController
from .segmentation_controller import SegmentationController

logger = logging.getLogger(__name__)


class Actions:
    """Facade for user actions in the main window.

    The ``Actions`` class wires up UI events to the appropriate
    controllers.  It exposes a subset of methods that match the
    original ``Actions`` API so that existing UI bindings (such as
    button click callbacks) continue to work.  Internally it holds
    instances of ``CameraController`` and ``SegmentationController``
    which implement the actual behaviour.

    Parameters
    ----------
    win : object
        The main window providing access to UI controls such as
        combo boxes, text edits and status footers.
    cam : object
        The camera manager used by ``CameraController``.  This is
        typically an instance of ``CameraManager``.
    explorer_ctrl : object, optional
        An optional explorer controller used by ``SegmentationController``
        to obtain the last image or video path and to bind right‑click
        context menus.
    sam_engine_instance : object, optional
        Optionally provide a pre‑instantiated ``SamEngine`` to the
        segmentation controller.  If omitted the segmentation
        controller will lazily instantiate one when needed.
    """

    def __init__(
        self,
        win: object,
        cam: object,
        explorer_ctrl: Optional[object] = None,
        sam_engine_instance: Optional[object] = None,
    ) -> None:
        self.w = win
        # Initialise domain controllers
        self.camera_controller = CameraController(win, cam)
        self.segmentation_controller = SegmentationController(
            win, explorer_ctrl, sam_engine_instance
        )

    # ------------------------------------------------------------------
    # Directory selection
    # ------------------------------------------------------------------
    def choose_dir(self) -> None:
        """Open a file dialog allowing the user to choose an output directory."""
        d = QFileDialog.getExistingDirectory(self.w, "選擇輸出資料夾", str(self.w.dir_edit.text()))
        if d:
            self.w.dir_edit.setText(d)

    # ------------------------------------------------------------------
    # Camera operations delegate to the controller
    # ------------------------------------------------------------------
    def select_camera_by_name(self, name: str) -> None:
        self.camera_controller.select_camera_by_name(name)

    def populate_camera_devices(self) -> None:
        self.camera_controller.populate_camera_devices()

    def start_camera(self) -> None:
        self.camera_controller.start_camera()

    def stop_camera(self) -> None:
        self.camera_controller.stop_camera()

    def capture_image(self) -> None:
        self.camera_controller.capture_image()

    def start_burst(self) -> None:
        self.camera_controller.start_burst()

    def stop_burst(self) -> None:
        self.camera_controller.stop_burst()

    def resume_recording(self) -> None:
        self.camera_controller.resume_recording()

    def pause_recording(self) -> None:
        self.camera_controller.pause_recording()

    def stop_recording(self) -> None:
        self.camera_controller.stop_recording()

    # ------------------------------------------------------------------
    # Segmentation operations delegate to the controller
    # ------------------------------------------------------------------
    def toggle_preload_sam(self, checked: bool) -> None:
        self.segmentation_controller.toggle_preload_sam(checked)

    def open_auto_segment_menu(self) -> None:
        self.segmentation_controller.open_auto_segment_menu()

    def open_segmentation_view_for_chosen_image(self) -> None:
        self.segmentation_controller.open_segmentation_view_for_chosen_image()

    def open_segmentation_view_for_folder_prompt(self) -> None:
        self.segmentation_controller.open_segmentation_view_for_folder_prompt()

    def open_segmentation_view_for_last_photo(self) -> None:
        self.segmentation_controller.open_segmentation_view_for_last_photo()

    def open_segmentation_view_for_video_file(self) -> None:
        self.segmentation_controller.open_segmentation_view_for_video_file()

    def open_segmentation_view_for_last_video(self) -> None:
        self.segmentation_controller.open_segmentation_view_for_last_video()

    def open_segmentation_for_file_list(self, file_list: List[Path]) -> None:
        """Delegate segmentation of a file list from the explorer."""
        self.segmentation_controller.open_segmentation_for_file_list(file_list)

    # ------------------------------------------------------------------
    # Backwards compatibility stubs
    # ------------------------------------------------------------------
    def _on_output_dir_changed(self, path: str) -> None:
        """
        Placeholder for the original slot.

        The legacy ``Actions`` implementation had a slot that reacted to
        output directory changes.  In this refactored version the window
        itself is responsible for handling edits to the directory text
        field, so this method remains a no‑op to preserve compatibility
        with any existing signal connections.
        """
        pass

    def _on_focus_updated(self, score: float, sharp: bool) -> None:
        """
        Forward focus quality updates to the status footer.

        This method is retained for API compatibility with the previous
        implementation of ``Actions``.  It forwards focus quality
        updates to the status bar if the main window provides the
        appropriate method.
        """
        try:
            self.w.status.set_focus_quality(score, sharp)
        except Exception:
            # fallback: show a temporary message if the main method is missing
            try:
                self.w.status.message_temp(f"{'清晰' if sharp else '模糊'} ({score:.0f})", 800)
            except Exception:
                logger.warning("Focus update could not be displayed", exc_info=True)
