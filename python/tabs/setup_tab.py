import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import threading

class SetupTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.build_ui()
        
    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        
        # --- Top Bar: PRESETS ---
        preset_frame = ctk.CTkFrame(self)
        preset_frame.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 5), sticky="ew")
        
        ctk.CTkLabel(preset_frame, text="Presets:").pack(side="left", padx=10, pady=5)
        self.preset_combo = ctk.CTkComboBox(preset_frame, values=["Default"] + self.app.preset_mgr.get_preset_names())
        self.preset_combo.pack(side="left", padx=5, pady=5)
        
        self.preset_name_entry = ctk.CTkEntry(preset_frame, placeholder_text="New Preset Name")
        self.preset_name_entry.pack(side="left", padx=10, pady=5)
        
        self.btn_save_preset = ctk.CTkButton(preset_frame, text="Save Preset", command=self.save_preset)
        self.btn_save_preset.pack(side="left", padx=5, pady=5)
        self.btn_load_preset = ctk.CTkButton(preset_frame, text="Load Preset", command=self.load_preset)
        self.btn_load_preset.pack(side="left", padx=5, pady=5)
        
        # --- Column 1: Camera Settings ---
        col1_container = ctk.CTkFrame(self, fg_color="transparent")
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
        col2_container = ctk.CTkFrame(self, fg_color="transparent")
        col2_container.grid(row=1, column=1, padx=10, pady=5, sticky="nsew")
        
        # Card 3: Arduino Sync
        sync_frame = ctk.CTkFrame(col2_container)
        sync_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(sync_frame, text="3. Hardware Sync", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        ports = self.app.arduino.get_available_ports()
        self.port_combo = ctk.CTkComboBox(sync_frame, values=ports if ports else ["No Ports Found"])
        self.port_combo.pack(fill="x", padx=10, pady=5)
        
        self.btn_connect = ctk.CTkButton(sync_frame, text="Connect Arduino", command=self.connect_arduino)
        self.btn_connect.pack(fill="x", padx=10, pady=5)
        
        f_fps = ctk.CTkFrame(sync_frame, fg_color="transparent")
        f_fps.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_fps, text="Target Framerate (FPS):").pack(side="left")
        self.fps_entry = ctk.CTkEntry(f_fps, width=60)
        self.fps_entry.insert(0, "50")
        self.fps_entry.pack(side="right")
        
        self.btn_start_sync = ctk.CTkButton(sync_frame, text="START HARDWARE TRIGGER", fg_color="green", hover_color="darkgreen", command=self.start_sync, state="disabled")
        self.btn_start_sync.pack(fill="x", padx=10, pady=5)
        self.btn_stop_sync = ctk.CTkButton(sync_frame, text="STOP HARDWARE TRIGGER", fg_color="red", hover_color="darkred", command=self.stop_sync, state="disabled")
        self.btn_stop_sync.pack(fill="x", padx=10, pady=5)

        # --- Column 3: Charuco Board ---
        col3_container = ctk.CTkFrame(self, fg_color="transparent")
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
        log_container = ctk.CTkFrame(self, fg_color="transparent")
        log_container.grid(row=2, column=0, columnspan=3, padx=10, pady=5, sticky="nsew")
        
        log_frame = ctk.CTkFrame(log_container)
        log_frame.pack(fill="both", expand=True, pady=0)
        ctk.CTkLabel(log_frame, text="System Log", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        self.txt_log = ctk.CTkTextbox(log_frame, height=120)
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt_log.tag_config("success", foreground="#00FF00")
        self.txt_log.tag_config("error", foreground="#FF4444")
        self.app.txt_log = self.txt_log # Inject into app for app.log()
        self.app.log("Welcome to MoCap Recording Station.")

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

    def save_preset(self):
        name = self.preset_name_entry.get()
        if not name:
            self.app.log("Please enter a preset name.", "error")
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
        self.app.preset_mgr.save_preset(name, data)
        self.preset_combo.configure(values=["Default"] + self.app.preset_mgr.get_preset_names())
        self.preset_combo.set(name)
        self.app.log(f"Preset '{name}' saved.", "success")
        
    def load_preset(self):
        name = self.preset_combo.get()
        if name == "Default" or not name:
            return
            
        data = self.app.preset_mgr.get_preset(name)
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
            self.fps_entry.insert(0, data.get("fps", "50"))
            
            self.charuco_dict.set(data.get("charuco_dict", "DICT_4X4_50"))
            self.charuco_x.delete(0, 'end')
            self.charuco_x.insert(0, data.get("charuco_x", "11"))
            self.charuco_y.delete(0, 'end')
            self.charuco_y.insert(0, data.get("charuco_y", "8"))
            self.charuco_sq_size.delete(0, 'end')
            self.charuco_sq_size.insert(0, data.get("charuco_sq_size", "30"))
            self.charuco_marker_size.delete(0, 'end')
            self.charuco_marker_size.insert(0, data.get("charuco_marker_size", "22"))
            
            self.app.log(f"Preset '{name}' loaded.", "success")
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
            self.app.log(f"Charuco preview failed: {e}", "error")

    def update_exposure_label(self, value):
        val = int(value)
        denominator = 2 ** abs(val)
        self.lbl_exposure.configure(text=f"Exposure (Shutter Speed): 1/{denominator}s")

    def update_gain_label(self, value):
        self.lbl_gain.configure(text=f"Gain: {int(value)}")
        
    def update_wb_label(self, value):
        self.lbl_wb.configure(text=f"White Balance: {int(value)}K")

    def scan_cameras(self):
        self.app.log("Scanning for cameras (this may take a few seconds)...")
        self.btn_scan.configure(state="disabled")
        
        self.app.recorder.stop_workers()
        
        def scan():
            backend = self.backend_combo.get()
            cam_type = self.camera_type_combo.get()
            
            res_str = self.res_combo.get().split(' ')[0]
            target_w, target_h = map(int, res_str.split('x'))
            try:
                target_fps = int(self.fps_entry.get())
            except ValueError:
                target_fps = 50
                
            self.app.camera_indices = self.app.cam_mgr.find_and_open_cameras(
                6, 
                backend_name=backend,
                camera_type=cam_type,
                target_w=target_w,
                target_h=target_h,
                target_fps=target_fps
            )
            self.lbl_cams_found.configure(text=f"Cameras found: {len(self.app.camera_indices)} ({self.app.camera_indices})")
                
            self.app.preview_tab.setup_preview_grid()
            
            self.btn_scan.configure(state="normal")
            
            # Start background grabbing threads
            self.app.recorder.start_workers(self.app.cam_mgr.cameras, target_fps)
            self.app.log("Workers started. Go to Live Preview tab to see feeds.")
            
        threading.Thread(target=scan).start()

    def apply_camera_settings(self):
        self.app.recorder.stop_workers()
        
        res_str = self.res_combo.get().split(' ')[0]
        w, h = map(int, res_str.split('x'))
        try:
            fps = int(self.fps_entry.get())
        except ValueError:
            fps = 50
        exp = int(self.exposure_slider.get())
        gain = int(self.gain_slider.get())
        wb = int(self.wb_slider.get())
        
        for idx in self.app.camera_indices:
            actual = self.app.cam_mgr.apply_settings(idx, width=w, height=h, fps=fps, exposure_value=exp, gain_value=gain, wb_value=wb)
            if actual:
                self.app.log(f"Cam {idx} ACCEPTED: Res={actual['width']}x{actual['height']}, FPS={actual['fps']}, Exp={actual['exposure']}, Gain={actual['gain']}, WB={actual['wb']}", level="success")
            else:
                self.app.log(f"Cam {idx} FAILED to apply settings!", level="error")
                
        self.app.recorder.start_workers(self.app.cam_mgr.cameras, target_fps=fps)
        self.app.log("Settings applied to all cameras.")

    def connect_arduino(self):
        port = self.port_combo.get()
        if self.app.arduino.connect(port):
            self.app.log("Arduino connected!", level="success")
            self.btn_connect.configure(text="Connected", state="disabled")
            self.btn_start_sync.configure(state="normal")

    def start_sync(self):
        fps = int(self.fps_entry.get())
        self.app.arduino.set_fps(fps)
        self.app.arduino.start_trigger()
        self.app.log("Hardware Trigger STARTED!", level="success")
        self.btn_start_sync.configure(state="disabled")
        self.btn_stop_sync.configure(state="normal")

    def stop_sync(self):
        self.app.arduino.stop_trigger()
        self.app.log("Hardware Trigger STOPPED.")
        self.btn_stop_sync.configure(state="disabled")
        self.btn_start_sync.configure(state="normal")
