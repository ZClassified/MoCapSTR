import tkinter as tk
import customtkinter as ctk
from camera_manager import CameraManager
from arduino_sync import ArduinoSync
from project_manager import ProjectManager
from recorder import MultiCamManager
from preset_manager import PresetManager
import cv2
from PIL import Image, ImageTk
import threading
import os
import time
from tkinter import filedialog

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MoCapSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MoCapSTR: Sync / Trigger / Record for FreeMoCap")
        self.geometry("1100x800")
        
        # Managers
        self.cam_mgr = CameraManager()
        self.arduino = ArduinoSync()
        self.proj_mgr = ProjectManager()
        self.recorder = MultiCamManager()
        self.preset_mgr = PresetManager()
        
        self.camera_indices = []
        self.preview_labels = {} # Grid for previews
        
        self.record_start_time = 0
        self.ui_tick = 0
        self.last_free_space = 0
        
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
        parent.grid_columnconfigure(2, weight=1)
        
        # --- Top Bar: PRESETS ---
        preset_frame = ctk.CTkFrame(parent)
        preset_frame.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 5), sticky="ew")
        
        ctk.CTkLabel(preset_frame, text="Presets:").pack(side="left", padx=10, pady=5)
        self.preset_combo = ctk.CTkComboBox(preset_frame, values=["Default"] + self.preset_mgr.get_preset_names())
        self.preset_combo.pack(side="left", padx=5, pady=5)
        
        self.preset_name_entry = ctk.CTkEntry(preset_frame, placeholder_text="New Preset Name")
        self.preset_name_entry.pack(side="left", padx=10, pady=5)
        
        self.btn_save_preset = ctk.CTkButton(preset_frame, text="Save Preset", command=self.save_preset)
        self.btn_save_preset.pack(side="left", padx=5, pady=5)
        self.btn_load_preset = ctk.CTkButton(preset_frame, text="Load Preset", command=self.load_preset)
        self.btn_load_preset.pack(side="left", padx=5, pady=5)
        
        # --- Column 1: Camera Settings ---
        col1_container = ctk.CTkFrame(parent, fg_color="transparent")
        col1_container.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        
        # Card 1: Camera Connection
        conn_frame = ctk.CTkFrame(col1_container)
        conn_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(conn_frame, text="1. Camera Connection", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        backend_f = ctk.CTkFrame(conn_frame, fg_color="transparent")
        backend_f.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(backend_f, text="Backend:").pack(side="left")
        self.backend_combo = ctk.CTkComboBox(backend_f, values=["DSHOW", "MSMF", "ANY"], width=100)
        self.backend_combo.set("DSHOW")
        self.backend_combo.pack(side="right")
        
        type_f = ctk.CTkFrame(conn_frame, fg_color="transparent")
        type_f.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(type_f, text="Camera Type:").pack(side="left")
        self.camera_type_combo = ctk.CTkComboBox(type_f, values=["USB Webcams", "Blackmagic SDI"], width=130, command=self.on_camera_type_change)
        self.camera_type_combo.set("USB Webcams")
        self.camera_type_combo.pack(side="right")
        
        self.btn_scan = ctk.CTkButton(conn_frame, text="Scan & Open Cameras", command=self.scan_cameras)
        self.btn_scan.pack(fill="x", padx=10, pady=5)
        self.lbl_cams_found = ctk.CTkLabel(conn_frame, text="Cameras found: 0")
        self.lbl_cams_found.pack(anchor="w", padx=10, pady=(0, 5))

        # Card 2: Sensor Settings
        sensor_frame = ctk.CTkFrame(col1_container)
        sensor_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(sensor_frame, text="2. Sensor Settings", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        res_options = ["3840x2160 (4K)", "2560x1440 (1440p)", "1920x1080 (1080p)", "1280x800", "1280x720 (720p)", "1024x768", "800x600", "640x480", "640x400", "320x240"]
        self.res_combo = ctk.CTkComboBox(sensor_frame, values=res_options)
        self.res_combo.set("1280x720 (720p)")
        self.res_combo.pack(fill="x", padx=10, pady=5)
        
        self.lbl_exposure = ctk.CTkLabel(sensor_frame, text="Exposure (Shutter Speed): 1/128s")
        self.lbl_exposure.pack(anchor="w", padx=10)
        self.exposure_slider = ctk.CTkSlider(sensor_frame, from_=-11, to=-3, number_of_steps=8, command=self.update_exposure_label)
        self.exposure_slider.set(-7)
        self.exposure_slider.pack(fill="x", padx=10, pady=5)
        
        self.lbl_gain = ctk.CTkLabel(sensor_frame, text="Gain: 0")
        self.lbl_gain.pack(anchor="w", padx=10)
        self.gain_slider = ctk.CTkSlider(sensor_frame, from_=0, to=255, command=self.update_gain_label)
        self.gain_slider.set(0)
        self.gain_slider.pack(fill="x", padx=10, pady=5)
        
        self.lbl_wb = ctk.CTkLabel(sensor_frame, text="White Balance: 5600K")
        self.lbl_wb.pack(anchor="w", padx=10)
        self.wb_slider = ctk.CTkSlider(sensor_frame, from_=2000, to=8000, number_of_steps=60, command=self.update_wb_label)
        self.wb_slider.set(5600)
        self.wb_slider.pack(fill="x", padx=10, pady=5)
        
        self.btn_apply_cams = ctk.CTkButton(sensor_frame, text="Apply Camera Settings", command=self.apply_camera_settings)
        self.btn_apply_cams.pack(fill="x", padx=10, pady=10)

        # --- Column 2: Hardware Sync ---
        col2_container = ctk.CTkFrame(parent, fg_color="transparent")
        col2_container.grid(row=1, column=1, padx=10, pady=5, sticky="nsew")
        
        # Card 3: Arduino Sync
        sync_frame = ctk.CTkFrame(col2_container)
        sync_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(sync_frame, text="3. Hardware Sync", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        ports = ArduinoSync.get_available_ports()
        self.port_combo = ctk.CTkComboBox(sync_frame, values=ports if ports else ["No Ports Found"])
        self.port_combo.pack(fill="x", padx=10, pady=5)
        
        self.btn_connect = ctk.CTkButton(sync_frame, text="Connect Arduino", command=self.connect_arduino)
        self.btn_connect.pack(fill="x", padx=10, pady=5)
        
        f_fps = ctk.CTkFrame(sync_frame, fg_color="transparent")
        f_fps.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_fps, text="Target Framerate (FPS):").pack(side="left")
        self.fps_entry = ctk.CTkEntry(f_fps, width=60)
        self.fps_entry.insert(0, "60")
        self.fps_entry.pack(side="right")
        
        self.btn_start_sync = ctk.CTkButton(sync_frame, text="START HARDWARE TRIGGER", fg_color="green", hover_color="darkgreen", command=self.start_sync, state="disabled")
        self.btn_start_sync.pack(fill="x", padx=10, pady=5)
        self.btn_stop_sync = ctk.CTkButton(sync_frame, text="STOP HARDWARE TRIGGER", fg_color="red", hover_color="darkred", command=self.stop_sync, state="disabled")
        self.btn_stop_sync.pack(fill="x", padx=10, pady=5)

        # --- Column 3: Charuco Board ---
        col3_container = ctk.CTkFrame(parent, fg_color="transparent")
        col3_container.grid(row=1, column=2, padx=10, pady=5, sticky="nsew")

        # Card 4: Charuco Calibration Settings
        calib_frame = ctk.CTkFrame(col3_container)
        calib_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(calib_frame, text="4. Charuco Board (FreeMoCap)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        d_frame = ctk.CTkFrame(calib_frame, fg_color="transparent")
        d_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(d_frame, text="Dictionary:").pack(side="left")
        self.charuco_dict = ctk.CTkComboBox(d_frame, values=["DICT_4X4_50", "DICT_4X4_100", "DICT_5X5_50", "DICT_5X5_100", "DICT_6X6_250"])
        self.charuco_dict.set("DICT_4X4_50")
        self.charuco_dict.pack(side="right")
        
        sq_frame = ctk.CTkFrame(calib_frame, fg_color="transparent")
        sq_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(sq_frame, text="Squares X/Y:").pack(side="left")
        self.charuco_x = ctk.CTkEntry(sq_frame, width=40)
        self.charuco_x.insert(0, "5")
        self.charuco_x.pack(side="right")
        ctk.CTkLabel(sq_frame, text="x").pack(side="right", padx=5)
        self.charuco_y = ctk.CTkEntry(sq_frame, width=40)
        self.charuco_y.insert(0, "3")
        self.charuco_y.pack(side="right")
        
        size_frame = ctk.CTkFrame(calib_frame, fg_color="transparent")
        size_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(size_frame, text="Square Size (mm):").pack(side="left")
        self.charuco_sq_size = ctk.CTkEntry(size_frame, width=60)
        self.charuco_sq_size.insert(0, "51")
        self.charuco_sq_size.pack(side="right")
        
        marker_frame = ctk.CTkFrame(calib_frame, fg_color="transparent")
        marker_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(marker_frame, text="Marker Size (mm):").pack(side="left")
        self.charuco_marker_size = ctk.CTkEntry(marker_frame, width=60)
        self.charuco_marker_size.insert(0, "38")
        self.charuco_marker_size.pack(side="right")
        
        self.btn_preview_charuco = ctk.CTkButton(calib_frame, text="Update Board Preview", command=self.update_charuco_preview)
        self.btn_preview_charuco.pack(fill="x", padx=10, pady=(10, 2))
        
        self.lbl_charuco_preview = ctk.CTkLabel(calib_frame, text="No Preview")
        self.lbl_charuco_preview.pack(pady=5)

        # --- Bottom Row: Log ---
        log_container = ctk.CTkFrame(parent, fg_color="transparent")
        log_container.grid(row=2, column=0, columnspan=3, padx=10, pady=5, sticky="nsew")
        
        log_frame = ctk.CTkFrame(log_container)
        log_frame.pack(fill="both", expand=True, pady=0)
        ctk.CTkLabel(log_frame, text="System Log", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        self.txt_log = ctk.CTkTextbox(log_frame, height=120)
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt_log.tag_config("success", foreground="#00FF00")
        self.txt_log.tag_config("error", foreground="#FF4444")
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
        
        codec_frame = ctk.CTkFrame(frame_rec, fg_color="transparent")
        codec_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(codec_frame, text="Video Codec:").pack(side="left")
        
        self.btn_codec_info = ctk.CTkButton(codec_frame, text="ℹ️ Info", width=50, height=24, command=self.show_codec_info)
        self.btn_codec_info.pack(side="right", padx=(5, 0))
        
        self.codec_combo = ctk.CTkComboBox(codec_frame, values=list(self.recorder.get_supported_codecs().keys()))
        self.codec_combo.pack(side="right", fill="x", expand=True, padx=(10, 0))
        
        ctk.CTkLabel(frame_rec, text="Record Type:").pack(anchor="w", padx=10)
        self.record_type = ctk.StringVar(value="motion")
        ctk.CTkRadioButton(frame_rec, text="Motion Take (Normal)", variable=self.record_type, value="motion").pack(anchor="w", padx=10, pady=5)
        ctk.CTkRadioButton(frame_rec, text="Calibration (Charuco)", variable=self.record_type, value="calibration").pack(anchor="w", padx=10, pady=5)
        
        # Big Record Buttons
        self.btn_record = ctk.CTkButton(parent, text="⏺ START RECORDING", fg_color="darkred", hover_color="red", height=60, font=ctk.CTkFont(size=24, weight="bold"), command=self.toggle_record)
        self.btn_record.pack(fill="x", padx=10, pady=20)

    # --- TAB 3: PREVIEW ---
    def build_preview_tab(self, parent):
        # Top bar for controls and stats
        self.preview_top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        self.preview_top_bar.pack(fill="x", padx=10, pady=(10, 0))
        
        self.btn_record_live = ctk.CTkButton(self.preview_top_bar, text="⏺ START RECORDING", fg_color="darkred", hover_color="red", command=self.toggle_record)
        self.btn_record_live.pack(side="left", padx=10)
        
        self.chk_charuco = ctk.CTkCheckBox(self.preview_top_bar, text="Show Charuco")
        self.chk_charuco.pack(side="left", padx=10)
        
        self.lbl_live_stats = ctk.CTkLabel(self.preview_top_bar, text="Ready | Space: -- GB", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_live_stats.pack(side="left", padx=20)
        
        self.lbl_live_warning = ctk.CTkLabel(self.preview_top_bar, text="", text_color="red", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_live_warning.pack(side="right", padx=10)

        # We will dynamically create a grid of up to 6 labels
        self.preview_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.preview_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        for i in range(2):
            self.preview_frame.grid_rowconfigure(i, weight=1)
        for j in range(3):
            self.preview_frame.grid_columnconfigure(j, weight=1)
            
    # --- LOGIC ---
    def on_camera_type_change(self, choice):
        is_sdi = (choice == "Blackmagic SDI")
        state = "disabled" if is_sdi else "normal"
        text_color = "gray50" if is_sdi else "white"
        
        self.exposure_slider.configure(state=state)
        self.gain_slider.configure(state=state)
        self.wb_slider.configure(state=state)
        
        self.lbl_exposure.configure(text_color=text_color)
        self.lbl_gain.configure(text_color=text_color)
        self.lbl_wb.configure(text_color=text_color)
        
    def show_codec_info(self):
        info_win = ctk.CTkToplevel(self)
        info_win.title("Codec Recommendations")
        info_win.geometry("500x480")
        info_win.attributes("-topmost", True)
        
        text = (
            "Hardware & Codec Empfehlungen:\n\n"
            "• 2 Kameras (Geringe Last):\n"
            "  Nutze 'MP4V' oder 'FFmpeg (CPU)'. Jede normale CPU schafft das mühelos ohne Frame-Drops.\n\n"
            "• 4 Kameras (Mittlere Last):\n"
            "  Nutze 'FFmpeg (NVIDIA/Intel/AMD)'. Hardware-Beschleunigung durch die Grafikkarte wird dringend empfohlen, um Dropouts zu vermeiden.\n\n"
            "• 6+ Kameras (Hohe Last):\n"
            "  Hardware-Beschleunigung ist PFLICHT! Zusätzlich musst du auf eine schnelle interne NVMe SSD speichern. "
            "Du solltest die Kameras zudem auf mehrere USB-Controller verteilen (z.B. per PCIe-Erweiterungskarte), da der USB-Bus sonst überlastet.\n\n"
            "Hinweis zu MJPG: Erzeugt gigantische Dateien, schont aber die CPU stark. Gut für sehr alte PCs ohne gute GPU, aber schlecht für die Festplatte."
        )
        
        lbl = ctk.CTkLabel(info_win, text=text, justify="left", wraplength=460)
        lbl.pack(padx=20, pady=20, fill="both", expand=True)
        
        btn_close = ctk.CTkButton(info_win, text="Verstanden", command=info_win.destroy)
        btn_close.pack(pady=10)

    def save_preset(self):
        name = self.preset_name_entry.get()
        if not name:
            self.log("Please enter a preset name.", "error")
            return
            
        data = {
            "camera_type": self.camera_type_combo.get(),
            "backend": self.backend_combo.get(),
            "resolution": self.res_combo.get(),
            "exposure": self.exposure_slider.get(),
            "gain": self.gain_slider.get(),
            "wb": self.wb_slider.get(),
            "fps": self.fps_entry.get(),
            "charuco_dict": self.charuco_dict.get(),
            "charuco_x": self.charuco_x.get(),
            "charuco_y": self.charuco_y.get(),
            "charuco_sq_size": self.charuco_sq_size.get(),
            "charuco_marker_size": self.charuco_marker_size.get()
        }
        self.preset_mgr.save_preset(name, data)
        self.preset_combo.configure(values=["Default"] + self.preset_mgr.get_preset_names())
        self.preset_combo.set(name)
        self.log(f"Preset '{name}' saved.", "success")
        
    def load_preset(self):
        name = self.preset_combo.get()
        if name == "Default" or not name:
            return
            
        data = self.preset_mgr.get_preset(name)
        if data:
            cam_type = data.get("camera_type", "USB Webcams")
            self.camera_type_combo.set(cam_type)
            self.on_camera_type_change(cam_type)
            
            self.backend_combo.set(data.get("backend", "DSHOW"))
            self.res_combo.set(data.get("resolution", "1280x720 (720p)"))
            self.exposure_slider.set(data.get("exposure", -7))
            self.update_exposure_label(data.get("exposure", -7))
            self.gain_slider.set(data.get("gain", 0))
            self.update_gain_label(data.get("gain", 0))
            self.wb_slider.set(data.get("wb", 5600))
            self.update_wb_label(data.get("wb", 5600))
            
            self.fps_entry.delete(0, 'end')
            self.fps_entry.insert(0, data.get("fps", "60"))
            
            self.charuco_dict.set(data.get("charuco_dict", "DICT_4X4_50"))
            self.charuco_x.delete(0, 'end')
            self.charuco_x.insert(0, data.get("charuco_x", "11"))
            self.charuco_y.delete(0, 'end')
            self.charuco_y.insert(0, data.get("charuco_y", "8"))
            self.charuco_sq_size.delete(0, 'end')
            self.charuco_sq_size.insert(0, data.get("charuco_sq_size", "30"))
            self.charuco_marker_size.delete(0, 'end')
            self.charuco_marker_size.insert(0, data.get("charuco_marker_size", "22"))
            
            self.log(f"Preset '{name}' loaded.", "success")
            self.update_charuco_preview()

    def update_charuco_preview(self):
        try:
            dict_str = self.charuco_dict.get()
            x = int(self.charuco_x.get())
            y = int(self.charuco_y.get())
            
            sq_size = float(self.charuco_sq_size.get())
            marker_size = float(self.charuco_marker_size.get())
            
            dict_mapping = {
                "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
                "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
                "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
                "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
                "DICT_6X6_250": cv2.aruco.DICT_6X6_250
            }
            dict_id = dict_mapping.get(dict_str, cv2.aruco.DICT_4X4_50)
            
            if hasattr(cv2.aruco, 'getPredefinedDictionary'):
                aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
            else:
                aruco_dict = cv2.aruco.Dictionary_get(dict_id)
                
            if hasattr(cv2.aruco, 'CharucoBoard'):
                board = cv2.aruco.CharucoBoard((x, y), sq_size, marker_size, aruco_dict)
                if hasattr(board, 'generateImage'):
                    img_cv = board.generateImage((x * 40, y * 40))
                else:
                    img_cv = board.draw((x * 40, y * 40))
            else:
                board = cv2.aruco.CharucoBoard_create(x, y, sq_size, marker_size, aruco_dict)
                img_cv = board.draw((x * 40, y * 40))
                
            if len(img_cv.shape) == 2:
                img_cv = cv2.cvtColor(img_cv, cv2.COLOR_GRAY2RGB)
                
            img_pil = Image.fromarray(img_cv)
            
            target_w = 250
            aspect = img_pil.height / img_pil.width
            target_h = int(target_w * aspect)
            
            ctk_img = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(target_w, target_h))
            self.lbl_charuco_preview.configure(image=ctk_img, text="")
            
        except Exception as e:
            self.log(f"Charuco preview failed: {e}", "error")

    def get_free_space(self):
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.proj_mgr.base_path)
            return free // (2**30)
        except Exception:
            return 0

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

    def log(self, message, level="info"):
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

    def scan_cameras(self):
        self.log("Scanning for cameras (this may take a few seconds)...")
        self.btn_scan.configure(state="disabled")
        
        # WICHTIG: Stoppe alte Aufnahme-Threads, bevor wir Kameras schließen/öffnen!
        # Sonst greifen Threads auf geschlossene Kamera-Handles zu -> Freeze.
        self.recorder.stop_workers()
        
        def scan():
            backend = self.backend_combo.get()
            cam_type = self.camera_type_combo.get()
            
            # Extract resolution and fps to pass to CameraManager for SDI
            res_str = self.res_combo.get().split(' ')[0]
            target_w, target_h = map(int, res_str.split('x'))
            try:
                target_fps = int(self.fps_entry.get())
            except ValueError:
                target_fps = 60
                
            self.camera_indices = self.cam_mgr.find_and_open_cameras(
                6, 
                backend_name=backend,
                camera_type=cam_type,
                target_w=target_w,
                target_h=target_h,
                target_fps=target_fps
            )
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
                self.log(f"Cam {idx} ACCEPTED: Res={actual['width']}x{actual['height']}, FPS={actual['fps']}, Exp={actual['exposure']}, Gain={actual['gain']}, WB={actual['wb']}", level="success")
            else:
                self.log(f"Cam {idx} FAILED to apply settings!", level="error")
        self.log("Settings applied to all cameras.")

    def connect_arduino(self):
        port = self.port_combo.get()
        if self.arduino.connect(port):
            self.log("Arduino connected!", level="success")
            self.btn_connect.configure(text="Connected", state="disabled")
            self.btn_start_sync.configure(state="normal")

    def start_sync(self):
        fps = int(self.fps_entry.get())
        self.arduino.set_fps(fps)
        self.arduino.start_trigger()
        self.log("Hardware Trigger STARTED!", level="success")
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
                self.log("Error: Enter a project name.", level="error")
                return
                
            self.proj_mgr.set_project(proj_name)
            is_calib = (self.record_type.get() == "calibration")
            save_dir = self.proj_mgr.get_recording_folder(is_calib)
            
            fps = int(self.fps_entry.get())
            codec = self.codec_combo.get()
            
            self.log(f"Starting recording to: {save_dir}")
            self.recorder.start_recording(save_dir, fps, codec)
            self.record_start_time = time.time()
            
            self.btn_record.configure(text="⏹ STOP RECORDING", fg_color="red", hover_color="darkred")
            self.btn_record_live.configure(text="⏹ STOP RECORDING", fg_color="red", hover_color="darkred")
        else:
            # STOP
            self.recorder.stop_recording()
            self.btn_record.configure(text="⏺ START RECORDING", fg_color="darkred", hover_color="red")
            self.btn_record_live.configure(text="⏺ START RECORDING", fg_color="darkred", hover_color="red")
            self.lbl_live_warning.configure(text="")
            self.log("Recording stopped and saved.")

    def update_preview(self):
        self.ui_tick += 1
        if self.ui_tick % 20 == 0 or self.ui_tick == 1:
            self.last_free_space = self.get_free_space()
            
            if self.recorder.is_recording and self.last_free_space < 2:
                self.log("CRITICAL: Less than 2 GB free! Auto-stopping recording.", "error")
                self.toggle_record()
                
            if not self.recorder.is_recording:
                space_str = f"Space: {self.last_free_space} GB"
                color = "red" if self.last_free_space < 20 else ("white" if ctk.get_appearance_mode() == "Dark" else "black")
                self.lbl_live_stats.configure(text=f"Ready | {space_str}", text_color=color)

        if self.recorder.is_recording:
            elapsed = time.time() - self.record_start_time
            mins, secs = divmod(int(elapsed), 60)
            
            frame_counts = [w.frames_recorded for w in self.recorder.workers.values()]
            max_frames = max(frame_counts) if frame_counts else 0
            min_frames = min(frame_counts) if frame_counts else 0
            
            if max_frames - min_frames > 0:
                self.lbl_live_warning.configure(text=f"⚠️ SYNC WARNING: Frame drop! (Delta: {max_frames - min_frames})")
            else:
                self.lbl_live_warning.configure(text="")
                
            space_str = f"Space: {self.last_free_space} GB"
            color = "red" if self.last_free_space < 20 else ("white" if ctk.get_appearance_mode() == "Dark" else "black")
            if self.last_free_space < 20:
                space_str = f"⚠️ LOW SPACE: {self.last_free_space} GB"
                
            self.lbl_live_stats.configure(text=f"Recording 🔴 | {mins:02d}:{secs:02d} | Frames: {max_frames} | {space_str}", text_color=color)

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
                    
                    # --- Live Charuco Detection ---
                    if getattr(self, 'chk_charuco', None) and self.chk_charuco.get() == 1:
                        try:
                            dict_str = self.charuco_dict.get()
                            dict_mapping = {
                                "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
                                "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
                                "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
                                "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
                                "DICT_6X6_250": cv2.aruco.DICT_6X6_250
                            }
                            dict_id = dict_mapping.get(dict_str, cv2.aruco.DICT_4X4_50)
                            
                            # Handle different OpenCV versions for getPredefinedDictionary
                            if hasattr(cv2.aruco, 'getPredefinedDictionary'):
                                aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
                            else:
                                aruco_dict = cv2.aruco.Dictionary_get(dict_id)
                                
                            if hasattr(cv2.aruco, 'DetectorParameters'):
                                parameters = cv2.aruco.DetectorParameters()
                            else:
                                parameters = cv2.aruco.DetectorParameters_create()
                                
                            gray = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2GRAY)
                            
                            if hasattr(cv2.aruco, 'ArucoDetector'):
                                detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
                                corners, ids, rejected = detector.detectMarkers(gray)
                            else:
                                corners, ids, rejected = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=parameters)
                            
                            num_markers = 0
                            if corners and len(corners) > 0:
                                cv2.aruco.drawDetectedMarkers(rgb_frame, corners, ids)
                                num_markers = len(corners)
                        except Exception as e:
                            self.log(f"Charuco Error: {e}", "error")
                            self.chk_charuco.deselect()
                    # ------------------------------
                    
                    # --- FPS Overlay ---
                    fps = 0.0
                    if idx in self.recorder.workers:
                        fps = self.recorder.workers[idx].current_fps
                        
                    try:
                        target_fps = float(self.fps_entry.get())
                    except ValueError:
                        target_fps = 60.0
                        
                    # Determine color based on deviation
                    diff = abs(fps - target_fps)
                    if diff <= 0.5:
                        color = (0, 255, 0) # Green (Perfect)
                    elif diff <= 3.0:
                        color = (255, 255, 0) # Yellow (Slight deviation)
                    else:
                        color = (255, 0, 0) # Red (Significant deviation)
                        
                    text = f"FPS: {fps:.1f}"
                    if getattr(self, 'chk_charuco', None) and self.chk_charuco.get() == 1:
                        try:
                            text += f" | Markers: {num_markers}"
                            if num_markers < 8:
                                color = (255, 165, 0) # Orange warning if few markers
                        except NameError:
                            pass
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
