import customtkinter as ctk
import tkinter as tk

class PreviewTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.build_ui()
        
    def build_ui(self):
        # Top bar for controls and stats
        self.preview_top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.preview_top_bar.pack(fill="x", padx=10, pady=(10, 0))
        
        self.btn_record_live = ctk.CTkButton(self.preview_top_bar, text="⏺ START RECORDING", fg_color="darkred", hover_color="red", command=self.app.toggle_record)
        self.btn_record_live.pack(side="left", padx=10)
        
        self.chk_charuco = ctk.CTkCheckBox(self.preview_top_bar, text="Show Charuco", command=self.on_charuco_toggled)
        self.chk_charuco.pack(side="left", padx=10)
        
        self.lbl_live_stats = ctk.CTkLabel(self.preview_top_bar, text="Ready | Space: -- GB", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_live_stats.pack(side="left", padx=20)
        
        self.lbl_live_warning = ctk.CTkLabel(self.preview_top_bar, text="", text_color="red", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_live_warning.pack(side="right", padx=10)

        # We will dynamically create a grid of up to 6 labels
        self.preview_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.preview_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        for i in range(2):
            self.preview_frame.grid_rowconfigure(i, weight=1)
        for j in range(3):
            self.preview_frame.grid_columnconfigure(j, weight=1)
            
    def on_charuco_toggled(self):
        show = (self.chk_charuco.get() == 1)
        dict_str = self.app.setup_tab.charuco_dict.get()
        self.app.recorder.set_charuco_settings(show, dict_str)
        
    def setup_preview_grid(self):
        for widget in self.preview_frame.winfo_children():
            widget.destroy()
        self.app.preview_labels.clear()
        self.app.camera_enable_vars.clear()
        
        for i, idx in enumerate(self.app.camera_indices):
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
            self.app.preview_labels[idx] = lbl
            
            # Checkbox for enable/disable
            enable_var = ctk.IntVar(value=1)
            self.app.camera_enable_vars[idx] = enable_var
            chk = ctk.CTkCheckBox(cam_frame, text="Aufnahme aktiv", variable=enable_var)
            chk.grid(row=1, column=0, pady=(5,0))
            
            # Rotation Dropdown
            def make_rot_callback(cam_id):
                def callback(choice):
                    deg = int(choice.split('°')[0])
                    self.app.recorder.set_camera_rotation(cam_id, deg)
                return callback
            
            rot_menu = ctk.CTkOptionMenu(cam_frame, values=["0°", "90° (Portrait)", "180°", "270° (Portrait)"], command=make_rot_callback(idx))
            rot_menu.set("0°")
            rot_menu.grid(row=2, column=0, pady=5, sticky="ew")
            
            if not hasattr(self.app, 'rotation_menus'):
                self.app.rotation_menus = {}
            self.app.rotation_menus[idx] = rot_menu
