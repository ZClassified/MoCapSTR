import av
import time

class CameraManager:
    def __init__(self):
        self.cameras = {} # Dictionary mapping index to av.container.InputContainer
        self.camera_info = {} # Dictionary mapping index to dict of {backend, camera_type, name, format}
        self.device_names = []
        
    def _get_device_names(self):
        try:
            from pygrabber.dshow_graph import FilterGraph
            graph = FilterGraph()
            return graph.get_input_devices()
        except ImportError:
            return []
            
    def apply_uvc_exposure_and_gain(self, valid_indices, exposure_val, gain_val=0):
        """
        Sets manual exposure and gain via DirectShow while ensuring Free-Run (AutoFocus=0) mode.
        Ensures clean unbinding and COM release before PyAV opens streams.
        """
        if exposure_val is None:
            return
        import cv2
        import gc
        
        print(f"[CameraManager] Applying UVC Settings via DirectShow (Exposure={exposure_val}, Gain={gain_val})...")
        for i, cam_name in valid_indices:
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    # Always ensure Free-Run (0) during open negotiation to prevent DirectShow graph lockup
                    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                    # Set Manual Exposure & Gain
                    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25) # 0.25 is manual in DirectShow (0.75 is auto)
                    cap.set(cv2.CAP_PROP_EXPOSURE, exposure_val)
                    cap.set(cv2.CAP_PROP_GAIN, gain_val)
                    cap.release()
                del cap
            except Exception as e:
                print(f"[CameraManager] DirectShow hardware sync failed for {cam_name} (index {i}): {e}")
        gc.collect()
        
        # Allow DirectShow COM graph to unbind cleanly from physical USB device before PyAV opens
        time.sleep(0.3)

    def find_and_open_cameras(self, max_index=6, backend_name="MSMF", camera_type="USB Webcams", target_w=1280, target_h=720, target_fps=50, target_format="MJPG", exposure_val=None, gain_val=None, trigger_on=None):
        """Scans for available cameras using PyAV (FFmpeg) and keeps them open."""
        self.close_all()
        print(f"Scanning for cameras using PyAV (Type: {camera_type})...")
        
        self.device_names = self._get_device_names()
        available_cams = []
        valid_indices = []
        
        for i in range(max_index):
            if i >= len(self.device_names):
                continue
                
            cam_name = self.device_names[i]
            cam_name_lower = cam_name.lower()
            is_blackmagic = "blackmagic" in cam_name_lower or "decklink" in cam_name_lower
            
            if camera_type == "USB Webcams" and is_blackmagic:
                print(f"Skipping index {i} ({cam_name}) - USB Webcams mode active.")
                continue
            if camera_type == "Blackmagic SDI" and not is_blackmagic:
                print(f"Skipping index {i} ({cam_name}) - Blackmagic SDI mode active.")
                continue
                
            # Skip common virtual cameras that shouldn't receive hardware trigger/exposure commands
            if "virtual" in cam_name_lower or "obs" in cam_name_lower:
                print(f"Skipping virtual camera at index {i} ({cam_name})")
                continue
            
            valid_indices.append((i, cam_name))
            
        # --- HARDWARE SYNC (Exposure & Gain) ---
        # Set Exposure & Gain via DirectShow in Free-Run mode so av.open is guaranteed to succeed instantly.
        if camera_type == "USB Webcams" and exposure_val is not None:
            self.apply_uvc_exposure_and_gain(valid_indices, exposure_val, gain_val if gain_val is not None else 0)
        # ---------------------------

        for i, cam_name in valid_indices:
            try:
                if camera_type == "Blackmagic SDI":
                    # PyAV Decklink format
                    print(f"Setting Blackmagic SDI format to {target_w}x{target_h} @ {target_fps}fps on index {i}")
                    options = {
                        'video_size': f'{target_w}x{target_h}',
                        'framerate': str(target_fps)
                    }
                    container = av.open(cam_name, format='decklink', options=options)
                else:
                    # PyAV DirectShow (dshow) format
                    print(f"Setting USB Webcam format to {target_format} {target_w}x{target_h} @ {target_fps}fps on index {i}")
                    
                    # Map MJPG/YUY2 to FFmpeg codecs
                    vcodec = 'mjpeg' if target_format == "MJPG" else 'rawvideo'
                    if target_format == "YUY2":
                        pixel_format = 'yuyv422'
                    else:
                        pixel_format = 'yuvj422p' # Common for MJPEG
                        
                    # Calculate video_device_number for duplicate names (e.g. multiple "USB Camera"s)
                    device_number = self.device_names[:i].count(cam_name)
                    
                    options = {
                        'video_size': f'{target_w}x{target_h}',
                        'framerate': str(target_fps),
                        'vcodec': vcodec,
                        'rtbufsize': '256M',
                        'video_device_number': str(device_number)
                    }
                    if target_format == "YUY2":
                        options['pixel_format'] = pixel_format
                        
                    container = av.open(f'video={cam_name}', format='dshow', options=options)
                    
                # Verify the stream is accessible (limit probing to 30 packets).
                stream = container.streams.video[0]
                packet_found = False
                max_probe_packets = 30
                probe_count = 0
                for packet in container.demux(stream):
                    probe_count += 1
                    if packet.size > 0:
                        packet_found = True
                        break
                    if probe_count >= max_probe_packets:
                        break

                if packet_found:
                    self.cameras[i] = container
                    self.camera_info[i] = {
                        "name": cam_name,
                        "camera_type": camera_type,
                        "format": target_format,
                        "width": target_w,
                        "height": target_h,
                        "fps": target_fps,
                        "stream": stream,
                        "device_number": device_number
                    }
                    available_cams.append(i)
                else:
                    container.close()
            except Exception as e:
                print(f"Failed to open camera {i} ({cam_name}): {e}")
                
        print(f"Successfully opened cameras at indices: {available_cams}")
        return available_cams
        
    def close_camera(self, index):
        if index in self.cameras:
            try:
                self.cameras[index].close()
            except:
                pass
            del self.cameras[index]
            if index in self.camera_info:
                del self.camera_info[index]
            
    def close_all(self):
        for index in list(self.cameras.keys()):
            self.close_camera(index)

    def set_trigger_mode(self, trigger_on: bool):
        """
        Switches connected physical USB cameras between Hardware Trigger (AutoFocus=1)
        and Free-Run (AutoFocus=0) mode.
        Uses Media Foundation (MSMF) to set UVC property registers directly without colliding
        with the active DirectShow capture graph.
        """
        try:
            import cv2
            import gc
            if not self.device_names:
                self.device_names = self._get_device_names()
            
            mode_str = "Hardware Trigger (1)" if trigger_on else "Free-Run (0)"
            print(f"[CameraManager] Setting UVC trigger mode to {mode_str}...")
            
            num_cams = max(len(self.device_names), len(self.cameras), 1)
            for idx in range(num_cams):
                # Check if this is a known virtual camera by name
                if idx < len(self.device_names):
                    cam_name = self.device_names[idx].lower()
                    if "virtual" in cam_name or "obs" in cam_name:
                        continue
                        
                # 1. First attempt: Media Foundation (accesses UVC controls on active devices)
                success = False
                try:
                    cap = cv2.VideoCapture(idx, cv2.CAP_MSMF)
                    if cap.isOpened():
                        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1 if trigger_on else 0)
                        if trigger_on:
                            cap.set(cv2.CAP_PROP_FOCUS, 0)
                        cap.release()
                        success = True
                    del cap
                except Exception:
                    pass
                    
                # 2. Second attempt: DirectShow fallback if MSMF wasn't opened
                if not success:
                    try:
                        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                        if cap.isOpened():
                            cap.set(cv2.CAP_PROP_AUTOFOCUS, 1 if trigger_on else 0)
                            if trigger_on:
                                cap.set(cv2.CAP_PROP_FOCUS, 0)
                            cap.release()
                        del cap
                    except Exception:
                        pass
            gc.collect()
            time.sleep(0.2)
        except Exception as e:
            print(f"[CameraManager] Error in set_trigger_mode: {e}")

    def reset_hardware_trigger_mode(self):
        """Resets all connected cameras back to free-run mode (AutoFocus=0) so they don't remain locked."""
        self.set_trigger_mode(False)
            

    def apply_settings(self, index, width=1280, height=800, fps=50, format_str="MJPG", exposure_value=None, gain_value=None, wb_value=None):
        """
        Applies settings by reopening the PyAV container with new options.
        Note: Exposure/Gain control is currently limited with PyAV dshow backend.
        """
        if index in self.cameras and index in self.camera_info:
            info = self.camera_info[index]
            
            # Check if we need a full restart
            needs_reopen = (info["width"] != width or 
                            info["height"] != height or 
                            abs(info["fps"] - fps) > 1.0 or 
                            info["format"] != format_str)
            
            if needs_reopen:
                print(f"Format change detected for Cam {index}. Reopening PyAV container...")
                self.close_camera(index)
                
                cam_name = info["name"]
                camera_type = info["camera_type"]
                
                try:
                    if camera_type == "Blackmagic SDI":
                        options = {'video_size': f'{width}x{height}', 'framerate': str(fps)}
                        container = av.open(cam_name, format='decklink', options=options)
                    else:
                        vcodec = 'mjpeg' if format_str == "MJPG" else 'rawvideo'
                        
                        device_number = info.get("device_number", 0)
                        
                        options = {
                            'video_size': f'{width}x{height}',
                            'framerate': str(fps),
                            'vcodec': vcodec,
                            'rtbufsize': '256M',
                            'video_device_number': str(device_number)
                        }
                        if format_str == "YUY2":
                            options['pixel_format'] = 'yuyv422'
                            
                        container = av.open(f'video={cam_name}', format='dshow', options=options)
                        
                    stream = container.streams.video[0]
                    # verify
                    packet_found = False
                    for packet in container.demux(stream):
                        if packet.size > 0:
                            packet_found = True
                            break
                            
                    if packet_found:
                        self.cameras[index] = container
                        self.camera_info[index] = {
                            "name": cam_name,
                            "camera_type": camera_type,
                            "format": format_str,
                            "width": width,
                            "height": height,
                            "fps": fps,
                            "stream": stream
                        }
                    else:
                        container.close()
                        return None
                except Exception as e:
                    print(f"Failed to reopen Cam {index}: {e}")
                    return None
                    
            if exposure_value is not None or gain_value is not None or wb_value is not None:
                print(f"Warning: Exposure/Gain control not supported directly through PyAV dshow. Skipping.")
                
            info = self.camera_info[index]
            return {
                "format": info["format"],
                "width": info["width"],
                "height": info["height"],
                "fps": info["fps"],
                "exposure": None,
                "gain": None,
                "wb": None
            }
        return None
        
    def get_frame(self, index):
        """Used mainly for quick preview. Decodes one frame."""
        if index in self.cameras:
            try:
                container = self.cameras[index]
                stream = self.camera_info[index]["stream"]
                for frame in container.decode(stream):
                    # Convert to numpy bgr24 for UI/OpenCV compatibility
                    return frame.to_ndarray(format='bgr24')
            except Exception as e:
                pass
        return None



if __name__ == "__main__":
    # Test script
    cam_mgr = CameraManager()
    cams = cam_mgr.find_and_open_cameras(2)
    if cams:
        print("Cameras found:", cams)
        idx = cams[0]
        frame = cam_mgr.get_frame(idx)
        if frame is not None:
            print("Successfully captured a frame of shape:", frame.shape)
        cam_mgr.close_all()
