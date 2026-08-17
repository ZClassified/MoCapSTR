import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image
import threading
import cv2

class SetupTab(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.build_ui()
        
    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        
        # --- BLOCK 1: Project & Session ---
        blk1 = ctk.CTkFrame(self)
        blk1.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(blk1, text="1. Project & Session", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        # Base Dir
        dir_f = ctk.CTkFrame(blk1, fg_color="transparent")
        dir_f.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(dir_f, text="Save Directory:").pack(side="left")
        self.lbl_save_dir = ctk.CTkLabel(dir_f, text=self.app.proj_mgr.base_path, text_color="gray")
        self.lbl_save_dir.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(dir_f, text="Browse...", width=80, command=self.browse_directory).pack(side="right")
        
        # Project Name & Codec
        proj_f = ctk.CTkFrame(blk1, fg_color="transparent")
        proj_f.pack(fill="x", padx=10, pady=(5, 10))
        ctk.CTkLabel(proj_f, text="Project Name:").pack(side="left")
        self.proj_name_entry = ctk.CTkEntry(proj_f, width=150)
        self.proj_name_entry.insert(0, "My_MoCap_Project")
        self.proj_name_entry.pack(side="left", padx=5)
        
        ctk.CTkLabel(proj_f, text="Codec:").pack(side="left", padx=(15, 5))
        self.codec_combo = ctk.CTkComboBox(proj_f, values=list(self.app.recorder.get_supported_codecs().keys()), width=150)
        self.codec_combo.pack(side="left")
        
        # --- BLOCK 2: Presets ---
        blk2 = ctk.CTkFrame(self)
        blk2.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(blk2, text="2. Presets", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        pre_f = ctk.CTkFrame(blk2, fg_color="transparent")
        pre_f.pack(fill="x", padx=10, pady=(0, 10))
        self.preset_combo = ctk.CTkComboBox(pre_f, values=["Default"] + self.app.preset_mgr.get_preset_names(), width=150)
        self.preset_combo.pack(side="left", padx=5)
        ctk.CTkButton(pre_f, text="Load", width=60, command=self.load_preset).pack(side="left", padx=5)
        
        self.preset_name_entry = ctk.CTkEntry(pre_f, placeholder_text="New Preset Name", width=150)
        self.preset_name_entry.pack(side="left", padx=(20, 5))
        ctk.CTkButton(pre_f, text="Save", width=60, command=self.save_preset).pack(side="left")
        
        # --- BLOCK 3: Workflow Selection ---
        blk3 = ctk.CTkFrame(self)
        blk3.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(blk3, text="3. Workflow Selection", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        wf_f = ctk.CTkFrame(blk3, fg_color="transparent")
        wf_f.pack(fill="x", padx=10, pady=(0, 10))
        self.workflow_var = ctk.StringVar(value="USB Webcams")
        r1 = ctk.CTkRadioButton(wf_f, text="Option 1: Innomaker USB (+ Arduino Trigger)", variable=self.workflow_var, value="USB Webcams", command=self.update_workflow_ui)
        r1.pack(side="left", padx=20)
        r2 = ctk.CTkRadioButton(wf_f, text="Option 2: Blackmagic SDI (Genlock)", variable=self.workflow_var, value="Blackmagic SDI", command=self.update_workflow_ui)
        r2.pack(side="left", padx=20)

        # --- BLOCK 4: Camera Configuration ---
        self.blk4 = ctk.CTkFrame(self)
        self.blk4.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(self.blk4, text="4. Camera Configuration", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        cam_f = ctk.CTkFrame(self.blk4, fg_color="transparent")
        cam_f.pack(fill="x", padx=10, pady=2)
        
        ctk.CTkLabel(cam_f, text="Resolution:").pack(side="left")
        res_options = ["3840x2160 (4K)", "2560x1440 (1440p)", "1920x1080 (1080p)", "1280x800", "1280x720 (720p)", "1024x768", "800x600", "640x480", "640x400", "320x240"]
        self.res_combo = ctk.CTkComboBox(cam_f, values=res_options, width=150)
        self.res_combo.set("1280x720 (720p)")
        self.res_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(cam_f, text="Target FPS:").pack(side="left", padx=(15,5))
        self.fps_entry = ctk.CTkEntry(cam_f, width=60)
        self.fps_entry.insert(0, "50")
        self.fps_entry.pack(side="left")
        # Recalculate exposure limits whenever the user changes FPS
        self.fps_entry.bind("<FocusOut>", lambda e: self._clamp_exposure_to_fps())
        self.fps_entry.bind("<Return>",   lambda e: self._clamp_exposure_to_fps())

        # Hardware Tuning (Only for USB)
        self.tuning_frame = ctk.CTkFrame(self.blk4, fg_color="transparent")
        self.tuning_frame.pack(fill="x", padx=10, pady=10)

        # Wir geben dem Label eine feste Breite, damit der Slider nicht wackelt/schrumpft!
        self.lbl_exposure = ctk.CTkLabel(self.tuning_frame, text="Exposure: -9 (1/512s)", width=160, anchor="w")
        self.lbl_exposure.grid(row=0, column=0, sticky="w", padx=5)

        # Slider von -11 bis -3 (bleibt jetzt fest, keine automatische Beschneidung mehr)
        self.exposure_slider = ctk.CTkSlider(
            self.tuning_frame, from_=-11, to=-3,
            number_of_steps=8, command=self.update_exposure_label
        )
        self.exposure_slider.set(-9)
        self.exposure_slider.grid(row=0, column=1, sticky="ew", padx=10)
        
        # Warn-Label unter dem Slider (anfangs unsichtbar)
        self.lbl_exposure_warn = ctk.CTkLabel(self.tuning_frame, text="", text_color="red", font=ctk.CTkFont(size=11))
        self.lbl_exposure_warn.grid(row=1, column=1, sticky="w", padx=10)

        self.lbl_gain = ctk.CTkLabel(self.tuning_frame, text="Gain: 0", width=160, anchor="w")
        self.lbl_gain.grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.gain_slider = ctk.CTkSlider(self.tuning_frame, from_=0, to=255, command=self.update_gain_label)
        self.gain_slider.set(0)
        self.gain_slider.grid(row=2, column=1, sticky="ew", padx=10, pady=5)

        self.chk_uvc_trigger_var = ctk.BooleanVar(value=True)
        self.chk_uvc_trigger = ctk.CTkCheckBox(
            self.tuning_frame, text="Enable UVC Hardware Trigger",
            variable=self.chk_uvc_trigger_var
        )
        self.chk_uvc_trigger.grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        self.tuning_frame.columnconfigure(1, weight=1)

        # Run once so the slider already reflects the default FPS=50
        self._clamp_exposure_to_fps()

        # Action Row — single button that initialises everything, placed last so
        # the user naturally reads: Resolution → FPS → Exposure/Gain → Initialize.
        action_f = ctk.CTkFrame(self.blk4, fg_color="transparent")
        action_f.pack(fill="x", padx=10, pady=(5, 10))
        self.btn_init_system = ctk.CTkButton(
            action_f,
            text="Initialize System & Start Preview",
            command=self.initialize_system_cmd,
            fg_color="#1f538d", hover_color="#14375e",
            height=40, font=ctk.CTkFont(weight="bold", size=14)
        )
        self.btn_init_system.pack(fill="x", expand=True)


        # --- BLOCK 5: Arduino Trigger ---
        self.blk5 = ctk.CTkFrame(self)
        self.blk5.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(self.blk5, text="5. Arduino Trigger Sync", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        ard_f = ctk.CTkFrame(self.blk5, fg_color="transparent")
        ard_f.pack(fill="x", padx=10, pady=5)
        
        ports = self.app.arduino.get_available_ports()
        self.port_combo = ctk.CTkComboBox(ard_f, values=ports if ports else ["No Ports Found"], width=120)
        self.port_combo.pack(side="left", padx=5)
        ctk.CTkButton(ard_f, text="Refresh", width=80, command=self.refresh_ports).pack(side="left", padx=5)
        self.btn_connect = ctk.CTkButton(ard_f, text="Connect (Manual)", width=120, command=self.connect_arduino)
        self.btn_connect.pack(side="left", padx=5)
        
        self.chk_auto_trigger_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(ard_f, text="Auto-Trigger on Record", variable=self.chk_auto_trigger_var).pack(side="right", padx=10)
        
        self.update_workflow_ui()

    def update_workflow_ui(self):
        choice = self.workflow_var.get()
        if choice == "Blackmagic SDI":
            self.tuning_frame.pack_forget()
            self.blk5.pack_forget()
        else:
            self.tuning_frame.pack(fill="x", padx=10, pady=10)
            self.blk5.pack(fill="x", padx=10, pady=5)

    def browse_directory(self):
        new_dir = filedialog.askdirectory(title="Select MoCap Save Directory", initialdir=self.app.proj_mgr.base_path)
        if new_dir:
            self.app.proj_mgr.set_base_path(new_dir)
            self.lbl_save_dir.configure(text=new_dir)
            self.app.log(f"Base save directory set to: {new_dir}")

    def update_exposure_label(self, value):
        val = int(round(float(value)))
        denominator = 2 ** abs(val)
        self.lbl_exposure.configure(text=f"Exposure: {val} (1/{denominator}s)")
        self._clamp_exposure_to_fps() # Check warning dynamically

    def update_gain_label(self, value):
        self.lbl_gain.configure(text=f"Gain: {int(value)}")

    def _clamp_exposure_to_fps(self):
        """
        Calculates if the current exposure time exceeds the frame interval (1/FPS)
        and displays a warning instead of rigidly clamping the slider.
        """
        try:
            fps = int(self.fps_entry.get())
            if fps <= 0:
                return
        except ValueError:
            return

        frame_period_s = 1.0 / fps
        current_val = int(round(self.exposure_slider.get()))
        shutter_s = 1.0 / (2 ** abs(current_val))
        
        # Readout time for full 720p sensor in trigger mode is roughly 18ms.
        total_cycle = shutter_s + 0.018
        
        if total_cycle > frame_period_s:
            max_safe_exposure_s = frame_period_s - 0.018
            if max_safe_exposure_s <= 0:
                self.lbl_exposure_warn.configure(text=f"Warnung: {fps} FPS ist unmöglich (Sensor braucht 18ms).")
            else:
                self.lbl_exposure_warn.configure(text=f"Warnung: Zyklus zu lang! Framerate wird sich halbieren.")
        else:
            self.lbl_exposure_warn.configure(text="")

    def save_preset(self):
        name = self.preset_name_entry.get()
        if not name:
            self.app.log("Please enter a preset name.", "error")
            return
            
        data = {
            "camera_type": self.workflow_var.get(),
            "resolution": self.res_combo.get(),
            "exposure": self.exposure_slider.get(),
            "gain": self.gain_slider.get(),
            "uvc_trigger": self.chk_uvc_trigger_var.get(),
            "fps": self.fps_entry.get(),
            "arduino_port": self.port_combo.get(),
            "arduino_auto_trigger": self.chk_auto_trigger_var.get()
        }
        
        # Charuco is moved to preview tab, we should still save it if possible, or let preview_tab handle its own preset. 
        # For now, let's grab it from preview_tab if it exists.
        if hasattr(self.app, 'preview_tab'):
            data["charuco_dict"] = self.app.preview_tab.charuco_dict.get()
            data["charuco_x"] = self.app.preview_tab.charuco_x.get()
            data["charuco_y"] = self.app.preview_tab.charuco_y.get()
            data["charuco_sq_size"] = self.app.preview_tab.charuco_sq_size.get()
            data["charuco_marker_size"] = self.app.preview_tab.charuco_marker_size.get()
            
        if hasattr(self.app, 'rotation_menus'):
            rotations = {}
            for idx, menu in self.app.rotation_menus.items():
                rotations[str(idx)] = menu.get()
            data["rotations"] = rotations
            
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
            wf = data.get("camera_type", "USB Webcams")
            self.workflow_var.set(wf)
            self.update_workflow_ui()
            
            self.res_combo.set(data.get("resolution", "1280x720 (720p)"))
            self.gain_slider.set(data.get("gain", 0))
            self.update_gain_label(data.get("gain", 0))
            self.chk_uvc_trigger_var.set(data.get("uvc_trigger", True))

            self.fps_entry.delete(0, 'end')
            self.fps_entry.insert(0, data.get("fps", "50"))

            self._clamp_exposure_to_fps()
            saved_exp = data.get("exposure", -9)
            # Entferne den Zwang, wir setzen einfach den geladenen Wert.
            self.exposure_slider.set(saved_exp)
            self.update_exposure_label(saved_exp)
            
            arduino_port = data.get("arduino_port", "")
            if arduino_port and arduino_port in self.port_combo._values:
                self.port_combo.set(arduino_port)
            self.chk_auto_trigger_var.set(data.get("arduino_auto_trigger", True))
            
            if hasattr(self.app, 'preview_tab'):
                self.app.preview_tab.charuco_dict.set(data.get("charuco_dict", "DICT_4X4_50"))
                self.app.preview_tab.charuco_x.delete(0, 'end')
                self.app.preview_tab.charuco_x.insert(0, data.get("charuco_x", "5"))
                self.app.preview_tab.charuco_y.delete(0, 'end')
                self.app.preview_tab.charuco_y.insert(0, data.get("charuco_y", "3"))
                self.app.preview_tab.charuco_sq_size.delete(0, 'end')
                self.app.preview_tab.charuco_sq_size.insert(0, data.get("charuco_sq_size", "51"))
                self.app.preview_tab.charuco_marker_size.delete(0, 'end')
                self.app.preview_tab.charuco_marker_size.insert(0, data.get("charuco_marker_size", "38"))
                self.app.preview_tab.update_charuco_preview()
            
            rotations = data.get("rotations", {})
            if hasattr(self.app, 'rotation_menus'):
                for idx_str, val in rotations.items():
                    idx = int(idx_str)
                    if idx in self.app.rotation_menus:
                        self.app.rotation_menus[idx].set(val)
                        deg = int(val.split('°')[0])
                        self.app.recorder.set_camera_rotation(idx, deg)
            
            self.app.log(f"Preset '{name}' loaded.", "success")

    def initialize_system_cmd(self):
        self.app.log("Initializing System...")
        self.btn_init_system.configure(state="disabled", text="Initializing...")
        
        def init_task():
            cam_type = self.workflow_var.get()
            trigger_on = self.chk_uvc_trigger_var.get()
            
            try:
                target_fps = int(self.fps_entry.get())
            except ValueError:
                target_fps = 50
                
            # 1. Auto-connect Arduino if not connected
            if cam_type == "USB Webcams" and not self.app.arduino.is_connected:
                port = self.port_combo.get()
                if port and port != "No Ports Found":
                    self.app.log(f"Auto-connecting to Arduino on {port}...")
                    if self.app.arduino.connect(port):
                        self.app.log("Arduino connected!", level="success")
                        self.btn_connect.configure(text="Connected", state="disabled")
                    else:
                        self.app.log(f"Failed to connect Arduino on {port}. Trigger will not work.", "error")
            
            if cam_type == "USB Webcams" and trigger_on and not self.app.arduino.is_connected:
                self.app.log("⚠️ No Arduino connected! Falling back to free-run mode (trigger disabled).", "error")
                trigger_on = False

            # 2. CRITICAL FIX: Start Arduino trigger BEFORE touching PyAV!
            # If the camera is already in hardware trigger mode from a previous run,
            # stopping PyAV or re-opening the camera will DEADLOCK if the Arduino is not sending pulses.
            if cam_type == "USB Webcams" and self.app.arduino.is_connected:
                self.app.arduino.set_fps(target_fps)
                self.app.arduino.start_trigger()

            # 3. Cleanly stop existing PyAV workers (they will now exit safely because trigger is pulsing)
            self.app.recorder.stop_workers()
            
            # 4. Open Cameras
            res_str = self.res_combo.get().split(' ')[0]
            target_w, target_h = map(int, res_str.split('x'))
            
            # Force USB bus to 120fps to allow high polling rate for hardware trigger
            cam_fps = 120 if trigger_on and cam_type == "USB Webcams" else target_fps
            fmt = "MJPG" 
                
            self.app.camera_indices = self.app.cam_mgr.find_and_open_cameras(
                max_index=6, 
                camera_type=cam_type,
                target_w=target_w,
                target_h=target_h,
                target_fps=cam_fps,
                target_format=fmt,
                exposure_val=int(self.exposure_slider.get()) if cam_type == "USB Webcams" else None,
                gain_val=int(self.gain_slider.get()) if cam_type == "USB Webcams" else None,
                trigger_on=trigger_on if cam_type == "USB Webcams" else None
            )
            self.app.log(f"Cameras found: {len(self.app.camera_indices)} ({self.app.camera_indices})", "success")
            
            # Must run GUI updates in the main thread!
            self.app.after(0, self.app.preview_tab.setup_preview_grid)
            
            # 5. Start PyAV Workers
            self.app.recorder.start_workers(self.app.cam_mgr.cameras, target_fps=target_fps)
            self.app.log("Workers started. Go to Live Preview tab to see feeds.")
            
            # 6. Start Arduino Trigger
            if cam_type == "USB Webcams" and self.app.arduino.is_connected and trigger_on:
                self.app.log(f"Hardware Trigger STARTED at {target_fps} FPS!", level="success")
            elif self.app.arduino.is_connected:
                self.app.arduino.stop_trigger() # Turn off if not needed
                
            self.app.after(0, lambda: self.btn_init_system.configure(state="normal", text="Initialize System & Start Preview"))
            
        threading.Thread(target=init_task).start()

    # sync_exposure_cmd() removed – 'Update Settings Live' was a duplicate of
    # initialize_system_cmd(). A single 'Initialize System & Start Preview'
    # button now handles both first-run init and live settings updates.

    def refresh_ports(self):
        ports = self.app.arduino.get_available_ports()
        if ports:
            self.port_combo.configure(values=ports)
            if self.port_combo.get() not in ports:
                self.port_combo.set(ports[0])
        else:
            self.port_combo.configure(values=["No Ports Found"])
            self.port_combo.set("No Ports Found")
            
    def connect_arduino(self):
        port = self.port_combo.get()
        if self.app.arduino.connect(port):
            self.app.log("Arduino connected!", level="success")
            self.btn_connect.configure(text="Connected", state="disabled")
