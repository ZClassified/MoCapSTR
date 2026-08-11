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
        self.test_resolutions = [(1920, 1080), (1600, 1200), (1280, 1024), (1280, 720), (1024, 768), (800, 600), (640, 480)]
        self.test_fps = [60, 50, 30, 25, 15]
        self.test_fourcc = ["MJPG"]
        
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
        self.cam_idx_combo = ctk.CTkComboBox(self.left_panel, values=["All"] + [str(i) for i in range(10)])
        self.cam_idx_combo.set("All")
        self.cam_idx_combo.pack(fill="x", padx=10, pady=(0, 15))
        
        ctk.CTkLabel(self.left_panel, text="Format to Test:").pack(anchor="w", padx=10)
        self.format_test_combo = ctk.CTkComboBox(self.left_panel, values=["MJPG Only"])
        self.format_test_combo.set("MJPG Only")
        self.format_test_combo.pack(fill="x", padx=10, pady=(0, 15))

        ctk.CTkLabel(self.left_panel, text="Custom Res (WxH):").pack(anchor="w", padx=10)
        self.custom_res_entry = ctk.CTkEntry(self.left_panel, placeholder_text="e.g. 1280x1024")
        self.custom_res_entry.pack(fill="x", padx=10, pady=(0, 15))
        
        self.btn_scan_custom = ctk.CTkButton(self.left_panel, text="Scan Custom Res Only", command=lambda: self.start_scan(custom_only=True), fg_color="#457b9d", hover_color="#1d3557")
        self.btn_scan_custom.pack(fill="x", padx=10, pady=(0, 5))

        self.btn_scan = ctk.CTkButton(self.left_panel, text="Run Full Scan", command=self.start_scan, fg_color="#2b5c8f", hover_color="#1d3f63")
        self.btn_scan.pack(fill="x", padx=10, pady=(0, 20))
        
        self.status_lbl = ctk.CTkLabel(self.left_panel, text="Ready", text_color="gray")
        self.status_lbl.pack(pady=10)
        
        self.progress_bar = ctk.CTkProgressBar(self.left_panel)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=10, pady=10)
        
        self.summary_box = ctk.CTkTextbox(self.left_panel)
        # We will pack this dynamically when the scan finishes
        
    def start_scan(self, custom_only=False):
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
        self.btn_scan_custom.configure(state="disabled")
        self.progress_bar.set(0)
        
        idx_val = self.cam_idx_combo.get()
        custom_res_str = self.custom_res_entry.get().strip()
        
        self.all_successful_formats = {}
        self.summary_box.pack_forget()
        
        import threading
        threading.Thread(target=self.scan_worker, args=(idx_val, custom_res_str, custom_only), daemon=True).start()
        
    def scan_worker(self, idx_val, custom_res_str, custom_only):
        backend = "MSMF" # Dummy, ignored
        
        if idx_val == "All":
            self.app.after(0, lambda: self.status_lbl.configure(text="Discovering cameras..."))
            cams_to_test = self.app.cam_mgr.find_and_open_cameras(10, camera_type="USB Webcams")
            self.app.cam_mgr.close_all()
            if not cams_to_test:
                self.app.after(0, lambda: self.status_lbl.configure(text="No cameras found"))
                self.app.after(0, self.scan_finished)
                return
        else:
            cams_to_test = [int(idx_val)]
            
        # Build resolution list
        resolutions_to_test = list(self.test_resolutions)
        if custom_res_str:
            try:
                w, h = map(int, custom_res_str.lower().split('x'))
                if custom_only:
                    resolutions_to_test = [(w, h)]
                else:
                    if (w, h) not in resolutions_to_test:
                        resolutions_to_test.insert(0, (w, h))
            except ValueError:
                self.app.after(0, lambda: self.status_lbl.configure(text="Invalid custom res"))
                if custom_only:
                    self.app.after(0, self.scan_finished)
                    return
        elif custom_only:
            self.app.after(0, lambda: self.status_lbl.configure(text="No custom res entered"))
            self.app.after(0, self.scan_finished)
            return
            
        formats_to_test = ["MJPG"]
                
        total_tests = len(cams_to_test) * len(formats_to_test) * len(resolutions_to_test) * len(self.test_fps)
        current_test = 0
        
        self.all_successful_formats = {cam_idx: {fmt: [] for fmt in formats_to_test} for cam_idx in cams_to_test}
        
        for cam_idx in cams_to_test:
            self.app.after(0, self.add_section_header, f"--- Camera {cam_idx} ---")
            
            for fourcc_str in formats_to_test:
                # Create a section header for the codec
                self.app.after(0, self.add_section_header, f"Format: {fourcc_str}")
                
                for w, h in resolutions_to_test:
                    res_failed = False
                    for target_fps in self.test_fps:
                        if res_failed:
                            current_test += 1
                            self.app.after(0, self.progress_bar.set, current_test / total_tests)
                            continue
                            
                        self.app.after(0, lambda t=f"Cam {cam_idx}: Testing {w}x{h} @ {target_fps}fps ({fourcc_str})": self.status_lbl.configure(text=t))
                        
                        # Test this specific combination
                        result = self.test_format(cam_idx, backend, fourcc_str, w, h, target_fps)
                        
                        # Add result card to UI
                        self.app.after(0, self.add_result_card, fourcc_str, w, h, target_fps, result, cam_idx)
                        
                        if result["status"] == "success":
                            self.all_successful_formats[cam_idx][fourcc_str].append(f"{w}x{h} @ {target_fps}fps")
                        elif result["status"] in ["error", "failed"]:
                            # Resolution not supported, skip other FPS for this resolution
                            res_failed = True
                        
                        current_test += 1
                        self.app.after(0, self.progress_bar.set, current_test / total_tests)
                        
        self.app.after(0, self.scan_finished)
        
    def test_format(self, idx, backend, fourcc_str, w, h, fps):
        import av
        device_names = self.app.cam_mgr._get_device_names()
        if idx >= len(device_names):
            return {"status": "failed", "reason": "Camera not found"}
            
        cam_name = device_names[idx]
        vcodec = 'mjpeg' if fourcc_str == "MJPG" else 'rawvideo'
        
        options = {
            'video_size': f'{w}x{h}',
            'framerate': str(fps),
            'vcodec': vcodec
        }
        if fourcc_str == "YUY2":
            options['pixel_format'] = 'yuyv422'
            
        try:
            container = av.open(f'video={cam_name}', format='dshow', options=options)
            stream = container.streams.video[0]
            
            # verify we can demux a packet
            packet_found = False
            for packet in container.demux(stream):
                if packet.size > 0:
                    packet_found = True
                    break
                    
            if not packet_found:
                container.close()
                return {"status": "failed", "reason": "No packets received"}
                
            actual_w = stream.codec_context.width
            actual_h = stream.codec_context.height
            actual_fps = float(stream.average_rate) if stream.average_rate else fps
            container.close()
            
            if actual_w == w and actual_h == h:
                if abs(actual_fps - fps) <= 1.5:
                    return {"status": "success", "actual_w": actual_w, "actual_h": actual_h, "actual_fps": actual_fps}
                else:
                    return {"status": "warning", "reason": "FPS Mismatch", "actual_w": actual_w, "actual_h": actual_h, "actual_fps": actual_fps}
            else:
                return {"status": "error", "reason": "Resolution Mismatch", "actual_w": actual_w, "actual_h": actual_h, "actual_fps": actual_fps}
                
        except Exception as e:
            return {"status": "failed", "reason": "Rejected by driver"}

    def add_section_header(self, title):
        lbl = ctk.CTkLabel(self.right_panel, text=title, font=ctk.CTkFont(size=18, weight="bold"), anchor="w")
        lbl.pack(fill="x", pady=(20, 5))
        
    def add_result_card(self, fourcc, target_w, target_h, target_fps, result, cam_idx):
        card = ctk.CTkFrame(self.right_panel, fg_color="#2b2b2b")
        card.pack(fill="x", pady=2, padx=5)
        
        # Base info string
        req_str = f"[Cam {cam_idx}] Requested: {target_w}x{target_h} @ {target_fps}fps"
        
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
        
        # Auto-scroll to bottom
        self.right_panel.update_idletasks()
        self.right_panel._parent_canvas.yview_moveto(1.0)
        
    def scan_finished(self):
        self.is_scanning = False
        self.btn_scan.configure(state="normal", text="Run Full Scan")
        self.btn_scan_custom.configure(state="normal")
        self.status_lbl.configure(text="Scan Complete", text_color="#28a745")
        
        # Build summary report
        report = "--- SUMMARY ---\n"
        if not hasattr(self, "all_successful_formats") or not self.all_successful_formats:
            report += "No cameras scanned or found.\n"
        else:
            for cam_idx, formats in self.all_successful_formats.items():
                report += f"\n--- CAMERA {cam_idx} ---\n"
                for fmt, configs in formats.items():
                    report += f"[{fmt}]\n"
                    if configs:
                        for c in configs:
                            report += f"✔️ {c}\n"
                    else:
                        report += "None fully supported.\n"
                        
            # Common formats across all cameras
            if len(self.all_successful_formats) > 1:
                report += "\n\n=== COMMON (SUPPORTED BY ALL CAMERAS) ===\n"
                first_cam = list(self.all_successful_formats.keys())[0]
                formats_tested = list(self.all_successful_formats[first_cam].keys())
                for fmt in formats_tested:
                    common_set = set(self.all_successful_formats[first_cam][fmt])
                    for cam_idx in list(self.all_successful_formats.keys())[1:]:
                        common_set = common_set.intersection(set(self.all_successful_formats[cam_idx][fmt]))
                        
                    common_list = [f for f in self.all_successful_formats[first_cam][fmt] if f in common_set]
                    
                    report += f"\n[{fmt}]\n"
                    if common_list:
                        for c in common_list:
                            report += f"🌟 {c}\n"
                    else:
                        report += "No common settings found.\n"
                
        self.summary_box.pack(fill="both", expand=True, padx=10, pady=10)
        self.summary_box.delete("0.0", "end")
        self.summary_box.insert("0.0", report)
