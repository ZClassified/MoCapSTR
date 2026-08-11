# Active Context

**Current Status:** Implemented Arduino Software-Integration in GUI (Auto-Trigger, FPS Matching, Presets).
**Last Modified:** 2026-08-11 11:26:00

---

## Instructions for LLM Assistants
Welcome to the MoCapST project. This file (`ACTIVE_CONTEXT.md`) serves as the central memory for this repository. 

**Whenever you make significant changes to this project, you MUST update this file:**
1. Update the **Last Modified** timestamp to the current time.
2. Update the **Current Status** with a brief summary of what you just completed.
3. Append a short bullet point to the **Recent Changes** list below.

This ensures that the next AI assistant immediately knows what was just done and where the project currently stands.

## Recent Changes
- **2026-08-10:** Added top control bar in Live Preview tab including Recording Timer, Frame Counter, Disk Space Warning, and live Dropped Frame detection.
- **2026-08-10:** Implemented `PresetManager` to save/load all UI settings to `presets.json`. Overhauled the Setup Tab UI using `CTkFrame` cards for better grouping.
- **2026-08-10:** Added FreeMoCap specific Charuco Board parameters (Dictionary, Grid, Sizes) and a live `cv2.aruco` detection overlay in the Live Preview tab.
- **2026-08-10:** Implemented Phase 1 of Blackmagic SDI Integration. Added "Camera Type" dropdown to UI to switch between USB and Blackmagic SDI. Modified CameraManager to apply resolution and framerate to DeckLink WDM filters before the first frame read to ensure successful initialization.
- **2026-08-11 (v1.0.4):** Created `CameraTestTab` (Tab 4) to brute-force test camera capabilities. Added Format selector (MJPG / YUY2) to the Setup Tab and `CameraManager`, allowing users to explicitly choose uncompressed streams or compressed high-FPS streams. Added info button explaining the USB bandwidth differences.
- **2026-08-11:** Enhanced `CameraTestTab` by removing DSHOW (to fix false positive format reporting), adding a custom resolution text input for arbitrary format testing, adding `1280x1024` and `1600x1200` to default tests, and generating a clean summary text report of fully successful formats at the end of the scan.
- **2026-08-11 (v1.0.5):** Improved `CameraTestTab` by adding a "Scan All" option that reports identical available combinations across all connected cameras. Made the test smarter by short-circuiting and skipping unsupported resolutions. Added format selector and a "Scan Custom Res Only" button to test specific cases quickly.
- **2026-08-11 (v1.1.0):** Major architectural refactor. Replaced `cv2.VideoCapture` with `PyAV` (FFmpeg) in `camera_manager.py` and `recorder.py`. Implemented Zero-Copy stream muxing (direct MJPEG to disk without CPU decoding) to eliminate RAM/CPU bottlenecks for 4+ camera setups. Separated UI preview decoding (limited to 15fps) from raw packet recording. Pre-configured native `decklink` PyAV format for Blackmagic SDI.
- **2026-08-11:** UI Cleanup post-PyAV. Removed obsolete Backend selection, YUY2 format option, and White Balance slider. Re-wired Exposure and Gain to a dedicated "Sync Hardware Exposure" button that temporarily closes PyAV, opens OpenCV DSHOW to set hardware registers, and reopens PyAV. Optimized UI for MJPEG / SDI workflows.
- **2026-08-11 (v1.0.6):** Fixed PyAV frame drops by offloading Charuco and rotation logic to a separate `PreviewWorker` thread, freeing up the `demux` thread. Increased DirectShow `rtbufsize` to 256M to prevent OS-level buffering drops. Fixed MKV 1000fps timestamp bug by correctly overriding `packet.time_base = 1/fps` before muxing.
- **2026-08-11 (v1.0.7):** Implemented Arduino Software-Integration (Python GUI). Added "Auto-Trigger on Record" logic, automatic FPS matching when applying camera settings, a COM-Port refresh button, and integrated the Arduino port & trigger settings into the `PresetManager`.
- **2026-08-11 (v1.0.8):** Added FreeMoCap `session_info.json` metadata generation on record start. Implemented Camera Rotation Persistence (saves Portrait mode rotations to `presets.json`). Added a Watchdog `<PING>` to Arduino firmware and Python UI to instantly detect and warn on USB connection loss.
