import json
import os
import re
from datetime import datetime

from freemocap_bridge import (SESSION_INFO_FILENAME, SYNCHRONIZED_VIDEOS_FOLDER,
                              get_freemocap_recordings_folder)


def safe_name(text, fallback):
    """Folder-name safe version of user input (Windows forbids <>:"/\\|?*)."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", (text or "").strip()).strip(" ._")
    return cleaned or fallback


class ProjectManager:
    """
    Recording folder layout (FreeMoCap 2 compatible, one folder per recording):

        <base_path>/<YYYY-MM-DD_HH-MM-SS>_<project>_<take>/
            synchronized_videos/camX.avi
            synchronized_videos/timestamps/camX_timestamps.csv
            session_info.json          (project, take, recording type, fps, ...)

    Calibration recordings use "calibration" as take name. Every recording gets
    its own folder, so a new calibration never overwrites or mixes with an old one.
    By default base_path is FreeMoCap's recordings folder: recordings show up in
    FreeMoCap without any export step.
    """
    def __init__(self, base_path=""):
        self.base_path = base_path or get_freemocap_recordings_folder()
        self.current_project = None
        self.ensure_dir(self.base_path)

    def set_base_path(self, path):
        self.base_path = path
        self.ensure_dir(self.base_path)

    def ensure_dir(self, path):
        os.makedirs(path, exist_ok=True)

    def set_project(self, project_name):
        self.current_project = project_name

    def get_recording_folder(self, is_calibration=False, take_name=""):
        """
        Creates a new recording folder and returns its synchronized_videos/ path.
        """
        if not self.current_project:
            return None

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        take = "calibration" if is_calibration else safe_name(take_name, "take")
        base_name = f"{timestamp}_{safe_name(self.current_project, 'project')}_{take}"

        recording_dir = os.path.join(self.base_path, base_name)
        suffix = 2
        while os.path.exists(recording_dir):  # two takes within the same second
            recording_dir = os.path.join(self.base_path, f"{base_name}_{suffix}")
            suffix += 1

        sync_dir = os.path.join(recording_dir, SYNCHRONIZED_VIDEOS_FOLDER)
        self.ensure_dir(sync_dir)
        return sync_dir

    def find_recordings(self, project_name=None):
        """
        Recording folders (containing synchronized_videos/) of a project, oldest first.
        Also finds recordings of MoCapSTR <= 1.5.0 (<base>/<project>/calibration
        and <base>/<project>/takes/*).
        """
        project_name = project_name or self.current_project
        found = []
        if not project_name or not os.path.isdir(self.base_path):
            return found

        for entry in os.scandir(self.base_path):
            if not entry.is_dir():
                continue
            info_path = os.path.join(entry.path, SESSION_INFO_FILENAME)
            if not os.path.isdir(os.path.join(entry.path, SYNCHRONIZED_VIDEOS_FOLDER)) or not os.path.exists(info_path):
                continue
            try:
                with open(info_path, encoding="utf-8") as f:
                    if json.load(f).get("project") == project_name:
                        found.append(entry.path)
            except (OSError, ValueError, AttributeError):
                continue

        legacy_root = os.path.join(self.base_path, project_name)
        legacy = [os.path.join(legacy_root, "calibration")]
        takes_dir = os.path.join(legacy_root, "takes")
        if os.path.isdir(takes_dir):
            legacy += [e.path for e in os.scandir(takes_dir) if e.is_dir()]
        found += [d for d in legacy if os.path.isdir(os.path.join(d, SYNCHRONIZED_VIDEOS_FOLDER))]

        return sorted(found, key=lambda d: os.path.getmtime(d))
