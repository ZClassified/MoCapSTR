import tkinter as tk
import customtkinter as ctk
import json
import os
import sys
from camera_manager import CameraManager
from arduino_sync import ArduinoSync
from project_manager import ProjectManager
from recorder import MultiCamManager
from preset_manager import PresetManager
import cv2
from PIL import Image, ImageTk
import time

from tabs.setup_tab import SetupTab
from tabs.preview_tab import PreviewTab
from tabs.camera_test_tab import CameraTestTab
from tabs.export_tab import ExportTab

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MoCapSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MoCapSTR: Sync / Trigger / Record for FreeMoCap v1.2.0")
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
        
        self.record_start_time = 0
        self.ui_tick = 0
        self.last_free_space = 0
        self.txt_log = None # Injected by SetupTab
        
        self.build_ui()
        self.after(50, self.update_preview) # Start preview loop
        

    def handle_remote_toggle_rec(self):
        self.after(0, self.toggle_record)
        
    def build_ui(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_setup_frame = self.tabview.add("1. Project & Setup")
        self.tab_preview_frame = self.tabview.add("2. Live Preview")
        self.tab_test_frame = self.tabview.add("3. Camera Tester")
        self.tab_export_frame = self.tabview.add("4. Export & Convert")
        
        self.setup_tab = SetupTab(self.tab_setup_frame, self)
        self.setup_tab.pack(fill="both", expand=True)
        
        self.preview_tab = PreviewTab(self.tab_preview_frame, self)
        self.preview_tab.pack(fill="both", expand=True)

        self.test_tab = CameraTestTab(self.tab_test_frame, self)
        self.test_tab.pack(fill="both", expand=True)

        self.export_tab = ExportTab(self.tab_export_frame, self)
        self.export_tab.pack(fill="both", expand=True)

    def get_free_space(self):
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.proj_mgr.base_path)
            return free // (2**30)
        except Exception:
            return 0

    def log(self, message, level="info"):
        if not self.txt_log:
            print(message)
            return
            
        tag = None
        if level == "success":
            tag = "success"
        elif level == "error":
            tag = "error"
            
        if tag:
            self.txt_log.insert(tk.END, message + "\n", tag)
        else:
            self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)

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
            
            try:
                fps = int(self.setup_tab.fps_entry.get())
            except ValueError:
                fps = 50
            codec = self.setup_tab.codec_combo.get()
            
            enabled_cams = [idx for idx, var in self.camera_enable_vars.items() if var.get() == 1]
            if not enabled_cams:
                self.log("Error: No cameras enabled for recording.", level="error")
                return
            
            self.log(f"Starting recording to: {save_dir}")
            
            # Generate session_info.json for FreeMoCap
            try:
                session_info = {
                    "fps": fps,
                    "codec": codec,
                    "resolution": self.setup_tab.res_combo.get(),
                    "charuco_dict": self.preview_tab.charuco_dict.get(),
                    "charuco_x": int(self.preview_tab.charuco_x.get()),
                    "charuco_y": int(self.preview_tab.charuco_y.get()),
                    "charuco_sq_size": float(self.preview_tab.charuco_sq_size.get()),
                    "charuco_marker_size": float(self.preview_tab.charuco_marker_size.get())
                }
                info_path = os.path.join(os.path.dirname(save_dir), "session_info.json")
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(session_info, f, indent=4)
                self.log("Generated session_info.json", "success")
            except Exception as e:
                self.log(f"Failed to generate session_info.json: {e}", "error")
            self.recorder.start_recording(save_dir, fps, codec, enabled_cams)
            self.record_start_time = time.time()
            

            
            self.preview_tab.btn_record_live.configure(text="⏹ STOP RECORDING", fg_color="red", hover_color="darkred")
        else:
            # STOP
            self.recorder.stop_recording()
            
            self.preview_tab.btn_record_live.configure(text="⏺ START RECORDING", fg_color="darkred", hover_color="red")
            self.preview_tab.lbl_live_warning.configure(text="")
            self.log("Recording stopped and saved.")

    def update_preview(self):
        self.ui_tick += 1
        
        # Check Arduino connection loss during trigger
        if self.arduino.is_running and not self.arduino.is_connected:
            self.preview_tab.lbl_live_warning.configure(text="⚠️ ARDUINO DISCONNECTED!")
            self.arduino.is_running = False
        
        if self.ui_tick % 40 == 0:
            if self.arduino.is_connected:
                if not self.arduino.ping():
                    self.preview_tab.lbl_live_warning.configure(text="⚠️ ARDUINO DISCONNECTED!")
                    self.log("Arduino ping failed! Disconnected.", "error")
                    
        if self.ui_tick % 20 == 0 or self.ui_tick == 1:
            self.last_free_space = self.get_free_space()
            
            if self.recorder.is_recording and self.last_free_space < 2:
                self.log("CRITICAL: Less than 2 GB free! Auto-stopping recording.", "error")
                self.toggle_record()
                
            if not self.recorder.is_recording:
                space_str = f"Space: {self.last_free_space} GB"
                color = "red" if self.last_free_space < 20 else ("white" if ctk.get_appearance_mode() == "Dark" else "black")
                self.preview_tab.lbl_live_stats.configure(text=f"Ready | {space_str}", text_color=color)

        if self.recorder.is_recording:
            elapsed = time.time() - self.record_start_time
            mins, secs = divmod(int(elapsed), 60)
            
            frame_counts = [w.frames_recorded for w in self.recorder.workers.values()]
            max_frames = max(frame_counts) if frame_counts else 0
            min_frames = min(frame_counts) if frame_counts else 0
            
            if max_frames - min_frames > 5:
                self.preview_tab.lbl_live_warning.configure(text=f"⚠️ SYNC WARNING: Frame drop! (Delta: {max_frames - min_frames})")
            elif not (self.arduino.is_running and not self.arduino.is_connected):
                self.preview_tab.lbl_live_warning.configure(text="")
                
            space_str = f"Space: {self.last_free_space} GB"
            color = "red" if self.last_free_space < 20 else ("white" if ctk.get_appearance_mode() == "Dark" else "black")
            if self.last_free_space < 20:
                space_str = f"⚠️ LOW SPACE: {self.last_free_space} GB"
                
            self.preview_tab.lbl_live_stats.configure(text=f"Recording 🔴 | {mins:02d}:{secs:02d} | Frames: {max_frames} | {space_str}", text_color=color)

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
                    
                    # --- FPS Overlay ---
                    fps = 0.0
                    if idx in self.recorder.workers:
                        fps = self.recorder.workers[idx].current_fps
                        
                    try:
                        target_fps = float(self.setup_tab.fps_entry.get())
                    except ValueError:
                        target_fps = 50.0
                        
                    # Determine color based on deviation
                    diff = abs(fps - target_fps)
                    if diff <= 0.5:
                        color = (0, 255, 0) # Green (Perfect)
                    elif diff <= 3.0:
                        color = (255, 255, 0) # Yellow (Slight deviation)
                    else:
                        color = (255, 0, 0) # Red (Significant deviation)
                        
                    text = f"FPS: {fps:.1f}"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    # Smaller font scale (50% smaller)
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
        self.recorder.stop_workers()
        self.arduino.disconnect()
        self.cam_mgr.close_all()
        self.destroy()

if __name__ == "__main__":
    app = MoCapSyncApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
