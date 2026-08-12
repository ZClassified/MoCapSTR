import customtkinter as ctk
import tkinter as tk
import cv2
from PIL import Image

class PreviewTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.build_ui()
        
    def build_ui(self):
        # Top bar for controls and stats
        self.preview_top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.preview_top_bar.pack(fill="x", padx=10, pady=(10, 0))
        
        # Take Name
        ctk.CTkLabel(self.preview_top_bar, text="Next Take Name:").pack(side="left", padx=(10, 5))
        self.take_name_entry = ctk.CTkEntry(self.preview_top_bar, width=150)
        self.take_name_entry.insert(0, "Take_01")
        self.take_name_entry.pack(side="left", padx=5)
        
        self.btn_record_live = ctk.CTkButton(self.preview_top_bar, text="⏺ START RECORDING", fg_color="darkred", hover_color="red", command=self.app.toggle_record)
        self.btn_record_live.pack(side="left", padx=15)
        
        self.lbl_live_stats = ctk.CTkLabel(self.preview_top_bar, text="Ready | Space: -- GB", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_live_stats.pack(side="left", padx=20)
        
        self.lbl_live_warning = ctk.CTkLabel(self.preview_top_bar, text="", text_color="red", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_live_warning.pack(side="right", padx=10)
        
        # Main content area: Split into Sidebar (Charuco) and Main (Camera Grid)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Sidebar for Charuco Calibration
        self.sidebar = ctk.CTkFrame(self.content_frame, width=280)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.sidebar.pack_propagate(False) # Fixed width
        
        ctk.CTkLabel(self.sidebar, text="Charuco Calibration", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
        self.chk_charuco = ctk.CTkCheckBox(self.sidebar, text="Show Charuco Detection", command=self.on_charuco_toggled)
        self.chk_charuco.pack(pady=(0, 10))
        
        ctk.CTkLabel(self.sidebar, text="Dictionary:").pack(anchor="w", padx=10)
        self.charuco_dict = ctk.CTkComboBox(self.sidebar, values=["DICT_4X4_50", "DICT_4X4_100", "DICT_5X5_50", "DICT_5X5_100", "DICT_6X6_250"])
        self.charuco_dict.set("DICT_4X4_50")
        self.charuco_dict.pack(fill="x", padx=10, pady=(0, 10))
        
        grid_f = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        grid_f.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(grid_f, text="Squares X/Y:").pack(side="left")
        self.charuco_x = ctk.CTkEntry(grid_f, width=40)
        self.charuco_x.insert(0, "5")
        self.charuco_x.pack(side="right")
        ctk.CTkLabel(grid_f, text="x").pack(side="right", padx=5)
        self.charuco_y = ctk.CTkEntry(grid_f, width=40)
        self.charuco_y.insert(0, "3")
        self.charuco_y.pack(side="right")
        
        size_f = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        size_f.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(size_f, text="Square Size (mm):").pack(side="left")
        self.charuco_sq_size = ctk.CTkEntry(size_f, width=60)
        self.charuco_sq_size.insert(0, "51")
        self.charuco_sq_size.pack(side="right")
        
        marker_f = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        marker_f.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(marker_f, text="Marker Size (mm):").pack(side="left")
        self.charuco_marker_size = ctk.CTkEntry(marker_f, width=60)
        self.charuco_marker_size.insert(0, "38")
        self.charuco_marker_size.pack(side="right")
        
        ctk.CTkButton(self.sidebar, text="Update Board Preview", command=self.update_charuco_preview).pack(fill="x", padx=10, pady=10)
        self.lbl_charuco_preview = ctk.CTkLabel(self.sidebar, text="No Preview")
        self.lbl_charuco_preview.pack(pady=5)
        
        # Camera Grid
        self.preview_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.preview_frame.pack(side="right", fill="both", expand=True)
        
        for i in range(2):
            self.preview_frame.grid_rowconfigure(i, weight=1)
        for j in range(3):
            self.preview_frame.grid_columnconfigure(j, weight=1)
            
    def on_charuco_toggled(self):
        show = (self.chk_charuco.get() == 1)
        dict_str = self.charuco_dict.get()
        self.app.recorder.set_charuco_settings(show, dict_str)
        
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
