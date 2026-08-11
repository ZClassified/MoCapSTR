import customtkinter as ctk
import tkinter as tk
import cv2
import threading
import time

class CameraTestTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.is_scanning = False
        
        # Define formats to test
        self.test_resolutions = [(1920, 1080), (1280, 720), (1024, 768), (800, 600), (640, 480)]
        self.test_fps = [60, 50, 30, 25, 15]
        self.test_fourcc = ["MJPG", "YUY2"]
        
        self.setup_ui()
        
    def setup_ui(self):
        # Split into left (controls) and right (results)
        self.left_panel = ctk.CTkFrame(self, width=300)
        self.left_panel.pack(side="left", fill="y", padx=10, pady=10)
        self.left_panel.pack_propagate(False)
        
        self.right_panel = ctk.CTkScrollableFrame(self)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)
        
        # --- Left Panel Controls ---
        ctk.CTkLabel(self.left_panel, text="Camera Tester", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 20))
        
        ctk.CTkLabel(self.left_panel, text="Camera Index:").pack(anchor="w", padx=10)
        self.cam_idx_combo = ctk.CTkComboBox(self.left_panel, values=[str(i) for i in range(10)])
        self.cam_idx_combo.set("0")
        self.cam_idx_combo.pack(fill="x", padx=10, pady=(0, 15))
        
        ctk.CTkLabel(self.left_panel, text="Backend:").pack(anchor="w", padx=10)
        self.backend_combo = ctk.CTkComboBox(self.left_panel, values=["MSMF", "DSHOW", "ANY"])
        self.backend_combo.set("MSMF")
        self.backend_combo.pack(fill="x", padx=10, pady=(0, 15))
        
        self.btn_scan = ctk.CTkButton(self.left_panel, text="Run Full Scan", command=self.start_scan, fg_color="#2b5c8f", hover_color="#1d3f63")
        self.btn_scan.pack(fill="x", padx=10, pady=20)
        
        self.status_lbl = ctk.CTkLabel(self.left_panel, text="Ready", text_color="gray")
        self.status_lbl.pack(pady=10)
        
        self.progress_bar = ctk.CTkProgressBar(self.left_panel)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=10, pady=10)
        
    def start_scan(self):
        if self.is_scanning:
            return
            
        # Ensure no cameras are actively being used by the app
        self.app.recorder.stop_workers()
        self.app.cam_mgr.close_all()
        
        # Clear previous results
        for widget in self.right_panel.winfo_children():
            widget.destroy()
            
        self.is_scanning = True
        self.btn_scan.configure(state="disabled", text="Scanning...")
        self.progress_bar.set(0)
        
        idx = int(self.cam_idx_combo.get())
        backend_name = self.backend_combo.get()
        
        threading.Thread(target=self.scan_worker, args=(idx, backend_name), daemon=True).start()
        
    def scan_worker(self, idx, backend_name):
        backend = cv2.CAP_MSMF
        if backend_name == "DSHOW":
            backend = cv2.CAP_DSHOW
        elif backend_name == "ANY":
            backend = cv2.CAP_ANY
            
        total_tests = len(self.test_fourcc) * len(self.test_resolutions) * len(self.test_fps)
        current_test = 0
        
        for fourcc_str in self.test_fourcc:
            # Create a section header for the codec
            self.app.after(0, self.add_section_header, f"Format: {fourcc_str}")
            
            for w, h in self.test_resolutions:
                for target_fps in self.test_fps:
                    
                    self.app.after(0, lambda t=f"Testing {w}x{h} @ {target_fps}fps ({fourcc_str})": self.status_lbl.configure(text=t))
                    
                    # Test this specific combination
                    result = self.test_format(idx, backend, fourcc_str, w, h, target_fps)
                    
                    # Add result card to UI
                    self.app.after(0, self.add_result_card, fourcc_str, w, h, target_fps, result)
                    
                    current_test += 1
                    self.app.after(0, self.progress_bar.set, current_test / total_tests)
                    
        self.app.after(0, self.scan_finished)
        
    def test_format(self, idx, backend, fourcc_str, w, h, fps):
        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            return {"status": "failed", "reason": "Failed to open camera"}
            
        # Try to enforce exact format
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc_str))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        cap.set(cv2.CAP_PROP_FPS, fps)
        
        # Grab a frame to let backend negotiate
        ret, _ = cap.read()
        
        if not ret:
            cap.release()
            return {"status": "failed", "reason": "Could not grab frame"}
            
        actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        
        cap.release()
        
        # Evaluate result
        if actual_w == w and actual_h == h:
            if abs(actual_fps - fps) <= 1.5:
                return {"status": "success", "actual_w": actual_w, "actual_h": actual_h, "actual_fps": actual_fps}
            else:
                return {"status": "warning", "reason": "FPS Mismatch", "actual_w": actual_w, "actual_h": actual_h, "actual_fps": actual_fps}
        else:
            return {"status": "error", "reason": "Resolution Mismatch", "actual_w": actual_w, "actual_h": actual_h, "actual_fps": actual_fps}

    def add_section_header(self, title):
        lbl = ctk.CTkLabel(self.right_panel, text=title, font=ctk.CTkFont(size=18, weight="bold"), anchor="w")
        lbl.pack(fill="x", pady=(20, 5))
        
    def add_result_card(self, fourcc, target_w, target_h, target_fps, result):
        card = ctk.CTkFrame(self.right_panel, fg_color="#2b2b2b")
        card.pack(fill="x", pady=2, padx=5)
        
        # Base info string
        req_str = f"Requested: {target_w}x{target_h} @ {target_fps}fps"
        
        if result["status"] == "success":
            color = "#28a745" # Green
            icon = "✔️"
            detail_str = f"Perfect Match: {int(result['actual_w'])}x{int(result['actual_h'])} @ {result['actual_fps']:.1f}fps"
        elif result["status"] == "warning":
            color = "#ffc107" # Yellow
            icon = "⚠️"
            detail_str = f"FPS Mismatch (Driver Fallback): {int(result['actual_w'])}x{int(result['actual_h'])} @ {result['actual_fps']:.1f}fps"
        elif result["status"] == "error":
            color = "#dc3545" # Red
            icon = "❌"
            detail_str = f"Resolution Rejected (Fallback): {int(result['actual_w'])}x{int(result['actual_h'])} @ {result['actual_fps']:.1f}fps"
        else:
            color = "#6c757d" # Gray
            icon = "🚫"
            detail_str = f"Failed: {result.get('reason', 'Unknown error')}"
            
        # UI Elements for the card
        status_indicator = ctk.CTkLabel(card, text=icon, text_color=color, font=ctk.CTkFont(size=20), width=40)
        status_indicator.pack(side="left", padx=10, pady=5)
        
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=5)
        
        ctk.CTkLabel(info_frame, text=req_str, font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(info_frame, text=detail_str, text_color=color, anchor="w").pack(fill="x")
        
    def scan_finished(self):
        self.is_scanning = False
        self.btn_scan.configure(state="normal", text="Run Full Scan")
        self.status_lbl.configure(text="Scan Complete", text_color="#28a745")
