import os
import sys
import glob
import shutil
import subprocess
import argparse
from datetime import datetime

class FreeMoCapBridge:
    """
    Bridge utility connecting MoCapSTR recordings directly with FreeMoCap.
    
    Provides:
    - Auto-discovery of the default FreeMoCap data directory (~/freemocap_data).
    - Creation of standardized FreeMoCap recording sessions.
    - Video transfer using NTFS hardlinks (zero disk copy) or fallback copy.
    - Updating FreeMoCap's active session tracker (most_recent_recording.toml).
    - Launching FreeMoCap GUI / CLI automatically.
    """
    
    def __init__(self, base_freemocap_dir=None):
        if base_freemocap_dir:
            self.base_dir = os.path.abspath(base_freemocap_dir)
        else:
            self.base_dir = os.path.join(os.path.expanduser("~"), "freemocap_data")
            
        self.sessions_dir = os.path.join(self.base_dir, "recording_sessions")
        self.settings_dir = os.path.join(self.base_dir, "logs_info_and_settings")
        self.recent_recording_toml = os.path.join(self.settings_dir, "most_recent_recording.toml")
        
    def ensure_directories(self):
        """Ensures the basic FreeMoCap folder hierarchy exists."""
        os.makedirs(self.sessions_dir, exist_ok=True)
        os.makedirs(self.settings_dir, exist_ok=True)

    def is_freemocap_installed(self):
        """Checks if FreeMoCap is available in the current PATH or Python environment."""
        # Check CLI command in PATH
        if shutil.which("freemocap") is not None:
            return True
            
        # Check if importable via Python
        try:
            res = subprocess.run(
                [sys.executable, "-c", "import freemocap; print(freemocap.__file__)"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return res.returncode == 0
        except Exception:
            return False

    def update_most_recent_recording(self, session_path):
        """
        Updates most_recent_recording.toml inside freemocap_data/logs_info_and_settings/
        so FreeMoCap automatically selects this recording upon startup.
        """
        self.ensure_directories()
        norm_path = os.path.abspath(session_path).replace("\\", "/")
        
        # FreeMoCap standard TOML format for most_recent_recording
        toml_content = f'most_recent_recording = "{norm_path}"\n'
        
        try:
            with open(self.recent_recording_toml, "w", encoding="utf-8") as f:
                f.write(toml_content)
            return True
        except Exception as e:
            print(f"[FreeMoCapBridge] Error writing most_recent_recording.toml: {e}")
            return False

    def export_take_to_freemocap(self, take_dir, session_name=None, prefer_mp4=True, use_hardlinks=True):
        """
        Transfers a MoCapSTR take into a standardized FreeMoCap session folder.
        
        Args:
            take_dir (str): Path to the take folder or take's synchronized_videos directory.
            session_name (str, optional): Custom name for the session.
            prefer_mp4 (bool): If True, looks for .mp4 files first.
            use_hardlinks (bool): If True, creates instant hardlinks instead of copying files.
            
        Returns:
            str: Path to the newly created FreeMoCap session, or None on failure.
        """
        self.ensure_directories()
        take_dir = os.path.abspath(take_dir)
        
        # Locate video files
        if os.path.basename(take_dir) == "synchronized_videos":
            search_dir = take_dir
            parent_take_name = os.path.basename(os.path.dirname(take_dir))
        else:
            sync_sub = os.path.join(take_dir, "synchronized_videos")
            search_dir = sync_sub if os.path.exists(sync_sub) else take_dir
            parent_take_name = os.path.basename(take_dir)

        if prefer_mp4:
            video_files = glob.glob(os.path.join(search_dir, "*.mp4"))
            if not video_files:
                video_files = glob.glob(os.path.join(search_dir, "*.avi"))
        else:
            video_files = glob.glob(os.path.join(search_dir, "*.avi"))
            if not video_files:
                video_files = glob.glob(os.path.join(search_dir, "*.mp4"))

        if not video_files:
            print(f"[FreeMoCapBridge] No video files (.mp4 / .avi) found in {search_dir}")
            return None

        # Build session name
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if not session_name:
            session_name = f"session_{timestamp}_{parent_take_name}"
        elif not session_name.startswith("session_"):
            session_name = f"session_{session_name}"

        target_session_dir = os.path.join(self.sessions_dir, session_name)
        target_sync_dir = os.path.join(target_session_dir, "synchronized_videos")
        os.makedirs(target_sync_dir, exist_ok=True)

        # Transfer video files into synchronized_videos
        for vfile in video_files:
            dest_file = os.path.join(target_sync_dir, os.path.basename(vfile))
            if os.path.exists(dest_file):
                try:
                    os.remove(dest_file)
                except Exception:
                    pass

            transferred = False
            if use_hardlinks:
                try:
                    # Instant zero-copy link on Windows/Linux (same drive)
                    os.link(vfile, dest_file)
                    transferred = True
                except Exception:
                    transferred = False

            if not transferred:
                try:
                    shutil.copy2(vfile, dest_file)
                except Exception as e:
                    print(f"[FreeMoCapBridge] Failed to copy {vfile} to {dest_file}: {e}")

        # Update most_recent_recording.toml
        self.update_most_recent_recording(target_session_dir)

        return target_session_dir

    def launch_freemocap(self, session_path=None):
        """
        Launches FreeMoCap in the background as a detached process.
        
        Args:
            session_path (str, optional): Target session to set as active before launch.
            
        Returns:
            bool: True if process was started, False otherwise.
        """
        if session_path:
            self.update_most_recent_recording(session_path)

        # Check if 'freemocap' command exists in PATH
        if shutil.which("freemocap"):
            cmd = ["freemocap"]
        else:
            # Fallback to python -m freemocap
            cmd = [sys.executable, "-m", "freemocap"]

        try:
            # Launch detached so it does not block MoCapSTR
            if os.name == "nt":
                DETACHED_PROCESS = 0x00000008
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                subprocess.Popen(
                    cmd,
                    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                    close_fds=True
                )
            else:
                subprocess.Popen(
                    cmd,
                    start_new_session=True
                )
            return True
        except Exception as e:
            print(f"[FreeMoCapBridge] Failed to launch FreeMoCap: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="FreeMoCap Bridge CLI for MoCapSTR")
    parser.add_argument("--take", type=str, help="Path to MoCapSTR take folder to export")
    parser.add_argument("--session-name", type=str, default=None, help="Custom name for FreeMoCap session")
    parser.add_argument("--launch", action="store_true", help="Launch FreeMoCap after export")
    parser.add_argument("--freemocap-dir", type=str, default=None, help="Custom freemocap_data base directory")
    
    args = parser.parse_args()
    
    bridge = FreeMoCapBridge(base_freemocap_dir=args.freemocap_dir)
    print(f"FreeMoCap Data Directory: {bridge.base_dir}")
    print(f"FreeMoCap Installed: {bridge.is_freemocap_installed()}")
    
    if args.take:
        print(f"Exporting take: {args.take}...")
        session_path = bridge.export_take_to_freemocap(args.take, session_name=args.session_name)
        if session_path:
            print(f"Successfully created FreeMoCap session at: {session_path}")
            if args.launch:
                print("Launching FreeMoCap...")
                bridge.launch_freemocap(session_path)
        else:
            print("Failed to export take.")
            sys.exit(1)
    elif args.launch:
        print("Launching FreeMoCap...")
        bridge.launch_freemocap()

if __name__ == "__main__":
    main()
