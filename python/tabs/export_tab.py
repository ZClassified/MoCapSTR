import customtkinter as ctk
import tkinter as tk
import os
import threading
import av
import glob

class ExportTab(ctk.CTkFrame):
    def __init__(self, master, main_app):
        super().__init__(master)
        self.main_app = main_app
        
        self.avi_files = []
        self.is_converting = False
        
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
        project_dir = self.main_app.proj_mgr.current_project_dir()
        if not project_dir or not os.path.exists(project_dir):
            self.lbl_progress.configure(text="No active project selected.")
            return
            
        search_pattern = os.path.join(project_dir, "*.avi")
        self.avi_files = glob.glob(search_pattern)
        
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
        
    def start_conversion(self):
        if not self.avi_files or self.is_converting:
            return
            
        self.is_converting = True
        self.btn_scan.configure(state="disabled")
        self.btn_convert.configure(state="disabled")
        self.chk_delete.configure(state="disabled")
        
        # Run conversion in a background thread
        threading.Thread(target=self._convert_thread, daemon=True).start()
        
    def _convert_thread(self):
        total_files = len(self.avi_files)
        
        for idx, input_path in enumerate(self.avi_files):
            filename = os.path.basename(input_path)
            output_filename = filename.rsplit('.', 1)[0] + '.mp4'
            output_path = os.path.join(os.path.dirname(input_path), output_filename)
            
            # Update UI
            self.after(0, self.lbl_progress.configure, text=f"Converting ({idx+1}/{total_files}): {filename} -> {output_filename}")
            self.after(0, self.progressbar.set, 0.0)
            
            success = self._convert_single_file(input_path, output_path)
            
            if success and self.delete_original_var.get():
                try:
                    os.remove(input_path)
                    self.main_app.log(f"Deleted original file: {filename}")
                except Exception as e:
                    self.main_app.log(f"Could not delete original {filename}: {e}", "error")
                    
        self.after(0, self._conversion_finished)
        
    def _convert_single_file(self, input_path, output_path):
        try:
            input_container = av.open(input_path)
            if not input_container.streams.video:
                self.main_app.log(f"No video stream found in {input_path}", "error")
                return False
                
            in_stream = input_container.streams.video[0]
            
            # Use original framerate or fallback to 50
            fps = in_stream.average_rate
            if not fps or fps == 0:
                fps = 50
                
            output_container = av.open(output_path, mode='w')
            out_stream = output_container.add_stream('libx264', rate=fps)
            out_stream.width = in_stream.width
            out_stream.height = in_stream.height
            out_stream.pix_fmt = 'yuv420p'
            out_stream.options = {'crf': '23', 'preset': 'fast'} # High quality H.264
            
            total_frames = in_stream.frames
            if total_frames <= 0:
                # Estimate from duration
                if input_container.duration:
                    total_frames = int(float(input_container.duration) / av.time_base * float(fps))
                else:
                    total_frames = 1000 # dummy fallback
                    
            frames_processed = 0
            
            for frame in input_container.decode(video=0):
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
            self.main_app.log(f"Error converting {os.path.basename(input_path)}: {e}", "error")
            return False

    def _conversion_finished(self):
        self.is_converting = False
        self.lbl_progress.configure(text="Conversion finished!")
        self.progressbar.set(1.0)
        self.btn_scan.configure(state="normal")
        self.chk_delete.configure(state="normal")
        
        # Rescan to reflect changes
        self.scan_files()
