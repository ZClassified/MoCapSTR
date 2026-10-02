import customtkinter as ctk
import tkinter as tk
import os
import threading
import av
import glob
import cv2
import json
import re
import shutil
from PIL import Image

import freemocap_bridge
from freemocap_bridge import SYNCHRONIZED_VIDEOS_FOLDER

RAW_VIDEO_EXTENSIONS = (".avi", ".mkv")   # as written by the recorder (MJPEG stream copy)
ORIGINALS_FOLDER = "original_videos"      # converted originals are moved here (outside synchronized_videos/)

class ExportTab(ctk.CTkFrame):
    def __init__(self, master, main_app):
        super().__init__(master)
        self.main_app = main_app
        
        self.recordings = []   # recording folders of the current project
        self.raw_files = []    # .avi/.mkv in synchronized_videos/
        self.mp4_files = []
        self.detected_cam_ids = []
        self.is_converting = False
        
        self.preview_frames_bgr = {} # cam_id (str) -> bgr frame ndarray
        self.cam_preview_labels = {} # cam_id (str) -> CTkLabel
        self.cam_rot_vars = {}        # cam_id (str) -> StringVar
        self.cam_rot_menus = {}       # cam_id (str) -> CTkOptionMenu
        
        self.rot_options = ["None", "90° Clockwise", "90° Counter-Clockwise", "180°"]
        self.cam_rotations = {}       # cam_id (str) -> rotation choice
        self.global_saved_rot = "None"
        
        self.settings_file = "export_settings.json"
        
        self.load_settings()
        self.build_ui()
        
    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "cam_rotations" in data and isinstance(data["cam_rotations"], dict):
                        self.cam_rotations = data["cam_rotations"]
                    if "global_rotation" in data and data["global_rotation"] in self.rot_options:
                        self.global_saved_rot = data["global_rotation"]
                    elif "rotation" in data and data["rotation"] in self.rot_options:
                        self.global_saved_rot = data["rotation"]
            except Exception as e:
                print(f"Error loading export settings: {e}")

    def save_settings(self):
        try:
            data = {
                "global_rotation": self.global_rot_var.get() if hasattr(self, 'global_rot_var') else self.global_saved_rot,
                "cam_rotations": self.cam_rotations
            }
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving export settings: {e}")
            
    def _get_cam_id_from_path(self, filepath):
        filename = os.path.basename(filepath).lower()
        match = re.search(r'cam(\d+)', filename)
        if match:
            return match.group(1)
        return None

    def build_ui(self):
        # Header
        self.lbl_header = ctk.CTkLabel(self, text="Post-Processing & FreeMoCap Export", font=("Arial", 16, "bold"))
        self.lbl_header.pack(pady=(10, 5))
        
        # Info text
        info_text = ("Scan the current project for recordings. FreeMoCap 2 reads the raw .avi/.mkv files directly - "
                     "conversion to H.264 .mp4 is only needed for rotation or smaller files.")
        self.lbl_info = ctk.CTkLabel(self, text=info_text, wraplength=650)
        self.lbl_info.pack(pady=5)
        
        # Scan Button
        self.btn_scan = ctk.CTkButton(self, text="Scan Project Files", command=self.scan_files)
        self.btn_scan.pack(pady=6)
        
        # File list display
        self.txt_files = ctk.CTkTextbox(self, height=110, width=650)
        self.txt_files.pack(pady=4)
        self.txt_files.insert(tk.END, "Click 'Scan Project Files' to find recordings and detect cameras...\n")
        self.txt_files.configure(state="disabled")
        
        # Options: Delete original
        self.delete_original_var = ctk.BooleanVar(value=False)
        self.chk_delete = ctk.CTkCheckBox(self, text="Delete originals after conversion (otherwise moved to original_videos/)", variable=self.delete_original_var)
        self.chk_delete.pack(pady=4)
        
        # --- PER-CAMERA ROTATION & PREVIEW CONTAINER ---
        self.rot_card = ctk.CTkFrame(self)
        self.rot_card.pack(pady=6, fill="x", padx=20)
        
        # Top toolbar of Rotation card
        self.rot_toolbar = ctk.CTkFrame(self.rot_card, fg_color="transparent")
        self.rot_toolbar.pack(fill="x", padx=10, pady=(6, 4))
        
        self.lbl_rot_title = ctk.CTkLabel(self.rot_toolbar, text="Camera Rotations:", font=ctk.CTkFont(weight="bold", size=13))
        self.lbl_rot_title.pack(side="left", padx=5)
        
        self.btn_sync_live = ctk.CTkButton(
            self.rot_toolbar,
            text="🔄 Sync from Live Preview",
            width=170,
            command=self.sync_from_live_preview,
            fg_color="#3a4f66",
            hover_color="#2b3b4d"
        )
        self.btn_sync_live.pack(side="left", padx=10)
        
        self.opt_apply_all = ctk.CTkOptionMenu(
            self.rot_toolbar,
            values=["Apply to All...", "All: None", "All: 90° Clockwise", "All: 90° Counter-Clockwise", "All: 180°"],
            command=self.on_apply_all_rotation,
            width=160
        )
        self.opt_apply_all.set("Apply to All...")
        self.opt_apply_all.pack(side="right", padx=5)
        
        # Fallback / Default Global Rotation for non-camX files
        self.global_rot_var = ctk.StringVar(value=self.global_saved_rot)
        
        # Scrollable container for individual camera cards
        self.cam_scroll_frame = ctk.CTkScrollableFrame(self.rot_card, height=170, orientation="horizontal")
        self.cam_scroll_frame.pack(fill="x", padx=10, pady=(0, 8))
        
        self.lbl_placeholder = ctk.CTkLabel(
            self.cam_scroll_frame,
            text="Scan project files to load per-camera rotation controls and thumbnails.",
            text_color="gray70"
        )
        self.lbl_placeholder.pack(pady=40, padx=20)
        
        # --- ACTION BUTTONS CONTAINER ---
        self.btn_container = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_container.pack(pady=8)
        
        self.btn_convert = ctk.CTkButton(
            self.btn_container,
            text="Start Conversion (.mp4)",
            command=self.start_conversion,
            state="disabled",
            fg_color="#1f538d",
            hover_color="#14375e"
        )
        self.btn_convert.pack(side="left", padx=8)
        
        self.btn_freemocap = ctk.CTkButton(
            self.btn_container,
            text="🚀 Open in FreeMoCap",
            command=self.start_freemocap_workflow,
            state="disabled",
            fg_color="#2e7d32",
            hover_color="#1b5e20"
        )
        self.btn_freemocap.pack(side="left", padx=8)
        
        # Progress
        self.lbl_progress = ctk.CTkLabel(self, text="Ready")
        self.lbl_progress.pack(pady=2)
        
        self.progressbar = ctk.CTkProgressBar(self, width=650)
        self.progressbar.pack(pady=4)
        self.progressbar.set(0.0)

    def scan_files(self):
        project = self.main_app.proj_mgr.current_project or self.main_app.setup_tab.proj_name_entry.get().strip()
        if not project:
            self.lbl_progress.configure(text="Enter a project name in the Setup tab first.")
            return
        project_dir = self.main_app.proj_mgr.base_path
        self.recordings = self.main_app.proj_mgr.find_recordings(project)

        self.raw_files = []
        self.mp4_files = []
        for recording in self.recordings:
            folder = os.path.join(recording, SYNCHRONIZED_VIDEOS_FOLDER)
            for name in sorted(os.listdir(folder)):
                path = os.path.join(folder, name)
                ext = os.path.splitext(name)[1].lower()
                if not os.path.isfile(path):
                    continue
                if ext in RAW_VIDEO_EXTENSIONS:
                    self.raw_files.append(path)
                elif ext == ".mp4":
                    self.mp4_files.append(path)

        self.txt_files.configure(state="normal")
        self.txt_files.delete("1.0", tk.END)
        
        if not self.raw_files and not self.mp4_files:
            self.txt_files.insert(tk.END, f"No recordings of project '{project}' found in: {project_dir}\n")
            self.btn_convert.configure(state="disabled")
            self.btn_freemocap.configure(state="disabled")
            self.lbl_progress.configure(text="No video files found.")
            self.detected_cam_ids = []
            self.update_camera_grid_ui()
        else:
            if self.raw_files:
                self.txt_files.insert(tk.END, f"Found {len(self.raw_files)} raw files (.avi/.mkv, usable by FreeMoCap):\n")
                for f in self.raw_files:
                    self.txt_files.insert(tk.END, f"  • {os.path.basename(f)}  ({os.path.relpath(f, project_dir)})\n")
                self.btn_convert.configure(state="normal")
            else:
                self.btn_convert.configure(state="disabled")
                
            if self.mp4_files:
                self.txt_files.insert(tk.END, f"\nFound {len(self.mp4_files)} .mp4 files (ready):\n")
                for f in self.mp4_files:
                    self.txt_files.insert(tk.END, f"  • {os.path.basename(f)}  ({os.path.relpath(f, project_dir)})\n")
                    
            self.btn_freemocap.configure(state="normal")
            
            if self.raw_files:
                self.lbl_progress.configure(text=f"{len(self.recordings)} recording(s), {len(self.raw_files)} raw file(s).")
            else:
                self.lbl_progress.configure(text=f"All files converted ({len(self.mp4_files)} MP4s ready).")
                
            # Extract unique camera IDs from all found files
            found_ids = set()
            for f in (self.raw_files + self.mp4_files):
                cid = self._get_cam_id_from_path(f)
                if cid is not None:
                    found_ids.add(cid)
            
            try:
                self.detected_cam_ids = sorted(list(found_ids), key=lambda x: int(x))
            except ValueError:
                self.detected_cam_ids = sorted(list(found_ids))
                
            self.load_camera_preview_frames()
            self.update_camera_grid_ui()
                
        self.txt_files.configure(state="disabled")
        self.progressbar.set(0.0)

    def load_camera_preview_frames(self):
        self.preview_frames_bgr.clear()
        
        # For each detected camera ID, find the first available video file
        for cid in self.detected_cam_ids:
            cam_file = None
            for f in self.raw_files:
                if self._get_cam_id_from_path(f) == cid:
                    cam_file = f
                    break
            if not cam_file:
                for f in self.mp4_files:
                    if self._get_cam_id_from_path(f) == cid:
                        cam_file = f
                        break
            if cam_file:
                try:
                    container = av.open(cam_file)
                    if container.streams.video:
                        for frame in container.decode(video=0):
                            self.preview_frames_bgr[cid] = frame.to_ndarray(format='bgr24')
                            break
                    container.close()
                except Exception as e:
                    self.main_app.log(f"Could not load preview frame for Cam {cid}: {e}", "error")

        # Fallback if no specific cam_id was parsed but files exist
        if not self.preview_frames_bgr and (self.raw_files or self.mp4_files):
            fallback_file = self.raw_files[0] if self.raw_files else self.mp4_files[0]
            try:
                container = av.open(fallback_file)
                if container.streams.video:
                    for frame in container.decode(video=0):
                        self.preview_frames_bgr["global"] = frame.to_ndarray(format='bgr24')
                        break
                container.close()
            except Exception:
                pass

    def update_camera_grid_ui(self):
        # Clear existing widgets in scroll frame
        for widget in self.cam_scroll_frame.winfo_children():
            widget.destroy()
            
        self.cam_preview_labels.clear()
        self.cam_rot_vars.clear()
        self.cam_rot_menus.clear()
        
        if not self.detected_cam_ids:
            if "global" in self.preview_frames_bgr:
                # Single fallback card
                card = ctk.CTkFrame(self.cam_scroll_frame, fg_color="gray25", corner_radius=8)
                card.pack(side="left", padx=10, pady=5)
                
                ctk.CTkLabel(card, text="All Cameras (Global)", font=ctk.CTkFont(weight="bold")).pack(pady=(5, 2))
                
                opt = ctk.CTkOptionMenu(
                    card,
                    values=self.rot_options,
                    variable=self.global_rot_var,
                    command=lambda c: self.on_global_rotation_changed(c),
                    width=150
                )
                opt.pack(pady=4, padx=10)
                
                lbl_prev = ctk.CTkLabel(card, text="Preview", width=140, height=90, fg_color="black")
                lbl_prev.pack(pady=(2, 6), padx=10)
                self.cam_preview_labels["global"] = lbl_prev
                self.update_single_preview("global")
            else:
                lbl = ctk.CTkLabel(
                    self.cam_scroll_frame,
                    text="Scan project files to load per-camera rotation controls and thumbnails.",
                    text_color="gray70"
                )
                lbl.pack(pady=40, padx=20)
            return

        # Render a card for each detected camera
        for cid in self.detected_cam_ids:
            card = ctk.CTkFrame(self.cam_scroll_frame, fg_color="gray25", corner_radius=8)
            card.pack(side="left", padx=8, pady=4)
            
            # Title
            lbl_title = ctk.CTkLabel(card, text=f"Camera {cid} (cam{cid})", font=ctk.CTkFont(weight="bold", size=12))
            lbl_title.pack(pady=(4, 2), padx=8)
            
            # Rotation choice
            initial_rot = self.cam_rotations.get(cid, self.global_saved_rot)
            if initial_rot not in self.rot_options:
                initial_rot = "None"
            self.cam_rotations[cid] = initial_rot
            
            var = ctk.StringVar(value=initial_rot)
            self.cam_rot_vars[cid] = var
            
            def make_cmd(cam_id):
                return lambda choice: self.on_cam_rotation_changed(cam_id, choice)
                
            opt = ctk.CTkOptionMenu(card, values=self.rot_options, variable=var, command=make_cmd(cid), width=150)
            opt.pack(pady=2, padx=8)
            self.cam_rot_menus[cid] = opt
            
            # Preview Thumbnail
            lbl_prev = ctk.CTkLabel(card, text="No Preview", width=140, height=90, fg_color="black")
            lbl_prev.pack(pady=(2, 6), padx=8)
            self.cam_preview_labels[cid] = lbl_prev
            
            self.update_single_preview(cid)

    def on_cam_rotation_changed(self, cam_id, choice):
        self.cam_rotations[cam_id] = choice
        self.save_settings()
        self.update_single_preview(cam_id)

    def on_global_rotation_changed(self, choice):
        self.global_saved_rot = choice
        self.save_settings()
        self.update_single_preview("global")

    def on_apply_all_rotation(self, choice):
        if not choice.startswith("All: "):
            return
        rot_val = choice.replace("All: ", "").strip()
        if rot_val in self.rot_options:
            self.global_saved_rot = rot_val
            self.global_rot_var.set(rot_val)
            for cid in self.detected_cam_ids:
                self.cam_rotations[cid] = rot_val
                if cid in self.cam_rot_vars:
                    self.cam_rot_vars[cid].set(rot_val)
                self.update_single_preview(cid)
            self.save_settings()
            self.main_app.log(f"Applied rotation '{rot_val}' to all cameras.", "info")
        self.opt_apply_all.set("Apply to All...")

    def sync_from_live_preview(self):
        """Reads rotation settings currently configured in the Live Preview tab and applies them."""
        # PreviewTab values: ["0°", "90° (Portrait)", "180°", "270° (Portrait)"]
        preview_to_export_map = {
            "0°": "None",
            "90° (Portrait)": "90° Clockwise",
            "180°": "180°",
            "270° (Portrait)": "90° Counter-Clockwise"
        }
        
        synced_count = 0
        if hasattr(self.main_app, 'rotation_menus') and self.main_app.rotation_menus:
            for cam_idx, menu in self.main_app.rotation_menus.items():
                cid = str(cam_idx)
                try:
                    val = menu.get()
                    export_val = preview_to_export_map.get(val, "None")
                    self.cam_rotations[cid] = export_val
                    if cid in self.cam_rot_vars:
                        self.cam_rot_vars[cid].set(export_val)
                    if cid in self.cam_preview_labels:
                        self.update_single_preview(cid)
                    synced_count += 1
                except Exception:
                    pass
                    
        if synced_count > 0:
            self.save_settings()
            self.main_app.log(f"Synced {synced_count} camera rotation(s) from Live Preview!", "success")
        else:
            self.main_app.log("No active rotation menus found in Live Preview to sync.", "warning")

    def update_single_preview(self, cam_id):
        if cam_id not in self.cam_preview_labels:
            return
        
        frame_bgr = self.preview_frames_bgr.get(cam_id)
        if frame_bgr is None:
            self.cam_preview_labels[cam_id].configure(image=None, text="No Frame")
            return
            
        img = frame_bgr.copy()
        rot_choice = self.cam_rotations.get(cam_id, self.global_rot_var.get())
        
        if rot_choice == "90° Clockwise":
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif rot_choice == "90° Counter-Clockwise":
            img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif rot_choice == "180°":
            img = cv2.rotate(img, cv2.ROTATE_180)
            
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        pil_img.thumbnail((140, 90))
        
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
        self.cam_preview_labels[cam_id].configure(image=ctk_img, text="")
        self.cam_preview_labels[cam_id].image = ctk_img

    def start_conversion(self):
        if not self.raw_files or self.is_converting:
            return
        self._start_workflow(send_to_freemocap=False)
        
    def start_freemocap_workflow(self):
        if self.is_converting:
            return
        if not self.recordings:
            return
        self._start_workflow(send_to_freemocap=True)
        
    def _start_workflow(self, send_to_freemocap=False):
        self.is_converting = True
        self.btn_scan.configure(state="disabled")
        self.btn_convert.configure(state="disabled")
        self.btn_freemocap.configure(state="disabled")
        self.chk_delete.configure(state="disabled")
        self.btn_sync_live.configure(state="disabled")
        self.opt_apply_all.configure(state="disabled")
        for menu in self.cam_rot_menus.values():
            menu.configure(state="disabled")
            
        threading.Thread(target=self._worker_thread, args=(send_to_freemocap,), daemon=True).start()
        
    def _rotation_for(self, path):
        return self.cam_rotations.get(self._get_cam_id_from_path(path), self.global_rot_var.get())

    def _retire_original(self, raw_path):
        """After a successful conversion only the .mp4 may stay in synchronized_videos/:
        FreeMoCap counts every video file there as a separate camera."""
        try:
            if self.delete_original_var.get():
                os.remove(raw_path)
                self.main_app.log(f"Deleted original file: {os.path.basename(raw_path)}")
            else:
                recording_dir = os.path.dirname(os.path.dirname(raw_path))
                target_dir = os.path.join(recording_dir, ORIGINALS_FOLDER)
                os.makedirs(target_dir, exist_ok=True)
                target = os.path.join(target_dir, os.path.basename(raw_path))
                if os.path.exists(target):
                    os.remove(target)
                shutil.move(raw_path, target)
        except OSError as e:
            self.main_app.log(f"Could not move/delete original {os.path.basename(raw_path)}: {e}", "error")

    def _worker_thread(self, send_to_freemocap=False):
        # Step 1: Convert raw files. When sending to FreeMoCap, only cameras that need
        # a rotation are converted - FreeMoCap 2 reads the raw .avi/.mkv files directly.
        if send_to_freemocap:
            to_convert = [f for f in self.raw_files if self._rotation_for(f) != "None"]
        else:
            to_convert = list(self.raw_files)
        total_files = len(to_convert)

        for idx, input_path in enumerate(to_convert):
            filename = os.path.basename(input_path)
            output_filename = filename.rsplit('.', 1)[0] + '.mp4'
            output_path = os.path.join(os.path.dirname(input_path), output_filename)

            rot_choice = self._rotation_for(input_path)

            msg = f"Converting ({idx+1}/{total_files}): {filename} [Rot: {rot_choice}] -> {output_filename}"
            self.after(0, lambda t=msg: self.lbl_progress.configure(text=t))
            self.after(0, self.progressbar.set, 0.0)

            if self._convert_single_file(input_path, output_path, rot_choice):
                self._retire_original(input_path)

        # Step 2: Make the recordings available in FreeMoCap and start it
        if send_to_freemocap:
            self.after(0, lambda: self.lbl_progress.configure(text="Opening FreeMoCap..."))
            for recording in self.recordings:
                try:
                    target = freemocap_bridge.export_recording(recording)
                except OSError as e:
                    self.main_app.log(f"Export of {os.path.basename(recording)} failed: {e}", "error")
                    continue
                if target and os.path.normcase(target) != os.path.normcase(recording):
                    self.main_app.log(f"Copied to FreeMoCap: {os.path.basename(target)}", "success")

            recordings_folder = freemocap_bridge.get_freemocap_recordings_folder()
            if freemocap_bridge.launch_freemocap():
                self.main_app.log(f"FreeMoCap started. Recordings are in {recordings_folder}", "success")
            else:
                self.main_app.log("FreeMoCap 2 not found (expected in %LOCALAPPDATA%\\Programs\\freemocap). "
                                  f"Recordings are ready in {recordings_folder}", "info")

        self.after(0, self._conversion_finished)

    def _convert_single_file(self, input_path, output_path, rot_choice):
        try:
            input_container = av.open(input_path)
            if not input_container.streams.video:
                self.main_app.log(f"No video stream found in {input_path}", "error")
                return False
                
            in_stream = input_container.streams.video[0]
            
            # Use original framerate or fallback to 30
            fps = in_stream.average_rate
            if not fps or fps == 0:
                fps = 30
                
            output_container = av.open(output_path, mode='w')
            out_stream = output_container.add_stream('libx264', rate=fps)
            
            # Swap dimensions if rotating 90 degrees
            if rot_choice in ["90° Clockwise", "90° Counter-Clockwise"]:
                out_stream.width = in_stream.height
                out_stream.height = in_stream.width
            else:
                out_stream.width = in_stream.width
                out_stream.height = in_stream.height
                
            out_stream.pix_fmt = 'yuv420p'
            out_stream.options = {'crf': '15', 'preset': 'fast'} # Visually lossless H.264
            
            total_frames = in_stream.frames
            if total_frames <= 0:
                # Estimate from duration
                if input_container.duration:
                    total_frames = int(float(input_container.duration) / av.time_base * float(fps))
                else:
                    total_frames = 1000 # dummy fallback
                    
            frames_processed = 0
            
            for frame in input_container.decode(video=0):
                if rot_choice != "None":
                    img = frame.to_ndarray(format='bgr24')
                    if rot_choice == "90° Clockwise":
                        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                    elif rot_choice == "90° Counter-Clockwise":
                        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    elif rot_choice == "180°":
                        img = cv2.rotate(img, cv2.ROTATE_180)
                    
                    new_frame = av.VideoFrame.from_ndarray(img, format='bgr24')
                    new_frame.pts = frame.pts
                    new_frame.time_base = frame.time_base
                    frame = new_frame

                for packet in out_stream.encode(frame):
                    output_container.mux(packet)
                    
                frames_processed += 1
                if frames_processed % 30 == 0:
                    progress = min(1.0, frames_processed / max(1, total_frames))
                    self.after(0, self.progressbar.set, progress)
                    
            # Flush encoder
            for packet in out_stream.encode():
                output_container.mux(packet)
                
            input_container.close()
            output_container.close()
            
            self.after(0, self.progressbar.set, 1.0)
            self.main_app.log(f"Successfully converted {os.path.basename(input_path)} [Rot: {rot_choice}]")
            return True
            
        except Exception as e:
            # Clean up output file if it was partially created
            if 'output_container' in dir() and output_container:
                try:
                    output_container.close()
                except Exception:
                    pass
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            self.main_app.log(f"Error converting {os.path.basename(input_path)}: {e}", "error")
            return False

    def _conversion_finished(self):
        self.is_converting = False
        self.lbl_progress.configure(text="Process finished!")
        self.progressbar.set(1.0)
        self.btn_scan.configure(state="normal")
        self.chk_delete.configure(state="normal")
        self.btn_sync_live.configure(state="normal")
        self.opt_apply_all.configure(state="normal")
        for menu in self.cam_rot_menus.values():
            menu.configure(state="normal")
            
        # Rescan to reflect changes
        self.scan_files()
