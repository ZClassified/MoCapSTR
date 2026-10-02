import tkinter as tk
import customtkinter as ctk
import json
import logging
import os
import queue
import sys
import threading
from datetime import datetime
from camera_manager import CameraManager
from arduino_sync import ArduinoSync
from project_manager import ProjectManager
from recorder import MultiCamManager
from clip_sync import finalize_clips
from freemocap_bridge import SESSION_INFO_FILENAME
from preset_manager import PresetManager
from app_paths import data_dir, logs_dir
from logging_setup import log_file_path, setup_logging
from settings_store import SettingsStore
import cv2
from PIL import Image, ImageTk
import time

from tabs.setup_tab import SetupTab
from tabs.preview_tab import PreviewTab
from tabs.camera_test_tab import CameraTestTab
from tabs.export_tab import ExportTab

APP_VERSION = "1.5.2"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MoCapSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"MoCapSTR: Sync / Trigger / Record for FreeMoCap v{APP_VERSION}")
        self.geometry("1100x800")
        
        # Set Window Icon
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        icon_path = os.path.join(base_path, "design", "Icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
            
        # Managers
        self.cam_mgr = CameraManager()
        self.arduino = ArduinoSync()
        self.arduino.on_toggle_rec_callback = self.handle_remote_toggle_rec
        
        self.proj_mgr = ProjectManager()
        self.recorder = MultiCamManager()
        self.preset_mgr = PresetManager()
        
        self.camera_indices = []
        self.preview_labels = {} # Grid for previews
        self.camera_enable_vars = {} # Stores IntVars for checkboxes
        self.rotation_menus = {}     # cam_idx -> rotation dropdown in the preview grid
        # User choices that must survive rebuilding the preview grid and app restarts
        self.saved_rotations = {}    # str(cam_idx) -> "0°" / "90° (Portrait)" / ...
        self.saved_enabled = {}      # cam_idx -> 1/0 ("Enable Recording")
        self.settings = SettingsStore()

        self.record_start_time = 0
        self.record_fps = 50
        self.record_hardware_trigger = False
        self.ui_tick = 0
        self.last_free_space = None
        self.last_ping_sent = 0.0
        self.arduino_was_connected = False
        self.arduino_unresponsive_logged = False
        self.last_warning_text = ""
        self.txt_log = None
        # app.log() may be called from any thread; only the Tk main thread touches the widget
        self._log_queue = queue.Queue()

        self.build_ui()
        self.load_session_settings()
        self.after(50, self.update_preview) # Start preview loop
        self.after(100, self._drain_log_queue)
        self.log(f"MoCapSTR v{APP_VERSION} started. Log file: {log_file_path()}")

        # Reset any leftover hardware trigger modes on startup in background
        threading.Thread(target=self.cam_mgr.reset_hardware_trigger_mode, daemon=True).start()
        

    def handle_remote_toggle_rec(self):
        self.after(0, self.toggle_record)
        
    def build_ui(self):
        # Log panel at the bottom, visible in every tab (packed first so it keeps its height)
        self.build_log_panel()

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        self.tab_setup_frame = self.tabview.add("1. Project & Setup")
        self.tab_preview_frame = self.tabview.add("2. Live Preview")
        self.tab_export_frame = self.tabview.add("3. Export & Convert")
        self.tab_test_frame = self.tabview.add("4. Camera Tester")
        
        self.setup_tab = SetupTab(self.tab_setup_frame, self)
        self.setup_tab.pack(fill="both", expand=True)
        
        self.preview_tab = PreviewTab(self.tab_preview_frame, self)
        self.preview_tab.pack(fill="both", expand=True)

        self.test_tab = CameraTestTab(self.tab_test_frame, self)
        self.test_tab.pack(fill="both", expand=True)

        self.export_tab = ExportTab(self.tab_export_frame, self)
        self.export_tab.pack(fill="both", expand=True)

    def build_log_panel(self):
        panel = ctk.CTkFrame(self)
        panel.pack(side="bottom", fill="x", padx=10, pady=(4, 10))

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(4, 0))
        ctk.CTkLabel(header, text="Log", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.btn_log_toggle = ctk.CTkButton(header, text="▾ Ausblenden", width=110, height=24,
                                            command=self.toggle_log_panel)
        self.btn_log_toggle.pack(side="right")
        ctk.CTkButton(header, text="📄 Log-Ordner öffnen", width=150, height=24,
                      command=lambda: os.startfile(logs_dir())).pack(side="right", padx=(0, 8))

        self.txt_log = ctk.CTkTextbox(panel, height=110, wrap="word")
        self.txt_log.pack(fill="x", padx=8, pady=(4, 8))
        self.txt_log.tag_config("success", foreground="#3ddc84")
        self.txt_log.tag_config("error", foreground="#ff5c5c")
        self.txt_log.tag_config("warning", foreground="#f4a261")
        self.txt_log.configure(state="disabled")

    def toggle_log_panel(self):
        if self.txt_log.winfo_ismapped():
            self.txt_log.pack_forget()
            self.btn_log_toggle.configure(text="▸ Einblenden")
        else:
            self.txt_log.pack(fill="x", padx=8, pady=(4, 8))
            self.btn_log_toggle.configure(text="▾ Ausblenden")

    def report_callback_exception(self, exc_type, exc, tb):
        """Exceptions in Tk callbacks: into the log file and visible in the UI log."""
        logging.getLogger("ui").error("Exception in UI callback", exc_info=(exc_type, exc, tb))
        self.log(f"Unexpected error: {exc_type.__name__}: {exc} (details in the log file)", "error")

    def load_session_settings(self):
        """Restores project, save folder and setup of the last session."""
        data = self.settings.data
        if not data:
            return
        try:
            self.setup_tab.apply_settings(data)
            if data.get("project_name"):
                self.setup_tab.proj_name_entry.delete(0, tk.END)
                self.setup_tab.proj_name_entry.insert(0, data["project_name"])
            if data.get("take_name"):
                self.preview_tab.take_name_entry.delete(0, tk.END)
                self.preview_tab.take_name_entry.insert(0, data["take_name"])
            base_path = data.get("base_path")
            if base_path and os.path.isdir(base_path):
                self.proj_mgr.set_base_path(base_path)
                self.setup_tab.lbl_save_dir.configure(text=base_path)
            elif base_path:
                self.log(f"Last save folder not found ({base_path}) - using {self.proj_mgr.base_path}.", "warning")
        except Exception as e:
            self.log(f"Could not restore the last settings: {e}", "warning")

    def save_session_settings(self):
        try:
            data = self.setup_tab.collect_settings()
            data["project_name"] = self.setup_tab.proj_name_entry.get()
            data["take_name"] = self.preview_tab.take_name_entry.get()
            data["base_path"] = self.proj_mgr.base_path
            self.settings.save(data)
        except Exception as e:
            print(f"[Settings] Could not collect settings: {e}")

    def apply_saved_rotations(self):
        """Applies the remembered rotation to every running camera worker."""
        for idx in self.recorder.workers:
            choice = self.saved_rotations.get(str(idx), "0°")
            self.recorder.set_camera_rotation(idx, int(choice.split('°')[0]))

    def get_free_space(self):
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.proj_mgr.base_path)
            return free // (2**30)
        except Exception:
            return None  # Unknown - must not trigger the low-space auto-stop

    LOG_LEVELS = {"info": logging.INFO, "success": logging.INFO, "warning": logging.WARNING, "error": logging.ERROR}
    MAX_LOG_LINES = 1000

    def log(self, message, level="info"):
        """Thread-safe: writes to the log file immediately, the UI log is updated by the main thread."""
        logging.getLogger("app").log(self.LOG_LEVELS.get(level, logging.INFO), message)
        self._log_queue.put((datetime.now().strftime("%H:%M:%S"), message, level))

    def _drain_log_queue(self):
        try:
            if self.txt_log is not None and not self._log_queue.empty():
                self.txt_log.configure(state="normal")
                while True:
                    try:
                        stamp, message, level = self._log_queue.get_nowait()
                    except queue.Empty:
                        break
                    tag = level if level in ("success", "error", "warning") else None
                    self.txt_log.insert(tk.END, f"{stamp}  {message}\n", tag)
                lines = int(self.txt_log.index("end-1c").split(".")[0])
                if lines > self.MAX_LOG_LINES:
                    self.txt_log.delete("1.0", f"{lines - self.MAX_LOG_LINES}.0")
                self.txt_log.see(tk.END)
                self.txt_log.configure(state="disabled")
        finally:
            self.after(100, self._drain_log_queue)

    def toggle_record(self):
        if not self.recorder.is_recording:
            # START
            proj_name = self.setup_tab.proj_name_entry.get()
            if not proj_name:
                self.log("Error: Enter a project name.", level="error")
                return
                
            self.proj_mgr.set_project(proj_name)
            is_calib = (self.preview_tab.chk_charuco.get() == 1)
            take_name = self.preview_tab.take_name_entry.get()
            save_dir = self.proj_mgr.get_recording_folder(is_calib, take_name)
            
            fps = self.setup_tab.get_target_fps()
            codec = self.setup_tab.codec_combo.get()
            
            enabled_cams = [idx for idx, var in self.camera_enable_vars.items() if var.get() == 1]
            if not enabled_cams:
                self.log("Error: No cameras enabled for recording.", level="error")
                return
            
            self.log(f"Starting recording to: {save_dir}")
            self.save_session_settings()

            # Generate session_info.json for FreeMoCap
            try:
                session_info = {
                    "mocapstr_version": APP_VERSION,
                    "project": proj_name,
                    "take": "calibration" if is_calib else take_name,
                    "recording_type": "calibration" if is_calib else "mocap",
                    "hardware_trigger": self.arduino.is_running,
                    "fps": fps,
                    "codec": codec,
                    "resolution": self.setup_tab.res_combo.get(),
                    "charuco_dict": self.preview_tab.charuco_dict.get(),
                    "charuco_x": int(self.preview_tab.charuco_x.get()),
                    "charuco_y": int(self.preview_tab.charuco_y.get()),
                    "charuco_sq_size": float(self.preview_tab.charuco_sq_size.get()),
                    "charuco_marker_size": float(self.preview_tab.charuco_marker_size.get())
                }
                info_path = os.path.join(os.path.dirname(save_dir), SESSION_INFO_FILENAME)
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(session_info, f, indent=4)
                self.log("Generated session_info.json", "success")
            except Exception as e:
                self.log(f"Failed to generate session_info.json: {e}", "error")
                
            # --- START SYNCHRONIZATION ---
            # Stop the trigger briefly to flush lingering packets from PyAV demux
            # so that all cameras start on the EXACT same new frame pulse.
            trigger_was_running = self.arduino.is_running
            if trigger_was_running:
                self.log("Synchronizing start frame...")
                self.arduino.stop_trigger()
                time.sleep(0.15) # Wait for pyav buffers to drain

            started = self.recorder.start_recording(save_dir, fps, codec, enabled_cams,
                                                    hold_until_released=trigger_was_running)
            if not started:
                self.log("Error: Recording could not be started (no camera ready).", level="error")
                if trigger_was_running:
                    self.arduino.start_trigger()
                return
            self.record_start_time = time.time()
            self.record_fps = fps
            self.record_hardware_trigger = trigger_was_running

            if trigger_was_running:
                self.arduino.start_trigger()
                # The first new pulse fires one trigger interval after <START>.
                # Anything arriving before half an interval is a stale frame from
                # before the restart and must not become frame 0.
                interval_ns = int(1e9 / max(1, self.arduino.current_fps))
                self.recorder.release_recording_gate(time.perf_counter_ns() + interval_ns // 2)
            # -----------------------------
            
            self.preview_tab.btn_record_live.configure(text="⏹ STOP RECORDING", fg_color="red", hover_color="darkred")
        else:
            # STOP
            
            # --- STOP SYNCHRONIZATION ---
            # Stop the trigger first, wait for the last frames to process, 
            # then close the recorder so all cameras have the exact same end frame.
            trigger_was_running = self.arduino.is_running
            if trigger_was_running:
                self.log("Synchronizing end frame...")
                self.arduino.stop_trigger()
                time.sleep(0.2) # Allow PyAV to fetch the final frames
                
            # stop_recording() returns {cam_idx: RecordingResult} for verification
            results = self.recorder.stop_recording()

            if trigger_was_running:
                self.arduino.start_trigger() # Resume preview
            # ----------------------------

            self.preview_tab.btn_record_live.configure(text="⏺ START RECORDING", fg_color="darkred", hover_color="red")
            self.log("Recording stopped. Verifying clip synchronization...")

            # Verify/align in a background thread so the UI stays responsive.
            def _finalize(clip_results, fps, hardware_trigger):
                try:
                    _, messages = finalize_clips(clip_results, fps, hardware_trigger)
                except Exception as e:
                    messages = [("error", f"Clip verification failed: {e}")]
                for level, text in messages:
                    self.after(0, lambda t=text, l=level: self.log(t, l))

            threading.Thread(target=_finalize,
                             args=(results, self.record_fps, self.record_hardware_trigger),
                             daemon=True).start()

    def update_preview(self):
        self.ui_tick += 1
        
        warnings = []

        # --- Arduino health (time-based, independent of UI frame rate) ---
        now = time.time()
        if self.arduino.is_connected:
            self.arduino_was_connected = True
            if now - self.last_ping_sent >= 1.0:
                self.arduino.ping()
                self.last_ping_sent = now
            responsive = self.arduino.is_responsive()
            if responsive is False:
                warnings.append("⚠️ TRIGGER-BOX ANTWORTET NICHT")
                if not self.arduino_unresponsive_logged:
                    self.log("Arduino does not answer PING (>5 s). Connection is kept - check USB cable.", "error")
                    self.arduino_unresponsive_logged = True
            elif responsive:
                if self.arduino_unresponsive_logged:
                    self.log("Arduino responds again.", "success")
                self.arduino_unresponsive_logged = False
        elif self.arduino_was_connected:
            # Serial port failed (cable unplugged etc.): the trigger is really gone.
            warnings.append("⚠️ ARDUINO DISCONNECTED!")
            if self.arduino.is_running:
                self.arduino.is_running = False
                self.log("Arduino serial connection lost!", "error")

        if self.ui_tick % 20 == 0 or self.ui_tick == 1:
            self.last_free_space = self.get_free_space()

            if self.recorder.is_recording and self.last_free_space is not None and self.last_free_space < 2:
                self.log("CRITICAL: Less than 2 GB free! Auto-stopping recording.", "error")
                self.toggle_record()

        free = self.last_free_space
        space_str = f"Space: {free} GB" if free is not None else "Space: ? GB"
        low_space = free is not None and free < 20
        color = "red" if low_space else ("white" if ctk.get_appearance_mode() == "Dark" else "black")

        if not self.recorder.is_recording:
            if self.ui_tick % 20 == 0 or self.ui_tick == 1:
                self.preview_tab.lbl_live_stats.configure(text=f"Ready | {space_str}", text_color=color)
        else:
            elapsed = time.time() - self.record_start_time
            mins, secs = divmod(int(elapsed), 60)

            # Only cameras that take part in this recording
            recording = self.recorder.recording_workers()
            frame_counts = [w.frames_recorded for w in recording.values()]
            max_frames = max(frame_counts) if frame_counts else 0
            min_frames = min(frame_counts) if frame_counts else 0
            lost = sum(w.lost_frames for w in recording.values())

            if lost:
                warnings.append(f"⚠️ {lost} Frame(s) verloren (durch Kopien ersetzt)")
            if max_frames - min_frames > 5:
                warnings.append(f"⚠️ SYNC WARNING: Frame drop! (Delta: {max_frames - min_frames})")

            if low_space:
                space_str = f"⚠️ LOW SPACE: {free} GB"

            self.preview_tab.lbl_live_stats.configure(text=f"Recording 🔴 | {mins:02d}:{secs:02d} | Frames: {max_frames} | {space_str}", text_color=color)

        warning_text = " | ".join(warnings)
        if warning_text != self.last_warning_text:
            self.preview_tab.lbl_live_warning.configure(text=warning_text)
            self.last_warning_text = warning_text

        # Update UI with latest frames
        frames = self.recorder.get_latest_frames()
        for idx, frame in frames.items():
            if idx in self.preview_labels:
                # Resize keeping aspect ratio for UI
                lbl = self.preview_labels[idx]
                target_w = lbl.winfo_width()
                target_h = lbl.winfo_height()
                if target_w > 10 and target_h > 10:
                    # Convert BGR to RGB (creates a new array, safe to modify)
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # --- FPS & Stall Overlay ---
                    fps = 0.0
                    is_stalled = False
                    now = time.time()
                    if idx in self.recorder.workers:
                        worker = self.recorder.workers[idx]
                        fps = worker.current_fps
                        # If trigger is supposed to be running, check if camera hasn't sent packets for > 2.0s
                        if self.arduino.is_running and (now - getattr(worker, 'last_packet_time', now) > 2.0):
                            is_stalled = True
                            fps = 0.0
                        
                    try:
                        target_fps = float(self.setup_tab.fps_entry.get())
                    except ValueError:
                        target_fps = 50.0
                        
                    # Determine color and text based on deviation or stall
                    if is_stalled:
                        color = (255, 0, 0) # Red
                        text = "⚠️ NO SIGNAL / FROZEN (0.0 FPS)"
                    else:
                        diff = abs(fps - target_fps)
                        if diff <= 0.5:
                            color = (0, 255, 0) # Green (Perfect)
                        elif diff <= 3.0:
                            color = (255, 255, 0) # Yellow (Slight deviation)
                        else:
                            color = (255, 0, 0) # Red (Significant deviation)
                        text = f"FPS: {fps:.1f}"
                        
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    # Smaller font scale
                    font_scale = max(0.35, rgb_frame.shape[0] / 1600.0)
                    thickness = max(1, int(font_scale * 1.5))
                    (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
                    
                    x, y = 20, int(20 + text_h)
                    pad = 10
                    
                    # Fast semi-transparent background using ROI
                    roi_x1, roi_y1 = max(0, x - pad), max(0, y - text_h - pad)
                    roi_x2, roi_y2 = min(rgb_frame.shape[1], x + text_w + pad), min(rgb_frame.shape[0], y + baseline + pad)
                    
                    if roi_x2 > roi_x1 and roi_y2 > roi_y1:
                        roi = rgb_frame[roi_y1:roi_y2, roi_x1:roi_x2]
                        black_rect = roi.copy()
                        black_rect[:] = 0
                        cv2.addWeighted(black_rect, 0.5, roi, 0.5, 0, roi)
                    
                    # Draw text in chosen color
                    cv2.putText(rgb_frame, text, (x, y), font, font_scale, color, thickness)
                    # -------------------
                    
                    img = Image.fromarray(rgb_frame)
                    
                    # Letterboxing thumbnail
                    img.thumbnail((target_w, target_h), Image.Resampling.BILINEAR)
                    # Create new image with black background
                    new_img = Image.new("RGB", (target_w, target_h), (0, 0, 0))
                    new_img.paste(img, ((target_w - img.size[0]) // 2, (target_h - img.size[1]) // 2))
                    
                    photo = ImageTk.PhotoImage(image=new_img)
                    lbl.configure(image=photo)
                    lbl.image = photo # Keep reference
                    
        self.after(50, self.update_preview) # ~20 FPS UI update

    def on_closing(self):
        self.save_session_settings()
        try:
            print("[Shutdown] Stopping camera workers...")
            self.recorder.stop_workers()
            print("[Shutdown] Closing camera streams...")
            self.cam_mgr.close_all()
            print("[Shutdown] Resetting camera trigger to free-run mode...")
            self.cam_mgr.reset_hardware_trigger_mode()
            print("[Shutdown] Disconnecting Arduino...")
            self.arduino.disconnect()
        except Exception as e:
            print(f"[Shutdown] Error during cleanup: {e}")
        finally:
            remove_instance_pid()
            try:
                self.destroy()
            except Exception:
                pass
            time.sleep(0.2)
            # Force immediate OS-level process exit to guarantee all DirectShow/UVC device handles are released
            os._exit(0)

_single_instance_mutex = None
INSTANCE_PID_FILE = os.path.join(data_dir(), "instance.pid")


def _process_image_path(pid):
    """Full executable path of a running process, or None if it does not exist."""
    import ctypes
    from ctypes import wintypes
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return None
    finally:
        kernel32.CloseHandle(handle)


def _running_instance_pid():
    """PID of the other MoCapSTR instance (from its PID file), if it is still running."""
    try:
        with open(INSTANCE_PID_FILE, encoding="utf-8") as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return None
    if pid == os.getpid():
        return None
    image = _process_image_path(pid)
    if not image:
        return None
    # Guard against PID reuse: only accept MoCapSTR.exe or a Python interpreter
    name = os.path.basename(image).lower()
    if not (name.startswith("mocapstr") or name in ("python.exe", "pythonw.exe")):
        return None
    return pid


def _write_instance_pid():
    try:
        os.makedirs(os.path.dirname(INSTANCE_PID_FILE), exist_ok=True)
        with open(INSTANCE_PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except OSError as e:
        print(f"[Startup] Could not write PID file: {e}")


def remove_instance_pid():
    try:
        with open(INSTANCE_PID_FILE, encoding="utf-8") as f:
            if f.read().strip() != str(os.getpid()):
                return  # file belongs to another instance
        os.remove(INSTANCE_PID_FILE)
    except (OSError, ValueError):
        pass


def enforce_single_instance():
    """
    Only one MoCapSTR may use the cameras. If another instance is running, the user
    decides: quit this one, or end the other one (e.g. if it hangs). Only that exact
    process (from its PID file) is ended - never other Python programs.
    Returns False if this instance should exit.
    """
    global _single_instance_mutex
    if not sys.platform.startswith("win"):
        return True
    try:
        import ctypes
        MUTEX_NAME = "Global\\MoCapSTR_Application_Singleton_Mutex_v1"
        kernel32 = ctypes.windll.kernel32
        _single_instance_mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        already_running = kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    except Exception as e:
        print(f"[Startup] Single instance check note: {e}")
        return True

    if already_running:
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        other_pid = _running_instance_pid()
        if other_pid is None:
            messagebox.showwarning(
                "MoCapSTR läuft bereits",
                "MoCapSTR läuft bereits (oder eine ältere Version hängt noch im Hintergrund).\n\n"
                "Bitte die andere Instanz schließen, ggf. über den Task-Manager.",
                parent=root)
            root.destroy()
            return False
        end_other = messagebox.askyesno(
            "MoCapSTR läuft bereits",
            f"Eine andere MoCapSTR-Instanz läuft bereits (Prozess {other_pid}).\n\n"
            "Nur falls diese hängt oder nicht mehr reagiert: Soll sie beendet und "
            "MoCapSTR neu gestartet werden?\n\n"
            "Achtung: Eine laufende Aufnahme in der anderen Instanz wird dabei abgebrochen.\n\n"
            "Nein = diesen Start abbrechen.",
            icon="warning", default="no", parent=root)
        root.destroy()
        if not end_other:
            return False
        import subprocess
        subprocess.run(["taskkill", "/PID", str(other_pid), "/T", "/F"], capture_output=True, timeout=10)
        time.sleep(1.0)  # let Windows release the camera and COM port handles

    _write_instance_pid()
    return True

if __name__ == "__main__":
    setup_logging()
    if not enforce_single_instance():
        sys.exit(0)
    app = MoCapSyncApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
