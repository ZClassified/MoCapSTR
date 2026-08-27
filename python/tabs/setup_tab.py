import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image
import threading
import cv2

def get_recommended_usb_fps(target_fps: int) -> str:
    """
    Calculates the optimal USB polling rate for a given target capture FPS in hardware trigger mode.
    - <= 50 FPS: 60 FPS USB polling (16.6ms slots prevent beat frequency/aliasing, fits 4 cams comfortably)
    - 51-60 FPS: 90 FPS USB polling
    - > 60 FPS: 120 FPS USB polling
    """
    if target_fps <= 50:
        return "60"
    elif target_fps <= 60:
        return "90"
    else:
        return "120"

class SetupTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.build_ui()
        
    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        
        # Helper for card frames
        def create_card(parent, title):
            card = ctk.CTkFrame(parent, corner_radius=10)
            card.pack(fill="x", padx=15, pady=6)
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", padx=15, pady=(10, 5))
            inner_frame = ctk.CTkFrame(card, fg_color="transparent")
            inner_frame.pack(fill="x", padx=15, pady=(0, 10))
            return card, inner_frame

        # ==========================================
        # CARD 1: Project & Presets
        # ==========================================
        self.card_project, proj_inner = create_card(self, "1. Project & Presets")
        proj_inner.grid_columnconfigure(1, weight=1)
        
        # --- Project Name & Save Dir ---
        ctk.CTkLabel(proj_inner, text="Project Name:").grid(row=0, column=0, sticky="w", pady=4)
        self.proj_name_entry = ctk.CTkEntry(proj_inner)
        self.proj_name_entry.insert(0, "My_MoCap_Project")
        self.proj_name_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=4)
        
        ctk.CTkLabel(proj_inner, text="Save Directory:").grid(row=1, column=0, sticky="w", pady=4)
        dir_f = ctk.CTkFrame(proj_inner, fg_color="transparent")
        dir_f.grid(row=1, column=1, sticky="ew", padx=10, pady=4)
        self.lbl_save_dir = ctk.CTkLabel(dir_f, text=self.app.proj_mgr.base_path, text_color="gray", anchor="w")
        self.lbl_save_dir.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(dir_f, text="Browse...", width=80, command=self.browse_directory).pack(side="right", padx=(5,0))
        
        # --- Codec ---
        ctk.CTkLabel(proj_inner, text="Codec:").grid(row=2, column=0, sticky="w", pady=4)
        self.codec_combo = ctk.CTkComboBox(proj_inner, values=list(self.app.recorder.get_supported_codecs().keys()))
        self.codec_combo.grid(row=2, column=1, sticky="ew", padx=10, pady=4)

        # --- Divider ---
        ctk.CTkFrame(proj_inner, height=2, fg_color=("gray70", "gray30")).grid(row=3, column=0, columnspan=2, sticky="ew", pady=8)

        # --- Presets ---
        ctk.CTkLabel(proj_inner, text="Preset:").grid(row=4, column=0, sticky="w", pady=4)
        pre_f = ctk.CTkFrame(proj_inner, fg_color="transparent")
        pre_f.grid(row=4, column=1, sticky="ew", padx=10, pady=4)
        
        self.preset_combo = ctk.CTkComboBox(pre_f, values=["Default"] + self.app.preset_mgr.get_preset_names(), width=140)
        self.preset_combo.pack(side="left", padx=(0, 5))
        ctk.CTkButton(pre_f, text="Load", width=60, command=self.load_preset).pack(side="left")
        
        self.preset_name_entry = ctk.CTkEntry(pre_f, placeholder_text="New Preset Name", width=140)
        self.preset_name_entry.pack(side="left", padx=(15, 5))
        ctk.CTkButton(pre_f, text="Save", width=60, command=self.save_preset).pack(side="left")

        # --- Workflow Selection ---
        ctk.CTkLabel(proj_inner, text="Workflow:").grid(row=5, column=0, sticky="w", pady=4)
        wf_f = ctk.CTkFrame(proj_inner, fg_color="transparent")
        wf_f.grid(row=5, column=1, sticky="ew", padx=10, pady=4)
        self.workflow_var = ctk.StringVar(value="USB Webcams")
        
        r1 = ctk.CTkRadioButton(wf_f, text="Option 1: Innomaker USB (+ Arduino Trigger)", variable=self.workflow_var, value="USB Webcams", command=self.update_workflow_ui)
        r1.pack(side="left", padx=(0, 20))
        r2 = ctk.CTkRadioButton(wf_f, text="Option 2: Blackmagic SDI (Genlock)", variable=self.workflow_var, value="Blackmagic SDI", command=self.update_workflow_ui)
        r2.pack(side="left")

        # --- Divider Between Cards ---
        ctk.CTkFrame(self, height=2, fg_color=("gray70", "gray30")).pack(fill="x", padx=15, pady=(4, 4))

        # ==========================================
        # CARD 2: Hardware Configuration
        # ==========================================
        self.card_hardware, hw_inner = create_card(self, "2. Hardware Configuration")
        hw_inner.grid_columnconfigure(1, weight=1)
        
        # --- Camera Basic Settings ---
        ctk.CTkLabel(hw_inner, text="Resolution:").grid(row=0, column=0, sticky="w", pady=4)
        res_options = ["3840x2160 (4K)", "2560x1440 (1440p)", "1920x1080 (1080p)", "1280x800", "1280x720 (720p)", "1024x768", "800x600", "640x480", "640x400", "320x240"]
        self.res_combo = ctk.CTkComboBox(hw_inner, values=res_options)
        self.res_combo.set("1280x720 (720p)")
        self.res_combo.grid(row=0, column=1, sticky="ew", padx=10, pady=4)
        
        ctk.CTkLabel(hw_inner, text="Target FPS:").grid(row=1, column=0, sticky="w", pady=4)
        
        fps_frame = ctk.CTkFrame(hw_inner, fg_color="transparent")
        fps_frame.grid(row=1, column=1, sticky="ew", padx=10, pady=4)
        
        self.fps_entry = ctk.CTkEntry(fps_frame, width=60)
        self.fps_entry.insert(0, "30")
        self.fps_entry.pack(side="left")
        self.fps_entry.bind("<FocusOut>", lambda e: self.on_fps_changed())
        self.fps_entry.bind("<Return>",   lambda e: self.on_fps_changed())
        
        ctk.CTkLabel(fps_frame, text="USB Polling:").pack(side="left", padx=(15, 5))
        self.usb_fps_combo = ctk.CTkComboBox(
            fps_frame, 
            values=["60", "90", "120", "30"], 
            width=70,
            command=lambda _: self._validate_usb_fps()
        )
        self.usb_fps_combo.set("60")
        self.usb_fps_combo.pack(side="left")

        # Dynamic warning/info badge for USB Polling & FPS compatibility (hidden by default)
        self.lbl_usb_warn = ctk.CTkLabel(hw_inner, text="", font=ctk.CTkFont(size=11), anchor="w")

        # --- Hardware Tuning (USB Only) ---
        self.tuning_frame = ctk.CTkFrame(hw_inner, fg_color="transparent")
        self.tuning_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 2))
        self.tuning_frame.grid_columnconfigure(1, weight=1)

        self.lbl_exposure = ctk.CTkLabel(self.tuning_frame, text="Exposure: -8 (1/256s)", width=140, anchor="w")
        self.lbl_exposure.grid(row=0, column=0, sticky="w", pady=4)
        self.exposure_slider = ctk.CTkSlider(self.tuning_frame, from_=-11, to=-3, number_of_steps=8, command=self.update_exposure_label)
        self.exposure_slider.set(-8)
        self.exposure_slider.grid(row=0, column=1, sticky="ew", padx=10, pady=4)
        
        self.lbl_exposure_warn = ctk.CTkLabel(self.tuning_frame, text="", text_color="red", font=ctk.CTkFont(size=11))

        # --- Arduino Sync (USB Only) ---
        self.arduino_frame = ctk.CTkFrame(hw_inner, fg_color="transparent")
        self.arduino_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.arduino_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkFrame(self.arduino_frame, height=2, fg_color=("gray70", "gray30")).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(6, 8))
        
        self.chk_uvc_trigger_var = ctk.BooleanVar(value=True)
        self.chk_uvc_trigger = ctk.CTkCheckBox(self.arduino_frame, text="Enable UVC Hardware Trigger", variable=self.chk_uvc_trigger_var)
        self.chk_uvc_trigger.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))
        
        ctk.CTkLabel(self.arduino_frame, text="Arduino Port:").grid(row=2, column=0, sticky="w", pady=4)
        
        ard_f = ctk.CTkFrame(self.arduino_frame, fg_color="transparent")
        ard_f.grid(row=2, column=1, sticky="ew", padx=10, pady=4)
        
        ports = self.app.arduino.get_available_ports()
        self.port_combo = ctk.CTkComboBox(ard_f, values=ports if ports else ["No Ports Found"])
        self.port_combo.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(ard_f, text="Refresh", width=80, command=self.refresh_ports).pack(side="left", padx=(10, 0))
        self.btn_connect = ctk.CTkButton(ard_f, text="Connect", width=100, command=self.connect_arduino)
        self.btn_connect.pack(side="left", padx=(10, 0))
        
        # ==========================================
        # Primary Action Button & Status
        # ==========================================
        self.btn_init_system = ctk.CTkButton(
            self,
            text="Initialize System & Start Preview",
            command=self.initialize_system_cmd,
            fg_color="#1f538d", hover_color="#14375e",
            height=48, font=ctk.CTkFont(weight="bold", size=15)
        )
        self.btn_init_system.pack(fill="x", padx=15, pady=(16, 4))

        self.lbl_init_status = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(weight="bold", size=13),
            anchor="center"
        )
        self.lbl_init_status.pack(fill="x", padx=15, pady=(0, 12))

        self.on_fps_changed() # Initialize warnings and USB FPS default
        self.update_workflow_ui()

    def update_workflow_ui(self):
        choice = self.workflow_var.get()
        if choice == "Blackmagic SDI":
            self.tuning_frame.grid_remove()
            self.arduino_frame.grid_remove()
        else:
            self.tuning_frame.grid()
            self.arduino_frame.grid()

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

    def on_fps_changed(self):
        try:
            fps = int(self.fps_entry.get())
            try:
                usb_fps = int(self.usb_fps_combo.get())
            except ValueError:
                usb_fps = 0
            
            # If current USB polling is strictly lower than target FPS, or is 30 on 20/24/25 FPS,
            # auto-suggest the safe recommended value
            if usb_fps < fps or (usb_fps == 30 and fps in [20, 24, 25]):
                self.usb_fps_combo.set(get_recommended_usb_fps(fps))
        except ValueError:
            pass
            
        self._clamp_exposure_to_fps()
        self._validate_usb_fps()

    def _validate_usb_fps(self):
        """
        Validates the chosen USB polling rate against target FPS to warn the user
        if a beat-frequency drop or bandwidth bottleneck is expected.
        """
        try:
            fps = int(self.fps_entry.get())
            usb_fps = int(self.usb_fps_combo.get())
        except ValueError:
            self.lbl_usb_warn.configure(text="")
            self.lbl_usb_warn.grid_remove()
            return

        recommended = get_recommended_usb_fps(fps)
        
        # Critical conflict: 30 FPS USB polling on 20/24/25 FPS trigger leads to 1/2 FPS
        if usb_fps == 30 and fps in [20, 24, 25]:
            self.lbl_usb_warn.configure(
                text=f"⚠️ USB Polling (30) führt bei {fps} FPS zu Framerate-Halbierung (~15 FPS)! Mindestens 60 empfohlen.",
                text_color="#e63946"
            )
            self.lbl_usb_warn.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(1, 3))
        elif usb_fps < fps:
            self.lbl_usb_warn.configure(
                text=f"⚠️ USB Polling ({usb_fps}) ist kleiner als Ziel-FPS ({fps})! Dropping erwartet. Empfohlen: {recommended}.",
                text_color="#e63946"
            )
            self.lbl_usb_warn.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(1, 3))
        elif usb_fps == 30 and fps == 30:
            self.lbl_usb_warn.configure(
                text=f"Hinweis: Bei 30 FPS Trigger ist 60 USB Polling stabiler gegen Phasen-Drift.",
                text_color="#f77f00"
            )
            self.lbl_usb_warn.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(1, 3))
        else:
            self.lbl_usb_warn.configure(text="")
            self.lbl_usb_warn.grid_remove()

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
            self.lbl_exposure_warn.grid(row=1, column=1, sticky="w", padx=10, pady=(0, 2))
        else:
            self.lbl_exposure_warn.configure(text="")
            self.lbl_exposure_warn.grid_remove()

    def save_preset(self):
        name = self.preset_name_entry.get()
        if not name:
            self.app.log("Please enter a preset name.", "error")
            return
            
        data = {
            "camera_type": self.workflow_var.get(),
            "resolution": self.res_combo.get(),
            "exposure": self.exposure_slider.get(),
            "uvc_trigger": self.chk_uvc_trigger_var.get(),
            "fps": self.fps_entry.get(),
            "usb_fps": self.usb_fps_combo.get(),
            "arduino_port": self.port_combo.get(),
            # "arduino_auto_trigger" removed
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
            self.chk_uvc_trigger_var.set(data.get("uvc_trigger", True))

            self.fps_entry.delete(0, 'end')
            self.fps_entry.insert(0, data.get("fps", "30"))
            
            if "usb_fps" in data:
                self.usb_fps_combo.set(data["usb_fps"])
            else:
                self.usb_fps_combo.set("60")

            self._clamp_exposure_to_fps()
            self._validate_usb_fps()
            saved_exp = data.get("exposure", -8)
            # Entferne den Zwang, wir setzen einfach den geladenen Wert.
            self.exposure_slider.set(saved_exp)
            self.update_exposure_label(saved_exp)
            
            arduino_port = data.get("arduino_port", "")
            if arduino_port and arduino_port in self.port_combo._values:
                self.port_combo.set(arduino_port)
            # arduino_auto_trigger load removed
            
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
        self.btn_init_system.configure(state="disabled", text="Initialisiere Hardware & Kameras...", fg_color="#555555")
        self.lbl_init_status.configure(text="⏳ Suche Arduino & Kameras (bitte kurz warten)...", text_color="#3a86ff")
        
        def init_task():
            success = False
            error_msg = None
            try:
                cam_type = self.workflow_var.get()
                trigger_on = self.chk_uvc_trigger_var.get()
                
                try:
                    target_fps = int(self.fps_entry.get())
                except ValueError:
                    target_fps = 30
                    
                # 1. Auto-connect Arduino if not connected
                if cam_type == "USB Webcams" and not self.app.arduino.is_connected:
                    port = self.port_combo.get()
                    if port and port != "No Ports Found":
                        self.app.log(f"Auto-connecting to Arduino on {port}...")
                        self.app.after(0, lambda: self.lbl_init_status.configure(text=f"⏳ Verbinde Arduino an {port}...", text_color="#3a86ff"))
                        if self.app.arduino.connect(port):
                            self.app.log("Arduino connected!", level="success")
                            self.app.after(0, lambda: self.btn_connect.configure(text="Connected", state="disabled"))
                        else:
                            self.app.log(f"Failed to connect Arduino on {port}. Trigger will not work.", "error")
                
                if cam_type == "USB Webcams" and trigger_on and not self.app.arduino.is_connected:
                    self.app.log("⚠️ No Arduino connected! Falling back to free-run mode (trigger disabled).", "error")
                    trigger_on = False

                # 2. Start Arduino trigger if trigger_on is requested
                if cam_type == "USB Webcams" and self.app.arduino.is_connected and trigger_on:
                    self.app.after(0, lambda: self.lbl_init_status.configure(text=f"⏳ Starte Arduino-Trigger ({target_fps} FPS)...", text_color="#3a86ff"))
                    self.app.arduino.set_fps(target_fps)
                    self.app.arduino.start_trigger()

                # 3. Cleanly stop existing PyAV workers
                self.app.recorder.stop_workers()
                
                # 4. Open Cameras (Always opened safely in Free-Run first to guarantee 0s DirectShow negotiation)
                self.app.after(0, lambda: self.lbl_init_status.configure(text="⏳ Öffne Kameras & setze Videoformate...", text_color="#3a86ff"))
                res_str = self.res_combo.get().split(' ')[0]
                target_w, target_h = map(int, res_str.split('x'))
                
                try:
                    usb_fps = int(self.usb_fps_combo.get())
                except ValueError:
                    usb_fps = target_fps
                
                cam_fps = usb_fps if trigger_on and cam_type == "USB Webcams" else target_fps
                fmt = "MJPG" 
                    
                self.app.camera_indices = self.app.cam_mgr.find_and_open_cameras(
                    max_index=6, 
                    camera_type=cam_type,
                    target_w=target_w,
                    target_h=target_h,
                    target_fps=cam_fps,
                    target_format=fmt,
                    exposure_val=int(self.exposure_slider.get()) if cam_type == "USB Webcams" else None,
                    gain_val=0 if cam_type == "USB Webcams" else None,
                    trigger_on=False # Always negotiate stream in free-run first
                )
                self.app.log(f"Cameras found: {len(self.app.camera_indices)} ({self.app.camera_indices})", "success")
                
                if len(self.app.camera_indices) > 0:
                    # Must run GUI updates in the main thread!
                    self.app.after(0, self.app.preview_tab.setup_preview_grid)
                    
                    # 5. Start PyAV Workers
                    self.app.recorder.start_workers(self.app.cam_mgr.cameras, target_fps=target_fps)
                    self.app.log("Workers started. Go to Live Preview tab to see feeds.")
                    
                    # 6. Engage Hardware Trigger on running streams
                    if cam_type == "USB Webcams" and self.app.arduino.is_connected and trigger_on:
                        self.app.cam_mgr.set_trigger_mode(True)
                        self.app.log(f"Hardware Trigger STARTED at {target_fps} FPS!", level="success")
                    else:
                        if self.app.arduino.is_connected:
                            self.app.arduino.stop_trigger()
                        self.app.cam_mgr.set_trigger_mode(False)

                    success = True
                else:
                    error_msg = "Keine Kameras gefunden! Bitte USB-Kabel und Erkennung prüfen."
                    
            except Exception as e:
                self.app.log(f"Initialization error: {e}", "error")
                import traceback
                traceback.print_exc()
                error_msg = str(e)
            finally:
                if success:
                    def on_success():
                        cam_count = len(self.app.camera_indices)
                        self.btn_init_system.configure(
                            state="normal",
                            text="✓ System bereit (Klick zum Aktualisieren)",
                            fg_color="#2a9d8f",
                            hover_color="#21867a"
                        )
                        self.lbl_init_status.configure(
                            text=f"✓ {cam_count} Kamera(s) aktiv! Live-Vorschau gestartet.",
                            text_color="#2a9d8f"
                        )
                        # Switch to Live Preview Tab automatically
                        self.app.tabview.set("2. Live Preview")
                    self.app.after(0, on_success)
                else:
                    def on_fail():
                        msg = error_msg or "Keine Kameras gefunden!"
                        self.btn_init_system.configure(
                            state="normal",
                            text="⚠️ Initialisierung fehlgeschlagen — Erneut versuchen",
                            fg_color="#e63946",
                            hover_color="#c1121f"
                        )
                        self.lbl_init_status.configure(
                            text=f"⚠️ {msg}",
                            text_color="#e63946"
                        )
                    self.app.after(0, on_fail)
            
        threading.Thread(target=init_task, daemon=True).start()

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
