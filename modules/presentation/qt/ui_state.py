# modules/ui_state.py
from __future__ import annotations


def update_ui_state(win):
    cam_active = win.cam.is_active()
    in_burst = win.burst_ctrl.is_active() if win.burst_ctrl else False

    win.btn_start_cam.setEnabled(not cam_active)
    win.btn_stop_cam.setEnabled(cam_active)

    win.btn_capture.setEnabled(cam_active and not in_burst)

    win.btn_start_burst.setEnabled(cam_active and not in_burst)
    win.btn_stop_burst.setEnabled(cam_active and in_burst)
    win.burst_count.setEnabled(cam_active and not in_burst)
    win.burst_interval.setEnabled(cam_active and not in_burst)

    win.btn_rec_resume.setEnabled(cam_active)
    win.btn_rec_pause.setEnabled(cam_active)
    win.btn_rec_stop.setEnabled(cam_active)

    win.btn_auto_seg_image.setEnabled(True)  # 有最近照片時可用，沒照片按了會提示
