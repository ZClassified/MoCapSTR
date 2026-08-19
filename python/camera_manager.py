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
            
        # --- HARDWARE SYNC ---
        # We MUST set properties BEFORE PyAV opens the stream!
        # Due to OpenCV backend bugs on Windows:
        # 1. DSHOW correctly sets Exposure, but fails to set AutoFocus.
        # 2. MSMF correctly sets AutoFocus, but fails to set Exposure.
        # CRITICAL: MSMF and DSHOW enumerate identical cameras in different orders!
        # If we alternate MSMF and DSHOW in a single loop, MSMF(1) might open the same
        # physical camera as DSHOW(0) and RESET its exposure.
        # Fix: Apply ALL MSMF settings first, THEN apply ALL DSHOW settings.
        if camera_type == "USB Webcams" and exposure_val is not None and gain_val is not None and trigger_on is not None:
            import cv2
            
            # Pass 1: Set Trigger via MSMF for all cameras
            # CRITICAL BUGFIX: We do NOT use 'valid_indices' (which is DSHOW based) here.
            # MSMF enumerates virtual cameras differently, meaning MSMF index 'i' might 
            # not match DSHOW index 'i'. We aggressively apply the trigger setting to 
            # the first 10 MSMF cameras to guarantee all physical cameras receive it.
            print("Applying UVC Trigger via MSMF to all available cameras...")
            for ms_idx in range(10):
                try:
                    cap = cv2.VideoCapture(ms_idx, cv2.CAP_MSMF)
                    if cap.isOpened():
                        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1 if trigger_on else 0)
                        cap.set(cv2.CAP_PROP_FOCUS, 0)
                        cap.release()
                except Exception:
                    pass

            # Fix 2: Give cameras time to switch into external trigger mode before
            # PyAV tries to open the streams. Without this pause the DSHOW pass
            # or PyAV may catch a camera mid-transition and misread its state.
            if trigger_on:
                print("Waiting 1.5s for cameras to securely enter trigger mode...")
                time.sleep(1.5)

            # Pass 2: Set Exposure/Gain via DSHOW for all cameras
            for i, cam_name in valid_indices:
                try:
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25) # 0.25 is manual in DirectShow (0.75 is auto)
                        cap.set(cv2.CAP_PROP_EXPOSURE, exposure_val)
                        cap.set(cv2.CAP_PROP_GAIN, gain_val)
                        cap.release()
                except Exception as e:
                    print(f"DSHOW hardware sync failed for {cam_name} (index {i}): {e}")
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
                    
                # Verify the stream is accessible.
                stream = container.streams.video[0]
                packet_found = False

                if trigger_on:
                    # Fix 1: In hardware-trigger mode a camera will NOT emit any
                    # frames until it receives a trigger pulse. Waiting for a packet
                    # here would block indefinitely and cause the camera to be
                    # discarded even though it is healthy. If av.open() succeeded
                    # and the video stream exists, the camera is present and open.
                    packet_found = True
                    print(f"Trigger mode: skipping packet verification for index {i} ({cam_name})")
                else:
                    # Fix 3: Limit probing to avoid hanging on a misbehaving
                    # free-run camera. 50 empty packets is a reliable upper bound.
                    max_probe_packets = 50
                    probe_count = 0
                    for packet in container.demux(stream):
                        probe_count += 1
                        if packet.size > 0:
                            packet_found = True
                            break
                        if probe_count >= max_probe_packets:
                            print(f"Free-run probe limit reached for index {i} ({cam_name}) — skipping.")
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
            
    def reset_uvc_drivers(self, max_index=10):
        """
        Simulates the behavior of OBS or other software that accesses the DirectShow 
        and Media Foundation graphs. This forces the Windows UVC driver to renegotiate 
        the endpoints and resets the internal state of the driver, potentially recovering 
        cameras that have stopped responding or were lost due to bus issues.
        """
        import cv2
        print("Resetting UVC drivers by cycling DSHOW and MSMF backends...")
        for i in range(max_index):
            try:
                # Cycle DSHOW
                cap_dshow = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap_dshow.isOpened():
                    cap_dshow.release()
                
                # Cycle MSMF
                cap_msmf = cv2.VideoCapture(i, cv2.CAP_MSMF)
                if cap_msmf.isOpened():
                    cap_msmf.set(cv2.CAP_PROP_AUTOFOCUS, 0)  # Ensure it leaves trigger mode
                    cap_msmf.release()
            except Exception as e:
                print(f"Error resetting UVC driver for index {i}: {e}")
        print("UVC driver reset complete.")
            
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
