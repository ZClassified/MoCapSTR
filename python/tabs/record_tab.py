import customtkinter as ctk
from tkinter import filedialog

class RecordTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.build_ui()
        
    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        
        # Project Config
        frame_proj = ctk.CTkFrame(self)
        frame_proj.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame_proj, text="Project Settings", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10,0))
        
        # Save Directory
        ctk.CTkLabel(frame_proj, text="Base Save Directory:").pack(anchor="w", padx=10, pady=(10,0))
        dir_frame = ctk.CTkFrame(frame_proj, fg_color="transparent")
        dir_frame.pack(fill="x", padx=10, pady=5)
        self.lbl_save_dir = ctk.CTkLabel(dir_frame, text=self.app.proj_mgr.base_path, text_color="gray")
        self.lbl_save_dir.pack(side="left", fill="x", expand=True, padx=(0,10))
        self.btn_browse = ctk.CTkButton(dir_frame, text="Browse...", width=100, command=self.browse_directory)
        self.btn_browse.pack(side="right")
        
        ctk.CTkLabel(frame_proj, text="Project Name (e.g. LivingRoom_Setup_1):").pack(anchor="w", padx=10, pady=(15,0))
        self.proj_name_entry = ctk.CTkEntry(frame_proj)
        self.proj_name_entry.insert(0, "My_MoCap_Project")
        self.proj_name_entry.pack(fill="x", padx=10, pady=(0, 10))
        
        # Recording Config
        frame_rec = ctk.CTkFrame(self)
        frame_rec.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame_rec, text="Recording Setup", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10,0))
        
        codec_frame = ctk.CTkFrame(frame_rec, fg_color="transparent")
        codec_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(codec_frame, text="Video Codec:").pack(side="left")
        
        self.btn_codec_info = ctk.CTkButton(codec_frame, text="ℹ️ Info", width=50, height=24, command=self.show_codec_info)
        self.btn_codec_info.pack(side="right", padx=(5, 0))
        
        self.codec_combo = ctk.CTkComboBox(codec_frame, values=list(self.app.recorder.get_supported_codecs().keys()))
        self.codec_combo.pack(side="right", fill="x", expand=True, padx=(10, 0))
        
        ctk.CTkLabel(frame_rec, text="Record Type:").pack(anchor="w", padx=10)
        self.record_type = ctk.StringVar(value="motion")
        ctk.CTkRadioButton(frame_rec, text="Motion Take (Normal)", variable=self.record_type, value="motion").pack(anchor="w", padx=10, pady=5)
        ctk.CTkRadioButton(frame_rec, text="Calibration (Charuco)", variable=self.record_type, value="calibration").pack(anchor="w", padx=10, pady=5)
        
        # Big Record Buttons
        self.btn_record = ctk.CTkButton(self, text="⏺ START RECORDING", fg_color="darkred", hover_color="red", height=60, font=ctk.CTkFont(size=24, weight="bold"), command=self.app.toggle_record)
        self.btn_record.pack(fill="x", padx=10, pady=20)
        
    def browse_directory(self):
        new_dir = filedialog.askdirectory(title="Select MoCap Save Directory", initialdir=self.app.proj_mgr.base_path)
        if new_dir:
            self.app.proj_mgr.set_base_path(new_dir)
            self.lbl_save_dir.configure(text=new_dir)
            self.app.log(f"Base save directory set to: {new_dir}")
            
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
