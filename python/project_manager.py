import os
from datetime import datetime

class ProjectManager:
    def __init__(self, base_path=""):
        self.base_path = base_path
        if not self.base_path:
            # Default to user's video folder or current directory
            self.base_path = os.path.join(os.path.expanduser("~"), "Videos", "MoCap_Projects")
            
        self.current_project = None
        self.ensure_dir(self.base_path)
        
    def set_base_path(self, path):
        self.base_path = path
        self.ensure_dir(self.base_path)
        
    def ensure_dir(self, path):
        if not os.path.exists(path):
            os.makedirs(path)
            
    def set_project(self, project_name):
        self.current_project = project_name
        proj_dir = os.path.join(self.base_path, self.current_project)
        self.ensure_dir(proj_dir)
        return proj_dir
        
    def get_recording_folder(self, is_calibration=False):
        """
        Creates and returns the exact folder structure for FreeMoCap.
        FreeMoCap expects data in a folder containing 'synchronized_videos/'
        """
        if not self.current_project:
            return None
            
        proj_dir = os.path.join(self.base_path, self.current_project)
        
        if is_calibration:
            target_dir = os.path.join(proj_dir, "calibration")
        else:
            # Create a new take folder based on timestamp to avoid overwriting
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            target_dir = os.path.join(proj_dir, "takes", f"take_{timestamp}")
            
        # FreeMoCap / SkellyCam standard subfolder
        sync_dir = os.path.join(target_dir, "synchronized_videos")
        self.ensure_dir(sync_dir)
        
        return sync_dir
