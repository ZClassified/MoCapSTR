import tkinter as tk
import customtkinter as ctk
from camera_manager import CameraManager
from arduino_sync import ArduinoSync
import cv2
from PIL import Image
import threading

# Configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MoCapSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OV9281 MoCap Sync Controller")
        self.geometry("900x700")

        self.cam_mgr = CameraManager()
        self.arduino = ArduinoSync()
        
        self.camera_indices = []
        
        self.build_ui()
        
    def build_ui(self):
        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Panel (Controls)
        self.left_panel = ctk.CTkFrame(self)
        self.left_panel.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Right Panel (Status / Preview)
        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        self.build_camera_controls(self.left_panel)
        self.build_arduino_controls(self.left_panel)
        self.build_status_panel(self.right_panel)

    def build_camera_controls(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame, text="Camera Settings", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 10))
        
        self.btn_scan = ctk.CTkButton(frame, text="Scan Cameras", command=self.scan_cameras)
        self.btn_scan.pack(fill="x", pady=5)
        
        self.lbl_cams_found = ctk.CTkLabel(frame, text="Cameras found: 0")
        self.lbl_cams_found.pack(anchor="w")

        # Resolution
        ctk.CTkLabel(frame, text="Resolution:").pack(anchor="w", pady=(10, 0))
        self.res_combo = ctk.CTkComboBox(frame, values=["1280x800", "1280x720", "640x400"])
        self.res_combo.pack(fill="x")

        # Exposure Slider
        self.lbl_exposure = ctk.CTkLabel(frame, text="Exposure (Shutter Speed): 1/32s")
        self.lbl_exposure.pack(anchor="w", pady=(10, 0))
        self.exposure_slider = ctk.CTkSlider(frame, from_=-11, to=-3, number_of_steps=8, command=self.update_exposure_label)
        self.exposure_slider.set(-5)
        self.exposure_slider.pack(fill="x")
        
        self.btn_apply_cams = ctk.CTkButton(frame, text="Apply Camera Settings", command=self.apply_camera_settings)
        self.btn_apply_cams.pack(fill="x", pady=15)

    def build_arduino_controls(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=20)
        
        ctk.CTkLabel(frame, text="Arduino Hardware Sync", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 10))
        
        # COM Port Selection
        ports = ArduinoSync.get_available_ports()
        self.port_combo = ctk.CTkComboBox(frame, values=ports if ports else ["No Ports Found"])
        self.port_combo.pack(fill="x", pady=5)
        
        self.btn_connect = ctk.CTkButton(frame, text="Connect Arduino", command=self.connect_arduino)
        self.btn_connect.pack(fill="x", pady=5)
        
        # FPS Setting
        ctk.CTkLabel(frame, text="Target Framerate (FPS):").pack(anchor="w", pady=(10, 0))
        self.fps_entry = ctk.CTkEntry(frame)
        self.fps_entry.insert(0, "60")
        self.fps_entry.pack(fill="x")
        
        # Trigger Control
        self.btn_start = ctk.CTkButton(frame, text="START SYNC TRIGGER", fg_color="green", hover_color="darkgreen", command=self.start_sync, state="disabled")
        self.btn_start.pack(fill="x", pady=10)
        
        self.btn_stop = ctk.CTkButton(frame, text="STOP SYNC TRIGGER", fg_color="red", hover_color="darkred", command=self.stop_sync, state="disabled")
        self.btn_stop.pack(fill="x", pady=5)

    def build_status_panel(self, parent):
        ctk.CTkLabel(parent, text="System Status", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=10, pady=(10, 10))
        
        self.txt_log = ctk.CTkTextbox(parent, height=500)
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=10)
        self.log("Application started.")
        self.log("Ready to scan cameras and connect Arduino.")

    def log(self, message):
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)

    def update_exposure_label(self, value):
        val = int(value)
        # Exposure in OpenCV DirectShow is typically 2^value seconds
        denominator = 2 ** abs(val)
        self.lbl_exposure.configure(text=f"Exposure (Shutter Speed): 1/{denominator}s")

    def scan_cameras(self):
        self.btn_scan.configure(state="disabled")
        self.log("Scanning for cameras...")
        
        def scan():
            self.camera_indices = self.cam_mgr.find_cameras(5)
            self.lbl_cams_found.configure(text=f"Cameras found: {len(self.camera_indices)} ({self.camera_indices})")
            self.log(f"Found {len(self.camera_indices)} cameras.")
            for idx in self.camera_indices:
                self.cam_mgr.open_camera(idx)
            self.btn_scan.configure(state="normal")
            
        threading.Thread(target=scan).start()

    def apply_camera_settings(self):
        try:
            res_str = self.res_combo.get()
            w, h = map(int, res_str.split('x'))
            fps = int(self.fps_entry.get())
            exp = int(self.exposure_slider.get())
            
            for idx in self.camera_indices:
                res = self.cam_mgr.apply_settings(idx, width=w, height=h, fps=fps, exposure_value=exp)
                self.log(f"Cam {idx} settings applied: {res}")
        except Exception as e:
            self.log(f"Error applying camera settings: {e}")

    def connect_arduino(self):
        port = self.port_combo.get()
        if port and port != "No Ports Found":
            self.log(f"Connecting to Arduino on {port}...")
            if self.arduino.connect(port):
                self.log("Arduino connected successfully!")
                self.btn_connect.configure(text="Connected", fg_color="gray", state="disabled")
                self.btn_start.configure(state="normal")
            else:
                self.log("Failed to connect to Arduino.")

    def start_sync(self):
        try:
            fps = int(self.fps_entry.get())
            self.arduino.set_fps(fps)
            self.arduino.start_trigger()
            self.log(f"Hardware trigger started at {fps} FPS!")
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
        except Exception as e:
            self.log(f"Error starting sync: {e}")

    def stop_sync(self):
        self.arduino.stop_trigger()
        self.log("Hardware trigger stopped.")
        self.btn_stop.configure(state="disabled")
        self.btn_start.configure(state="normal")

    def on_closing(self):
        self.arduino.disconnect()
        self.cam_mgr.close_all()
        self.destroy()

if __name__ == "__main__":
    app = MoCapSyncApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
