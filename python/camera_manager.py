import cv2

class CameraManager:
    def __init__(self):
        self.cameras = {} # Dictionary mapping index to cv2.VideoCapture object
        
    def find_cameras(self, max_index=10):
        """Scans for available cameras using DirectShow on Windows."""
        print("Scanning for cameras...")
        available_cams = []
        for i in range(max_index):
            # CAP_DSHOW is often required on Windows to set exposure properly
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    available_cams.append(i)
                cap.release()
        print(f"Found cameras at indices: {available_cams}")
        return available_cams
        
    def open_camera(self, index):
        if index not in self.cameras:
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                self.cameras[index] = cap
                return True
        return False
        
    def close_camera(self, index):
        if index in self.cameras:
            self.cameras[index].release()
            del self.cameras[index]
            
    def close_all(self):
        for index in list(self.cameras.keys()):
            self.close_camera(index)
            
    def apply_settings(self, index, width=1280, height=800, fps=60, exposure_value=None):
        """
        Applies settings to a specific camera.
        Note: The scale and meaning of exposure_value depends heavily on the camera driver (UVC).
        Usually in OpenCV with DSHOW, exposure is a negative value like -4 to -8, meaning 2^val seconds.
        For hardware trigger mode, some cameras require specific vendor extension commands (not standard OpenCV).
        """
        if index in self.cameras:
            cap = self.cameras[index]
            
            # Disable auto exposure first if we want to set it manually
            # cv2.CAP_PROP_AUTO_EXPOSURE: 0.25 (manual), 0.75 (auto) usually for UVC
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            
            if exposure_value is not None:
                cap.set(cv2.CAP_PROP_EXPOSURE, exposure_value)
                
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)
            
            return {
                "width": cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                "height": cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "exposure": cap.get(cv2.CAP_PROP_EXPOSURE)
            }
        return None
        
    def get_frame(self, index):
        if index in self.cameras:
            ret, frame = self.cameras[index].read()
            if ret:
                return frame
        return None

if __name__ == "__main__":
    # Test script
    cam_mgr = CameraManager()
    cams = cam_mgr.find_cameras(5)
    if cams:
        idx = cams[0]
        cam_mgr.open_camera(idx)
        print("Settings applied:", cam_mgr.apply_settings(idx, 1280, 800, 60))
        frame = cam_mgr.get_frame(idx)
        if frame is not None:
            print("Successfully captured a frame of shape:", frame.shape)
        cam_mgr.close_all()
