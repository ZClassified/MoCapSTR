import customtkinter as ctk
import tkinter as tk
import os
import threading
import av
import glob
import cv2
import json
from PIL import Image

class ExportTab(ctk.CTkFrame):
    def __init__(self, master, main_app):
        super().__init__(master)
        self.main_app = main_app
        
        self.avi_files = []
        self.is_converting = False
        self.preview_frame_bgr = None
        
        # Load saved settings
        self.settings_file = "export_settings.json"
        self.saved_rotation = "None"
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    self.saved_rotation = json.load(f).get("rotation", "None")
            except:
                pass
        
        self.build_ui()
        
    def build_ui(self):
        # Header
        self.lbl_header = ctk.CTkLabel(self, text="Post-Processing: Convert AVI to MP4", font=("Arial", 16, "bold"))
        self.lbl_header.pack(pady=(10, 5))
        
        # Info text
        info_text = "Scan the current project for raw .avi files and convert them into high-quality H.264 .mp4 files suitable for FreeMoCap."
        self.lbl_info = ctk.CTkLabel(self, text=info_text, wraplength=600)
        self.lbl_info.pack(pady=5)
        
        # Scan Button
        self.btn_scan = ctk.CTkButton(self, text="Scan Project for AVIs", command=self.scan_files)
        self.btn_scan.pack(pady=10)
        
        # File list display
        self.txt_files = ctk.CTkTextbox(self, height=150, width=600)
        self.txt_files.pack(pady=5)
        self.txt_files.insert(tk.END, "Click 'Scan' to find .avi files in the current project...\n")
        self.txt_files.configure(state="disabled")
        
        # Options
        self.delete_original_var = ctk.BooleanVar(value=False)
        self.chk_delete = ctk.CTkCheckBox(self, text="Delete original .avi after successful conversion", variable=self.delete_original_var)
        self.chk_delete.pack(pady=10)
        
        # Rotation Options and Preview
        self.preview_container = ctk.CTkFrame(self)
        self.preview_container.pack(pady=10, fill="x", padx=20)
        
        self.lbl_rot = ctk.CTkLabel(self.preview_container, text="Export Rotation:")
        self.lbl_rot.pack(side="left", padx=(10, 5))
        
        self.rot_options = ["None", "90° Clockwise", "90° Counter-Clockwise", "180°"]
        self.rot_var = ctk.StringVar(value=self.saved_rotation if self.saved_rotation in self.rot_options else "None")
        self.opt_rot = ctk.CTkOptionMenu(self.preview_container, values=self.rot_options, variable=self.rot_var, command=self.on_rotation_changed)
        self.opt_rot.pack(side="left", padx=5)
        
        self.lbl_preview = ctk.CTkLabel(self.preview_container, text="Scan to see preview", width=240, height=135, fg_color="gray20")
        self.lbl_preview.pack(side="right", padx=10, pady=5)
        
        # Convert Button
        self.btn_convert = ctk.CTkButton(self, text="Start Conversion", command=self.start_conversion, state="disabled", fg_color="green", hover_color="darkgreen")
        self.btn_convert.pack(pady=10)
        
        # Progress
        self.lbl_progress = ctk.CTkLabel(self, text="Ready")
        self.lbl_progress.pack(pady=5)
        
        self.progressbar = ctk.CTkProgressBar(self, width=600)
        self.progressbar.pack(pady=5)
        self.progressbar.set(0.0)
        
    def scan_files(self):
        if not self.main_app.proj_mgr.current_project:
            self.lbl_progress.configure(text="No active project selected. Please initialize the system first.")
            return
        project_dir = os.path.join(
            self.main_app.proj_mgr.base_path,
            self.main_app.proj_mgr.current_project
        )
        if not os.path.exists(project_dir):
            self.lbl_progress.configure(text=f"Project folder not found: {project_dir}")
            return

        # Recursive search — files are nested in takes/take_XYZ/synchronized_videos/
        self.avi_files = glob.glob(os.path.join(project_dir, "**", "*.avi"), recursive=True)
        
        self.txt_files.configure(state="normal")
        self.txt_files.delete("1.0", tk.END)
        
        if not self.avi_files:
            self.txt_files.insert(tk.END, f"No .avi files found in: {project_dir}\n")
            self.btn_convert.configure(state="disabled")
        else:
            self.txt_files.insert(tk.END, f"Found {len(self.avi_files)} .avi files in {project_dir}:\n\n")
            for f in self.avi_files:
                self.txt_files.insert(tk.END, f"- {os.path.basename(f)}\n")
            self.btn_convert.configure(state="normal")
            
        self.txt_files.configure(state="disabled")
        self.lbl_progress.configure(text=f"Found {len(self.avi_files)} files ready for conversion.")
        self.progressbar.set(0.0)
        
        self.load_first_frame()
        
    def on_rotation_changed(self, choice):
        # Save choice
        try:
            with open(self.settings_file, "w") as f:
                json.dump({"rotation": choice}, f)
        except:
            pass
        self.update_preview()
        
    def load_first_frame(self):
        self.preview_frame_bgr = None
        if not self.avi_files:
            self.lbl_preview.configure(image=None, text="No videos found")
            return
            
        try:
            container = av.open(self.avi_files[0])
            if not container.streams.video:
                return
            for frame in container.decode(video=0):
                self.preview_frame_bgr = frame.to_ndarray(format='bgr24')
                break
            container.close()
        except Exception as e:
            self.main_app.log(f"Error loading preview: {e}", "error")
            
        self.update_preview()
        
    def update_preview(self):
        if self.preview_frame_bgr is None:
            return
            
        img = self.preview_frame_bgr.copy()
        
        # Apply rotation
        rot_choice = self.rot_var.get()
        if rot_choice == "90° Clockwise":
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif rot_choice == "90° Counter-Clockwise":
            img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif rot_choice == "180°":
            img = cv2.rotate(img, cv2.ROTATE_180)
            
        # Convert to PIL
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        
        # Resize for preview, keep aspect ratio
        pil_img.thumbnail((240, 240))
        
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
        self.lbl_preview.configure(image=ctk_img, text="")
        self.lbl_preview.image = ctk_img # Keep reference
        
    def start_conversion(self):
        if not self.avi_files or self.is_converting:
            return
            
        self.is_converting = True
        self.btn_scan.configure(state="disabled")
        self.btn_convert.configure(state="disabled")
        self.chk_delete.configure(state="disabled")
        self.opt_rot.configure(state="disabled")
        
        rot_choice = self.rot_var.get()
        
        # Run conversion in a background thread
        threading.Thread(target=self._convert_thread, args=(rot_choice,), daemon=True).start()
        
    def _convert_thread(self, rot_choice):
        total_files = len(self.avi_files)
        
        for idx, input_path in enumerate(self.avi_files):
            filename = os.path.basename(input_path)
            output_filename = filename.rsplit('.', 1)[0] + '.mp4'
            output_path = os.path.join(os.path.dirname(input_path), output_filename)
            
            # Update UI (must use lambda for keyword args with self.after)
            msg = f"Converting ({idx+1}/{total_files}): {filename} -> {output_filename}"
            self.after(0, lambda t=msg: self.lbl_progress.configure(text=t))
            self.after(0, self.progressbar.set, 0.0)
            
            success = self._convert_single_file(input_path, output_path, rot_choice)
            
            if success and self.delete_original_var.get():
                try:
                    os.remove(input_path)
                    self.main_app.log(f"Deleted original file: {filename}")
                except Exception as e:
                    self.main_app.log(f"Could not delete original {filename}: {e}", "error")
                    
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
            self.main_app.log(f"Successfully converted {os.path.basename(input_path)}")
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
        self.lbl_progress.configure(text="Conversion finished!")
        self.progressbar.set(1.0)
        self.btn_scan.configure(state="normal")
        self.chk_delete.configure(state="normal")
        self.opt_rot.configure(state="normal")
        
        # Rescan to reflect changes
        self.scan_files()
