import tkinter as tk
import customtkinter as ctk
from camera_manager import CameraManager
from arduino_sync import ArduinoSync
from project_manager import ProjectManager
from recorder import MultiCamManager
import cv2
from PIL import Image, ImageTk
import threading
import os
from tkinter import filedialog

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MoCapSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OV9281 MoCap Recording Station")
        self.geometry("1100x800")
        
        # Managers
        self.cam_mgr = CameraManager()
        self.arduino = ArduinoSync()
        self.proj_mgr = ProjectManager()
        self.recorder = MultiCamManager()
        
        self.camera_indices = []
        self.preview_labels = {} # Grid for previews
        
        self.build_ui()
        self.after(50, self.update_preview) # Start preview loop
        
    def build_ui(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_setup = self.tabview.add("1. Setup & Cameras")
        self.tab_record = self.tabview.add("2. Project & Recording")
        self.tab_preview = self.tabview.add("3. Live Preview")
        
        self.build_setup_tab(self.tab_setup)
        self.build_record_tab(self.tab_record)
        self.build_preview_tab(self.tab_preview)

    # --- TAB 1: SETUP ---
    def build_setup_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        
        left = ctk.CTkFrame(parent, fg_color="transparent")
        left.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        # Cameras
        ctk.CTkLabel(left, text="Camera Setup", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 10))
        
        # Backend Selector
        backend_frame = ctk.CTkFrame(left, fg_color="transparent")
        backend_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(backend_frame, text="Backend:").pack(side="left")
        self.backend_combo = ctk.CTkComboBox(backend_frame, values=["DSHOW", "MSMF", "ANY"], width=100)
        self.backend_combo.set("DSHOW")
        self.backend_combo.pack(side="right")
        
        self.btn_scan = ctk.CTkButton(left, text="Scan & Open Cameras", command=self.scan_cameras)
        self.btn_scan.pack(fill="x", pady=5)
        self.lbl_cams_found = ctk.CTkLabel(left, text="Cameras found: 0")
        self.lbl_cams_found.pack(anchor="w")

        ctk.CTkLabel(left, text="Resolution:").pack(anchor="w", pady=(10, 0))
        res_options = ["3840x2160 (4K)", "2560x1440 (1440p)", "1920x1080 (1080p)", "1280x800", "1280x720 (720p)", "1024x768", "800x600", "640x480", "640x400", "320x240"]
        self.res_combo = ctk.CTkComboBox(left, values=res_options)
        self.res_combo.set("1280x720 (720p)")
        self.res_combo.pack(fill="x")

        self.lbl_exposure = ctk.CTkLabel(left, text="Exposure (Shutter Speed): 1/32s")
        self.lbl_exposure.pack(anchor="w", pady=(10, 0))
        self.exposure_slider = ctk.CTkSlider(left, from_=-11, to=-3, number_of_steps=8, command=self.update_exposure_label)
        self.exposure_slider.set(-5)
        self.exposure_slider.pack(fill="x")
        
        self.lbl_gain = ctk.CTkLabel(left, text="Gain: 0")
        self.lbl_gain.pack(anchor="w", pady=(10, 0))
        self.gain_slider = ctk.CTkSlider(left, from_=0, to=255, command=self.update_gain_label)
        self.gain_slider.set(0)
        self.gain_slider.pack(fill="x")
        
        self.lbl_wb = ctk.CTkLabel(left, text="White Balance: 4000K")
        self.lbl_wb.pack(anchor="w", pady=(10, 0))
        self.wb_slider = ctk.CTkSlider(left, from_=2000, to=8000, command=self.update_wb_label)
        self.wb_slider.set(4000)
        self.wb_slider.pack(fill="x")
        self.btn_apply_cams = ctk.CTkButton(left, text="Apply Camera Settings", command=self.apply_camera_settings)
        self.btn_apply_cams.pack(fill="x", pady=15)
        
        # Arduino
        ctk.CTkLabel(right, text="Arduino Hardware Sync", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 10))
        ports = ArduinoSync.get_available_ports()
        self.port_combo = ctk.CTkComboBox(right, values=ports if ports else ["No Ports Found"])
        self.port_combo.pack(fill="x", pady=5)
        
        self.btn_connect = ctk.CTkButton(right, text="Connect Arduino", command=self.connect_arduino)
        self.btn_connect.pack(fill="x", pady=5)
        
        ctk.CTkLabel(right, text="Target Framerate (FPS):").pack(anchor="w", pady=(10, 0))
        self.fps_entry = ctk.CTkEntry(right)
        self.fps_entry.insert(0, "60")
        self.fps_entry.pack(fill="x")
        
        self.btn_start_sync = ctk.CTkButton(right, text="START HARDWARE TRIGGER", fg_color="green", hover_color="darkgreen", command=self.start_sync, state="disabled")
        self.btn_start_sync.pack(fill="x", pady=10)
        self.btn_stop_sync = ctk.CTkButton(right, text="STOP HARDWARE TRIGGER", fg_color="red", hover_color="darkred", command=self.stop_sync, state="disabled")
        self.btn_stop_sync.pack(fill="x", pady=5)
        
        # Log
        self.txt_log = ctk.CTkTextbox(parent, height=150)
        self.txt_log.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=20)
        self.log("Welcome to MoCap Recording Station.")

    # --- TAB 2: RECORDING ---
    def build_record_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        
        # Project Config
        frame_proj = ctk.CTkFrame(parent)
        frame_proj.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame_proj, text="Project Settings", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10,0))
        
        # Save Directory
        ctk.CTkLabel(frame_proj, text="Base Save Directory:").pack(anchor="w", padx=10, pady=(10,0))
        dir_frame = ctk.CTkFrame(frame_proj, fg_color="transparent")
        dir_frame.pack(fill="x", padx=10, pady=5)
        self.lbl_save_dir = ctk.CTkLabel(dir_frame, text=self.proj_mgr.base_path, text_color="gray")
        self.lbl_save_dir.pack(side="left", fill="x", expand=True, padx=(0,10))
        self.btn_browse = ctk.CTkButton(dir_frame, text="Browse...", width=100, command=self.browse_directory)
        self.btn_browse.pack(side="right")
        
        ctk.CTkLabel(frame_proj, text="Project Name (e.g. LivingRoom_Setup_1):").pack(anchor="w", padx=10, pady=(15,0))
        self.proj_name_entry = ctk.CTkEntry(frame_proj)
        self.proj_name_entry.insert(0, "My_MoCap_Project")
        self.proj_name_entry.pack(fill="x", padx=10, pady=(0, 10))
        
        # Recording Config
        frame_rec = ctk.CTkFrame(parent)
        frame_rec.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame_rec, text="Recording Setup", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10,0))
        
        ctk.CTkLabel(frame_rec, text="Video Codec:").pack(anchor="w", padx=10)
        self.codec_combo = ctk.CTkComboBox(frame_rec, values=list(self.recorder.get_supported_codecs().keys()))
        self.codec_combo.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(frame_rec, text="Record Type:").pack(anchor="w", padx=10)
        self.record_type = ctk.StringVar(value="motion")
        ctk.CTkRadioButton(frame_rec, text="Motion Take (Normal)", variable=self.record_type, value="motion").pack(anchor="w", padx=10, pady=5)
        ctk.CTkRadioButton(frame_rec, text="Calibration (Charuco)", variable=self.record_type, value="calibration").pack(anchor="w", padx=10, pady=5)
        
        # Big Record Buttons
        self.btn_record = ctk.CTkButton(parent, text="⏺ START RECORDING", fg_color="darkred", hover_color="red", height=60, font=ctk.CTkFont(size=24, weight="bold"), command=self.toggle_record)
        self.btn_record.pack(fill="x", padx=10, pady=20)

    # --- TAB 3: PREVIEW ---
    def build_preview_tab(self, parent):
        # We will dynamically create a grid of up to 6 labels
        self.preview_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.preview_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        for i in range(2):
            self.preview_frame.grid_rowconfigure(i, weight=1)
        for j in range(3):
            self.preview_frame.grid_columnconfigure(j, weight=1)
            
    # --- LOGIC ---
    def browse_directory(self):
        new_dir = filedialog.askdirectory(title="Select MoCap Save Directory", initialdir=self.proj_mgr.base_path)
        if new_dir:
            self.proj_mgr.set_base_path(new_dir)
            self.lbl_save_dir.configure(text=new_dir)
            self.log(f"Base save directory set to: {new_dir}")

    def update_exposure_label(self, value):
        val = int(value)
        denominator = 2 ** abs(val)
        self.lbl_exposure.configure(text=f"Exposure (Shutter Speed): 1/{denominator}s")

    def update_gain_label(self, value):
        self.lbl_gain.configure(text=f"Gain: {int(value)}")
        
    def update_wb_label(self, value):
        self.lbl_wb.configure(text=f"White Balance: {int(value)}K")

    def log(self, message):
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)

    def scan_cameras(self):
        self.log("Scanning for cameras (this may take a few seconds)...")
        self.btn_scan.configure(state="disabled")
        
        # WICHTIG: Stoppe alte Aufnahme-Threads, bevor wir Kameras schließen/öffnen!
        # Sonst greifen Threads auf geschlossene Kamera-Handles zu -> Freeze.
        self.recorder.stop_workers()
        
        def scan():
            backend = self.backend_combo.get()
            self.camera_indices = self.cam_mgr.find_and_open_cameras(6, backend_name=backend)
            self.lbl_cams_found.configure(text=f"Cameras found: {len(self.camera_indices)} ({self.camera_indices})")
                
            # Setup preview grid
            for widget in self.preview_frame.winfo_children():
                widget.destroy()
            self.preview_labels.clear()
            
            for i, idx in enumerate(self.camera_indices):
                row = i // 3
                col = i % 3
                
                # Container for this camera
                cam_frame = ctk.CTkFrame(self.preview_frame)
                cam_frame.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
                cam_frame.grid_rowconfigure(0, weight=1)
                cam_frame.grid_columnconfigure(0, weight=1)
                
                # Label for video
                lbl = tk.Label(cam_frame, bg="black")
                lbl.grid(row=0, column=0, sticky="nsew")
                self.preview_labels[idx] = lbl
                
                # Rotation Dropdown
                def make_rot_callback(cam_id):
                    def callback(choice):
                        deg = int(choice.split('°')[0])
                        self.recorder.set_camera_rotation(cam_id, deg)
                    return callback
                
                rot_menu = ctk.CTkOptionMenu(cam_frame, values=["0°", "90° (Portrait)", "180°", "270° (Portrait)"], command=make_rot_callback(idx))
                rot_menu.set("0°")
                rot_menu.grid(row=1, column=0, pady=2, sticky="ew")
                
            self.btn_scan.configure(state="normal")
            
            # Start background grabbing threads
            self.recorder.start_workers(self.cam_mgr.cameras)
            self.log("Workers started. Go to Live Preview tab to see feeds.")
            
        threading.Thread(target=scan).start()

    def apply_camera_settings(self):
        res_str = self.res_combo.get().split(' ')[0] # Get e.g. "1920x1080" from "1920x1080 (1080p)"
        w, h = map(int, res_str.split('x'))
        fps = int(self.fps_entry.get())
        exp = int(self.exposure_slider.get())
        gain = int(self.gain_slider.get())
        wb = int(self.wb_slider.get())
        
        for idx in self.camera_indices:
            actual = self.cam_mgr.apply_settings(idx, width=w, height=h, fps=fps, exposure_value=exp, gain_value=gain, wb_value=wb)
            if actual:
                self.log(f"Cam {idx} ACCEPTED: Res={actual['width']}x{actual['height']}, FPS={actual['fps']}, Exp={actual['exposure']}, Gain={actual['gain']}, WB={actual['wb']}")
        self.log("Settings applied to all cameras.")

    def connect_arduino(self):
        port = self.port_combo.get()
        if self.arduino.connect(port):
            self.log("Arduino connected!")
            self.btn_connect.configure(text="Connected", state="disabled")
            self.btn_start_sync.configure(state="normal")

    def start_sync(self):
        fps = int(self.fps_entry.get())
        self.arduino.set_fps(fps)
        self.arduino.start_trigger()
        self.log("Hardware Trigger STARTED!")
        self.btn_start_sync.configure(state="disabled")
        self.btn_stop_sync.configure(state="normal")

    def stop_sync(self):
        self.arduino.stop_trigger()
        self.log("Hardware Trigger STOPPED.")
        self.btn_stop_sync.configure(state="disabled")
        self.btn_start_sync.configure(state="normal")

    def toggle_record(self):
        if not self.recorder.is_recording:
            # START
            proj_name = self.proj_name_entry.get()
            if not proj_name:
                self.log("Error: Enter a project name.")
                return
                
            self.proj_mgr.set_project(proj_name)
            is_calib = (self.record_type.get() == "calibration")
            save_dir = self.proj_mgr.get_recording_folder(is_calib)
            
            fps = int(self.fps_entry.get())
            codec = self.codec_combo.get()
            
            self.log(f"Starting recording to: {save_dir}")
            self.recorder.start_recording(save_dir, fps, codec)
            
            self.btn_record.configure(text="⏹ STOP RECORDING", fg_color="red", hover_color="darkred")
        else:
            # STOP
            self.recorder.stop_recording()
            self.btn_record.configure(text="⏺ START RECORDING", fg_color="darkred", hover_color="red")
            self.log("Recording stopped and saved.")

    def update_preview(self):
        # Update UI with latest frames
        frames = self.recorder.get_latest_frames()
        for idx, frame in frames.items():
            if idx in self.preview_labels:
                # Resize keeping aspect ratio for UI
                lbl = self.preview_labels[idx]
                target_w = lbl.winfo_width()
                target_h = lbl.winfo_height()
                if target_w > 10 and target_h > 10:
                    # Convert BGR to RGB
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(rgb_frame)
                    
                    # Letterboxing thumbnail
                    img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
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
