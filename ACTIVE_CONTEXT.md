# Active Context

**Current Status:** Fixed OpenCV dynamic resolution bugs and set MSMF as default backend.
**Last Modified:** 2026-08-11 07:28:00

---

## Instructions for LLM Assistants
Welcome to the MoCapST project. This file (`ACTIVE_CONTEXT.md`) serves as the central memory for this repository. 

**Whenever you make significant changes to this project, you MUST update this file:**
1. Update the **Last Modified** timestamp to the current time.
2. Update the **Current Status** with a brief summary of what you just completed.
3. Append a short bullet point to the **Recent Changes** list below.

This ensures that the next AI assistant immediately knows what was just done and where the project currently stands.

## Recent Changes
- **2026-08-10:** Added dynamic FPS counter overlay to camera previews with color coding (Green/Yellow/Red) based on target framerate.
- **2026-08-10:** Added top control bar in Live Preview tab including Recording Timer, Frame Counter, Disk Space Warning, and live Dropped Frame detection.
- **2026-08-10:** Implemented `PresetManager` to save/load all UI settings to `presets.json`. Overhauled the Setup Tab UI using `CTkFrame` cards for better grouping.
- **2026-08-10:** Added FreeMoCap specific Charuco Board parameters (Dictionary, Grid, Sizes) and a live `cv2.aruco` detection overlay in the Live Preview tab.
- **2026-08-10:** Implemented Phase 1 of Blackmagic SDI Integration. Added "Camera Type" dropdown to UI to switch between USB and Blackmagic SDI. Modified CameraManager to apply resolution and framerate to DeckLink WDM filters before the first frame read to ensure successful initialization.
- **2026-08-10 (v1.0.3):** Refactored `main.py` UI into modular tab classes (`SetupTab`, `RecordTab`, `PreviewTab`). Implemented dynamic RAM-buffer for `recorder.py`. Fixed critical DirectShow / OpenCV format negotiation issue by cleanly pausing threads before applying camera settings, and initializing USB cameras with target resolution upfront. Added `pygrabber` dependency to robustly filter camera names.
- **2026-08-11:** Fixed dynamic resolution switching bug in `CameraManager.apply_settings` by forcing a full camera re-initialization on format changes, preventing 9 FPS fallback issues. Set MSMF as the default backend over DSHOW.
