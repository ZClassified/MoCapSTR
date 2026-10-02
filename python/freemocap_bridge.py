"""
Bridge between MoCapSTR recordings and FreeMoCap 2.x.

FreeMoCap 2 layout (verified against v2.0.0-alpha.25):

    <base data folder>/recordings/<recording name>/
        synchronized_videos/cam0.avi|.mkv|.mp4 ...     one video per camera
        synchronized_videos/timestamps/cam0_timestamps.csv ...

- The base data folder defaults to ~/freemocap_data. A folder chosen in
  FreeMoCap's settings is stored in %APPDATA%/freemocap/freemocap-config.json
  (key "baseDataFolder").
- FreeMoCap reads .mp4, .avi and .mkv. Every file in synchronized_videos/ counts
  as a camera, so there must never be two files for the same camera there.
- The Windows installer puts the app in %LOCALAPPDATA%/Programs/freemocap.

By default MoCapSTR records directly into the FreeMoCap recordings folder, so
no export is needed. export_recording() covers recordings stored elsewhere.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

RECORDINGS_SUBDIR = "recordings"
SYNCHRONIZED_VIDEOS_FOLDER = "synchronized_videos"
TIMESTAMPS_FOLDER = "timestamps"
VIDEO_EXTENSIONS = (".mp4", ".avi", ".mkv")
SESSION_INFO_FILENAME = "session_info.json"


def get_freemocap_base_folder():
    """FreeMoCap's base data folder: the user's choice in FreeMoCap settings, else ~/freemocap_data."""
    config_path = os.path.join(os.environ.get("APPDATA", ""), "freemocap", "freemocap-config.json")
    try:
        with open(config_path, encoding="utf-8") as f:
            stored = json.load(f).get("baseDataFolder")
        if isinstance(stored, str) and stored.strip():
            return stored
    except (OSError, ValueError, AttributeError):
        pass
    return os.path.join(os.path.expanduser("~"), "freemocap_data")


def get_freemocap_recordings_folder():
    return os.path.join(get_freemocap_base_folder(), RECORDINGS_SUBDIR)


def is_inside_freemocap_recordings(path):
    """True if `path` is FreeMoCap's recordings folder (or inside it)."""
    folder = os.path.normcase(os.path.abspath(get_freemocap_recordings_folder()))
    target = os.path.normcase(os.path.abspath(path))
    return target == folder or target.startswith(folder + os.sep)


def find_freemocap_executable():
    """Path of the installed FreeMoCap 2 desktop app, or None."""
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "freemocap", "FreeMoCap.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "FreeMoCap", "FreeMoCap.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def launch_freemocap():
    """Starts the FreeMoCap desktop app detached from MoCapSTR. Returns True on success."""
    exe = find_freemocap_executable()
    if not exe:
        return False
    try:
        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            subprocess.Popen([exe], creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                             close_fds=True, cwd=os.path.dirname(exe))
        else:
            subprocess.Popen([exe], start_new_session=True)
        return True
    except OSError as e:
        print(f"[FreeMoCapBridge] Failed to launch FreeMoCap: {e}")
        return False


def select_videos(video_folder):
    """
    One video per camera: if a camera has several files (e.g. cam0.avi and the
    converted cam0.mp4), the .mp4 wins, then .avi, then .mkv.
    """
    by_camera = {}
    for path in sorted(glob.glob(os.path.join(video_folder, "*"))):
        stem, ext = os.path.splitext(os.path.basename(path))
        ext = ext.lower()
        if ext not in VIDEO_EXTENSIONS or not os.path.isfile(path):
            continue
        current = by_camera.get(stem)
        if current is None or VIDEO_EXTENSIONS.index(ext) < VIDEO_EXTENSIONS.index(os.path.splitext(current)[1].lower()):
            by_camera[stem] = path
    return [by_camera[stem] for stem in sorted(by_camera)]


def _link_or_copy(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)  # same drive: instant, no extra disk space
    except OSError:
        shutil.copy2(src, dst)


def export_recording(recording_dir, recordings_folder=None):
    """
    Makes a MoCapSTR recording available in FreeMoCap's recordings folder.

    Args:
        recording_dir:     folder containing synchronized_videos/
        recordings_folder: target (default: FreeMoCap's recordings folder)

    Returns:
        Path of the recording inside FreeMoCap's folder, or None if there were no videos.
    """
    recording_dir = os.path.abspath(recording_dir)
    recordings_folder = os.path.abspath(recordings_folder or get_freemocap_recordings_folder())
    target_dir = os.path.join(recordings_folder, os.path.basename(recording_dir))
    if os.path.normcase(target_dir) == os.path.normcase(recording_dir):
        return recording_dir  # already where FreeMoCap looks

    source_videos = os.path.join(recording_dir, SYNCHRONIZED_VIDEOS_FOLDER)
    videos = select_videos(source_videos)
    if not videos:
        print(f"[FreeMoCapBridge] No videos found in {source_videos}")
        return None

    target_videos = os.path.join(target_dir, SYNCHRONIZED_VIDEOS_FOLDER)
    os.makedirs(target_videos, exist_ok=True)

    # Never mix files of different exports/takes: FreeMoCap treats every video as a camera
    for path in glob.glob(os.path.join(target_videos, "*")):
        if os.path.isfile(path) and os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS:
            os.remove(path)
    for video in videos:
        _link_or_copy(video, os.path.join(target_videos, os.path.basename(video)))

    source_ts = os.path.join(source_videos, TIMESTAMPS_FOLDER)
    if os.path.isdir(source_ts):
        target_ts = os.path.join(target_videos, TIMESTAMPS_FOLDER)
        os.makedirs(target_ts, exist_ok=True)
        for csv_path in glob.glob(os.path.join(source_ts, "*.csv")):
            shutil.copy2(csv_path, os.path.join(target_ts, os.path.basename(csv_path)))

    info = os.path.join(recording_dir, SESSION_INFO_FILENAME)
    if os.path.exists(info):
        shutil.copy2(info, os.path.join(target_dir, SESSION_INFO_FILENAME))
    return target_dir


def main():
    parser = argparse.ArgumentParser(description="FreeMoCap 2 bridge for MoCapSTR")
    parser.add_argument("--recording", type=str, help="MoCapSTR recording folder to export")
    parser.add_argument("--launch", action="store_true", help="Launch FreeMoCap afterwards")
    args = parser.parse_args()

    print(f"FreeMoCap recordings folder: {get_freemocap_recordings_folder()}")
    print(f"FreeMoCap executable:        {find_freemocap_executable() or 'not found'}")
    if args.recording:
        target = export_recording(args.recording)
        if not target:
            sys.exit("Export failed: no videos found.")
        print(f"Recording available in FreeMoCap: {target}")
    if args.launch and not launch_freemocap():
        sys.exit("FreeMoCap executable not found.")


if __name__ == "__main__":
    main()
