import customtkinter as ctk
import time
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'python')))
from arduino_sync import ArduinoSync
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ArduinoTestApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Arduino Trigger Tester")
        self.geometry("400x420")
        
        self.is_recording = False
        self.trigger_started_by_rec = False
        
        self.arduino = ArduinoSync()
        self.arduino.on_toggle_trig_callback = self.on_hw_toggle_trig
        self.arduino.on_toggle_rec_callback = self.on_hw_toggle_rec
        
        # --- UI Elements ---
        ctk.CTkLabel(self, text="Arduino Trigger Test Tool", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=15)
        
        # Port Selection
        port_frame = ctk.CTkFrame(self, fg_color="transparent")
        port_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(port_frame, text="Port:").pack(side="left", padx=5)
        
        self.port_combo = ctk.CTkComboBox(port_frame, values=self.arduino.get_available_ports() or ["No Ports"])
        self.port_combo.pack(side="left", padx=5)
        
        self.btn_refresh = ctk.CTkButton(port_frame, text="🔄", width=30, command=self.refresh_ports)
        self.btn_refresh.pack(side="left", padx=5)
        
        self.btn_connect = ctk.CTkButton(port_frame, text="Connect", command=self.connect_arduino)
        self.btn_connect.pack(side="left", padx=10)
        
        # FPS Selection
        fps_frame = ctk.CTkFrame(self, fg_color="transparent")
        fps_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(fps_frame, text="Target FPS:").pack(side="left", padx=5)
        
        self.fps_entry = ctk.CTkEntry(fps_frame, width=80)
        self.fps_entry.insert(0, "60")
        self.fps_entry.pack(side="left", padx=5)
        
        # Trigger Controls
        self.btn_start = ctk.CTkButton(self, text="▶ START TRIGGER", fg_color="green", hover_color="darkgreen", command=self.start_trigger, state="disabled")
        self.btn_start.pack(pady=10, fill="x", padx=40)
        
        self.btn_stop = ctk.CTkButton(self, text="⏹ STOP TRIGGER", fg_color="red", hover_color="darkred", command=self.stop_trigger, state="disabled")
        self.btn_stop.pack(pady=10, fill="x", padx=40)
        
        # Record Controls (Dummy)
        self.btn_rec = ctk.CTkButton(self, text="⏺ START RECORDING (DUMMY)", fg_color="darkred", hover_color="red", command=self.toggle_record_dummy)
        self.btn_rec.pack(pady=10, fill="x", padx=40)
        
        self.status_label = ctk.CTkLabel(self, text="Status: Disconnected", text_color="gray")
        self.status_label.pack(side="bottom", pady=10)
        
    def refresh_ports(self):
        ports = self.arduino.get_available_ports()
        if ports:
            self.port_combo.configure(values=ports)
            self.port_combo.set(ports[0])
        else:
            self.port_combo.configure(values=["No Ports"])
            self.port_combo.set("No Ports")
            
    def connect_arduino(self):
        port = self.port_combo.get()
        if port == "No Ports":
            return
            
        self.status_label.configure(text=f"Connecting to {port}...")
        self.update()
        
        if self.arduino.connect(port):
            self.status_label.configure(text=f"Status: Connected to {port}", text_color="green")
            self.btn_connect.configure(state="disabled", text="Connected")
            self.btn_start.configure(state="normal")
        else:
            self.status_label.configure(text="Status: Connection Failed", text_color="red")
            
    def start_trigger(self):
        try:
            fps = int(self.fps_entry.get())
        except ValueError:
            fps = 60
            self.fps_entry.delete(0, 'end')
            self.fps_entry.insert(0, "60")
            
        self.arduino.set_fps(fps)
        time.sleep(0.1) # Kurze Pause, damit der Befehl verarbeitet wird
        self.arduino.start_trigger()
        
        self.status_label.configure(text=f"Status: Trigger RUNNING at {fps} FPS", text_color="lightgreen")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        
    def stop_trigger(self):
        self.arduino.stop_trigger()
        self.status_label.configure(text="Status: Trigger STOPPED", text_color="yellow")
        self.btn_stop.configure(state="disabled")
        self.btn_start.configure(state="normal")
        
    def on_hw_toggle_trig(self):
        # We need to run this in the main thread since CustomTkinter UI updates must be on the main thread
        self.after(0, self._handle_toggle_trig)
        
    def _handle_toggle_trig(self):
        if self.arduino.is_running:
            self.stop_trigger()
        else:
            self.start_trigger()
            
    def on_hw_toggle_rec(self):
        # We need to run this in the main thread
        self.after(0, self.toggle_record_dummy)
        
    def toggle_record_dummy(self):
        if not self.is_recording:
            self.is_recording = True
            
            # Logic: Start trigger if it's not running. Remember if WE started it.
            if not self.arduino.is_running:
                self.trigger_started_by_rec = True
                self.start_trigger()
            else:
                self.trigger_started_by_rec = False
                
            self.btn_rec.configure(text="⏹ STOP RECORDING (DUMMY)", fg_color="red", hover_color="darkred")
            self.status_label.configure(text="Status: Recording Started!", text_color="orange")
        else:
            self.is_recording = False
            
            # Logic: Stop trigger ONLY if we were the ones who started it.
            if self.trigger_started_by_rec:
                self.stop_trigger()
                self.trigger_started_by_rec = False
                
            self.btn_rec.configure(text="⏺ START RECORDING (DUMMY)", fg_color="darkred", hover_color="red")
            self.status_label.configure(text="Status: Recording Stopped!", text_color="orange")

if __name__ == "__main__":

    app = ArduinoTestApp()
    app.mainloop()
