# Active Context

**Current Status:** Bug-fix session. Fixed critical crash in Export Tab (`current_project_dir()` method didn't exist, AVI scan was not recursive). Fixed `TypeError` in conversion progress update (`self.after()` with keyword args). Added cleanup of partially-written `.mp4` on conversion error. Fixed FPS fallback inconsistency (50→30). Added recording guard in Camera Test Tab. Fixed German UI string. Bumped version to 1.2.4.
**Last Modified:** 2026-08-17 17:17:00

---

## Instructions for LLM Assistants
Welcome to the MoCapSTR project. This file (`ACTIVE_CONTEXT.md`) serves as the central memory for this repository. 

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
- **2026-08-11 (v1.0.4):** Created `CameraTestTab` (Tab 4) to brute-force test camera capabilities. Added Format selector (MJPG / YUY2) to the Setup Tab and `CameraManager`.
- **2026-08-11 (v1.0.5):** Improved `CameraTestTab` by adding a "Scan All" option that reports identical available combinations across all connected cameras.
- **2026-08-11 (v1.1.0):** Major architectural refactor. Replaced `cv2.VideoCapture` with `PyAV` (FFmpeg) in `camera_manager.py` and `recorder.py`. Implemented Zero-Copy stream muxing (direct MJPEG to disk without CPU decoding).
- **2026-08-11 (v1.0.6):** Fixed PyAV frame drops by offloading Charuco and rotation logic to a separate `PreviewWorker` thread. Fixed MKV 1000fps timestamp bug.
- **2026-08-11 (v1.0.7):** Implemented Arduino Software-Integration (Python GUI). Added "Auto-Trigger on Record" logic, automatic FPS matching.
- **2026-08-11 (v1.0.8):** Added FreeMoCap `session_info.json` metadata generation. Implemented Camera Rotation Persistence. Added Watchdog `<PING>` to Arduino.
- **2026-08-11 (v1.0.9):** Added hardware remote control functionality. Rewrote Arduino firmware and `arduino_sync.py` to use asynchronous threading for physical push buttons.
- **2026-08-12:** Hardware documentation & Trigger Fix. Added `CAMERA_SPECS.md` detailing the Innomaker OV9281. Updated `setup_tab.py` to correctly activate the external hardware trigger on these cameras by toggling the UVC `FOCUS` parameter.
- **2026-08-12 (v1.1.0):** Complete UI/UX Overhaul. Rewrote the setup process into a dynamic, top-to-bottom studio workflow. Removed `record_tab.py` entirely.
- **2026-08-12:** Added `arduino/test_hardware.py` standalone diagnostic script and `HARDWARE_SETUP.md` professional XLR Splitter Box wiring guide.
- **2026-08-12 (v1.1.1):** Added new "Export & Convert" tab for offline PyAV transcoding of raw MJPEG to H.264.
- **2026-08-13 (v1.1.2):** Improved Arduino intelligent Auto-Trigger logic. Created `arduino/arduino_test_ui.py` standalone UI tool.
- **2026-08-13 (v1.1.3):** Fixed Innomaker UVC Hardware Trigger integration. Switched `sync_hardware_exposure` to use OpenCV's MSMF backend.
- **2026-08-13 (v1.1.4):** Implemented One-Click System Initialization. Consolidated camera opening and hardware sync into a single robust button in the UI.
- **2026-08-13 (v1.1.5):** Resolved DSHOW/MSMF driver lock issues causing UVC settings to fail or flicker. Separated property application into two phases.
- **2026-08-13 (v1.1.6):** Arduino firmware timing fix to eliminate cumulative drift. Added new `<PULSE:N>` serial command. Setup Tab UX improvements.
- **2026-08-13 (v1.1.7):** Resolved the Hardware Trigger Framerate drop mystery (Targeting 60 yielded 30). Proved via empirical sweeping that the Innomaker OV9281 firmware has a fixed ~18-20ms sensor readout time over USB 2.0 in trigger mode, regardless of requested resolution. This caps the physical hardware trigger limit to strictly 50 FPS. Any trigger faster than 50Hz (e.g. 60Hz) strikes the sensor during readout, corrupting the pipeline and halving the framerate. Fixed UI: removed hard exposure slider clamping in favor of a physics-aware warning label. Fixed Backend: changed `CAP_PROP_AUTO_EXPOSURE` flag to `0.25` to correctly disable Auto-Exposure under Windows DirectShow. Default exposure set to -9 (1/512s) to ensure 50 FPS works out-of-the-box.
- **2026-08-17 (v1.1.8):** Fixed initialization hang on phantom COM ports by adding a `<PING>`/`<PONG>` handshake verification to `arduino_sync.py` during connection. Added graceful fallback to free-run mode if the hardware trigger is requested but no Arduino is verified. Fixed a bug in PyAV camera enumeration where multiple cameras with identical names (e.g. "USB Camera") would fail to open due to missing `video_device_number` parameter in FFmpeg dshow options. Fixed OpenCV hardware sync index logic so exposure/gain settings apply to all identical cameras instead of just the first one.
- **2026-08-17 (v1.1.9):** Added custom program window icon support using `design/Icon.ico`. Configured `main.py` with `sys._MEIPASS` pathing to ensure the icon persists when bundled via PyInstaller.
- **2026-08-17 (v1.2.0):** Fixed a bug in `camera_manager.py` where exposure changes only applied to a subset of identical cameras. MSMF hardware trigger initialization was accidentally resetting DSHOW exposure settings due to Windows enumeration differences. Fixed by separating the initialization into a dedicated MSMF pass for all cameras, followed by a DSHOW pass.
- **2026-08-17 (v1.2.1):** Added filter to ignore virtual cameras (like OBS Virtual Camera) in hardware enumeration to prevent MSMF/DSHOW I/O errors. Removed obsolete 'Auto-Trigger on Record' checkbox from the Setup UI as the trigger now runs continuously for PyAV Live Preview. Changed default target FPS from 50 to 30, and default exposure from -9 (1/512s) to -8 (1/256s) for better out-of-the-box brightness.
- **2026-08-17 (v1.2.2):** Redesigned the "Project & Setup" tab into a cleaner 2-card layout ("Project & Presets" and "Hardware Configuration") using Grid alignment. Removed the manual Gain slider to save space and simplify the interface, hardcoding hardware gain to 0 during initialization.
- **2026-08-17 (v1.2.3):** Documentation overhaul (`README.md`). Fixed a quality degradation issue in `export_tab.py` by lowering the FFmpeg H.264 Constant Rate Factor (CRF) from 23 to 15, ensuring the resulting `.mp4` files are visually lossless compared to the raw MJPEG AVI recordings.
- **2026-08-17 (v1.2.4):** Bug-fix session across multiple files. **`export_tab.py`**: Fixed `AttributeError` crash on "Scan" button — `ProjectManager` has no `current_project_dir()` method; replaced with correct `base_path + current_project` path construction. Fixed AVI scan using non-recursive `glob` that never found files nested inside `takes/take_XYZ/synchronized_videos/`; switched to `glob(..., recursive=True)`. Fixed `TypeError` crash during conversion progress update caused by passing keyword args to `self.after()` — replaced with lambda. Changed FPS fallback from 50 to 30 (consistent with UI default). Added cleanup of incomplete `.mp4` output file when conversion fails mid-stream. **`camera_test_tab.py`**: Added guard to prevent "Run Scan" from silently killing an active recording. **`main.py`**: Fixed FPS fallback 50→30. **`preview_tab.py`**: Fixed lone German UI string "Aufnahme aktiv" → "Enable Recording". **`README.md`**: Restructured as bilingual (English first, German second).