# MoCapSTR: Sync / Trigger / Record for FreeMoCap

MoCapSTR is a specialized control and recording application for markerless motion capture (optimized for **FreeMoCap**). It enables synchronized multi-camera recording, with a focus on hardware-triggered cameras (e.g. OV9281) combined with an Arduino, or professional capture cards (e.g. Blackmagic Decklink 2 Duo SDI). Standard USB webcams (without a sync pin) can also be used as a fallback, but offer no significant advantage over recording directly in FreeMoCap.

## Features

- **High-Performance PyAV Backend:** Uses FFmpeg (PyAV) to write raw MJPEG streams directly to disk without CPU decoding ("zero-copy stream muxing"), minimizing frame drops even with many cameras.
- **Broad Camera Support:** Supports USB cameras (DirectShow/MSMF) and **Blackmagic SDI** signals. Virtual cameras are automatically ignored.
- **Arduino Hardware Triggering:** Uses an Arduino to trigger compatible cameras simultaneously via an FSIN signal. Includes automatic fallback to free-run mode if no Arduino is connected. Supports external hardware buttons for remote control.
- **Live Preview with Charuco Detection:** Multi-camera view with per-camera rotation (0°, 90°, 180°, 270°) and a toggleable `cv2.aruco` overlay to verify calibration board detection. The top bar shows live dropped frames and warns when disk space is low.
- **Preset Manager:** Automatically saves and loads all UI and hardware settings (resolution, FPS, exposure, camera rotations, Charuco parameters) to a `presets.json` file next to the executable.
- **FreeMoCap Integration:** Saves recordings in the correct folder structure and automatically generates the metadata file (`session_info.json`) required by FreeMoCap.
- **Built-in Converter:** Since FreeMoCap often cannot reliably process raw AVI files, a dedicated tab lets you convert your takes offline into highly compatible H.264 (`.mp4`) videos after the session. A separate Camera Test tab assists with hardware diagnostics.

---

## Hardware Setup

### Required Hardware
- Multiple USB global-shutter cameras (e.g. Innomaker / Arducam OV9281) with an **External Trigger (FSIN)** pin, *or* Blackmagic SDI capture devices.
- An **Arduino** (e.g. Uno, Nano, Mega) for the hardware trigger.
- For Blackmagic SDI: **Blackmagic Desktop Video** drivers must be installed ([Download](https://www.blackmagicdesign.com/support/)).

### Wiring
1. Connect the **GND** pin of the Arduino to the **GND** pin of *all* cameras.
2. Connect digital **Pin 2** of the Arduino to the **FSIN (Frame Sync In)** pin of *all* cameras.
3. *(Optional)* Connect an external physical **Start/Stop button** to **Pin 4** of the Arduino.

*(Further wiring details for an XLR splitter box are in `HARDWARE_SETUP.md`, detailed camera specs in `CAMERA_SPECS.md`. Ready-to-print 3D models for hardware enclosures are in the `3Dprint` folder.)*

### Important Hardware Limitations (USB Bandwidth)
When using the Arduino Hardware Trigger, all cameras send their frames at the exact same microsecond. This causes a massive bandwidth spike on the USB bus. 
- **The Limit:** A single USB 2.0 controller (480 Mbps) **cannot** handle 4 cameras at 720p 30+ FPS simultaneously in hardware-trigger mode. It will result in dropped frames (e.g. recording at 15 or 12.5 FPS).
- **The Solution:** You must split the 4 cameras across **multiple physical USB controllers** on your PC. Plugging 2 cameras into the front panel and 2 into the rear I/O (or using a dedicated PCIe USB expansion card with dedicated controllers per port) doubles the bandwidth and completely resolves the bottleneck.
- **USB Polling FPS:** In the Setup Tab, the `USB Polling` dropdown must always be set to at least one step *higher* than your target recording FPS (e.g. Target 25 -> USB Polling 30. Target 30 -> USB Polling 60). This ensures the USB polling interval is fast enough to catch the hardware-triggered frames without drops.

---

## Installation

> **Note:** A pre-built `.exe` is available as a release download if you prefer not to install Python.

### Requirements
- **Python 3.10 or newer**
- For **Blackmagic SDI**: Install the [Blackmagic Desktop Video](https://www.blackmagicdesign.com/support/) drivers.

### Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/ZClassified/MoCapSTR.git
   cd MoCapSTR
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Flash the Arduino sketch `arduino/trigger_firmware/trigger_firmware.ino` to your Arduino using the Arduino IDE.

---

## Usage (Recording Workflow)

Launch the GUI with:
```bash
python python/main.py
```

### Tab 1: Project & Setup
Configure all essential settings for your recording session:

1. **Project & Presets:**
   - Enter a project name and choose a save directory via **Browse...** (default: `~/Videos/MoCap_Projects/`).
   - Select the recording codec (MJPEG is recommended for maximum FreeMoCap compatibility).
   - Load or save presets to reuse your configuration in future sessions.

2. **Workflow Selection:**
   - **Option 1: Innomaker USB (+ Arduino Trigger)** – for hardware-trigger cameras (OV9281 etc.).
   - **Option 2: Blackmagic SDI (Genlock)** – for professional SDI capture cards.

3. **Hardware Configuration:**
   - Select resolution, target FPS, and **USB Polling** (USB Polling automatically adapts to be 1 step higher than target FPS).
   - *(USB only)* Set exposure via the slider (e.g. `-8` = 1/256s). A warning appears if the exposure time would exceed the frame cycle.
   - *(USB only)* Enable or disable the **UVC Hardware Trigger** via checkbox. The Arduino COM port is detected automatically but can be selected manually from the dropdown and refreshed with **Refresh**.

4. **Initialize System & Start Preview:** Click this button to prepare the hardware. The app opens the cameras, connects to the Arduino if needed, and starts the trigger for the live preview.

5. **Calibration vs. Motion Take:**
   - Before recording a calibration, check **Show Calibration (Auto-Detect)** in the *Live Preview Tab*. The overlay lets you verify the Charuco board is detected. The recording is then automatically marked as a calibration.
   - For normal motion takes, uncheck it — this saves performance and prevents the take from being incorrectly flagged as a calibration.

### Tab 2: Live Preview
- Shows the live feed of all initialized cameras.
- **Top bar** with recording timer, frame counter, live FPS display, and low disk space warning.
  - Use the FPS display to check whether the configured FPS matches the actual camera FPS. Many webcams natively support only 30 or 60 FPS (NTSC), not 25 or 50 (PAL). Hardware-triggered cameras bypass this by firing on Arduino command.
- Charuco board parameters (dictionary, columns, rows, square size, marker size) and a checkbox for live detection overlay.
- Per-camera rotation (0°, 90°, 180°, 270°) settable directly via dropdown.

### Tab 3: Export & Convert
- An essential step in the FreeMoCap workflow: since FreeMoCap cannot always reliably read raw MJPEG (`.avi`) files, use this tab to batch-convert your takes offline into space-efficient, highly compatible H.264 (`.mp4`) videos.

### Tab 4: Camera Test
- A diagnostic tool to brute-force scan connected cameras for all supported resolutions, framerates, and formats (MJPG / YUY2).

---

## Import into FreeMoCap

Recordings are saved by default to `~/Videos/MoCap_Projects/[ProjectName]/`.
When you open FreeMoCap:
1. Select "Process Pre-recorded Data".
2. Navigate to your project folder and select either the `calibration` folder or one of the subfolders in `takes/` (e.g. `take_2026-08-10_10-45-00`).
3. FreeMoCap will automatically detect the synchronized videos (including `session_info.json`) and can begin tracking.

---
---

# Deutsche Version

MoCapSTR ist eine spezialisierte Steuerungs- und Aufnahme-Software für markerloses Motion Capturing (spezifisch optimiert für **FreeMoCap**). Sie ermöglicht die synchrone Aufzeichnung von mehreren Kameras. Der Fokus liegt dabei auf Kameras mit Hardware-Trigger (z.B. OV9281) in Kombination mit einem Arduino, oder auf professionellen Capture Cards (z.B. Blackmagic Decklink 2 Duo SDI). Normale USB-Webcams (ohne Sync-Pin) können ebenfalls als Fallback genutzt werden, aber dann gibt es keinen signifikanten Vorteil gegenüber der direkten Aufnahme in FreeMoCap selber.

## Features

- **Performantes PyAV Backend:** Nutzt FFmpeg (PyAV), um rohe MJPEG-Streams ohne zusätzliche CPU-Decodierung direkt auf die Festplatte zu schreiben ("Zero-Copy stream muxing"). Das hilft dabei, Frame-Drops auch bei Setups mit vielen Kameras zu minimieren.
- **Breiter Kamera-Support:** Unterstützt USB-Kameras (DirectShow/MSMF) sowie **Blackmagic SDI** Signale. Virtuelle Kameras werden automatisch ignoriert.
- **Arduino Hardware Triggering:** Nutzt einen Arduino, um kompatible Kameras über ein Trigger-Signal (FSIN) absolut zeitgleich auszulösen. Beinhaltet einen automatischen Fallback auf den "Free-Run"-Modus, falls kein Arduino verbunden ist. Unterstützt externe Hardware-Buttons für die Fernsteuerung.
- **Live Preview mit Charuco-Detection:** Multikamera-Ansicht mit individueller Rotation (0°, 90°, 180°, 270°) und zuschaltbarem `cv2.aruco` Overlay zur direkten Überprüfung des Kalibrierungs-Boards. Die Top-Bar zeigt live Dropped Frames und warnt bei wenig Speicherplatz.
- **Preset Manager:** Speichert und lädt alle UI- und Hardware-Einstellungen (Auflösung, FPS, Belichtung, Kamera-Rotationen, Charuco-Parameter) automatisch in einer `presets.json` neben der ausführbaren Datei.
- **FreeMoCap Integration:** Speichert Aufnahmen in der passenden Ordnerstruktur und generiert automatisch die für FreeMoCap benötigten Metadaten (`session_info.json`).
- **Integrierter Konverter:** Da FreeMoCap rohe AVI-Dateien häufig nicht fehlerfrei verarbeiten kann, bietet die Software einen integrierten Tab, um die Aufnahmen nach der Session bequem offline in hochkompatible H.264-Videos (`.mp4`) umzuwandeln. Ein dedizierter Hardware-Test-Tab hilft zusätzlich bei der Kamera-Diagnostik.

---

## Hardware Setup

### Benötigte Hardware
- Mehrere USB Global-Shutter Kameras (z.B. Innomaker / Arducam OV9281) mit einem **External Trigger (FSIN)** Pin, *oder* Blackmagic SDI Capture Devices.
- Einen **Arduino** (z.B. Uno, Nano, Mega) für den Hardware-Trigger.
- Für Blackmagic SDI: **Blackmagic Desktop Video** Treiber müssen installiert sein ([Download](https://www.blackmagicdesign.com/support/)).

### Verkabelung
1. Verbinde den **GND**-Pin des Arduinos mit dem **GND**-Pin *aller* Kameras.
2. Verbinde den digitalen **Pin 2** des Arduinos mit dem **FSIN (Frame Sync In)** Pin *aller* Kameras.
3. *(Optional)* Verbinde einen externen physischen **Start/Stop-Button** mit **Pin 4** des Arduinos.

*(Weitere Details zur Verkabelung einer XLR Splitter Box findest du in `HARDWARE_SETUP.md` und detaillierte Kameraspezifikationen in `CAMERA_SPECS.md`. Fertige 3D-Modelle für den Druck der Hardware-Boxen liegen im Ordner `3Dprint` bereit.)*

### Wichtige Hardware-Limitierungen (USB-Bandbreite)
Beim Einsatz des Arduino Hardware-Triggers senden alle Kameras ihre Bilder auf die exakt selbe Mikrosekunde. Das erzeugt einen massiven Bandbreiten-Stau (Spike) auf dem USB-Bus.
- **Das Limit:** Ein einzelner USB 2.0 Controller (480 Mbps) **kann keine** 4 Kameras bei 720p und 30+ FPS gleichzeitig im Trigger-Modus bewältigen. Die Kameras verschlucken sich am Stau und die Framerate halbiert sich exakt (z.B. auf 15 oder 12,5 FPS).
- **Die Lösung:** Die 4 Kameras müssen zwingend auf **mehrere physikalische USB-Controller** am PC aufgeteilt werden. Das Einstecken von 2 Kameras an der Frontblende und 2 Kameras hinten am Mainboard (oder die Nutzung einer PCIe USB-Erweiterungskarte mit eigenen Controllern pro Port) verdoppelt die Bandbreite und löst den Flaschenhals komplett.
- **USB Polling FPS:** Im Setup-Tab muss das Dropdown `USB Polling` immer mindestens eine Stufe *höher* eingestellt sein als die gewünschte Ziel-FPS für die Aufnahme (z.B. Target 25 -> USB Polling 30; Target 30 -> USB Polling 60). Nur so ist das Abfrage-Intervall von Windows schnell genug, um die Hardware-getriggerten Bilder verlustfrei einzufangen.

---

## Installation

> **Hinweis:** Es steht auch eine fertige `.exe` als Release zum Download bereit, falls du Python nicht installieren möchtest.

### Voraussetzungen
- **Python 3.10 oder neuer**
- Für **Blackmagic SDI**: [Blackmagic Desktop Video](https://www.blackmagicdesign.com/support/) Treiber installieren.

### Schritte

1. Klonen des Repositories:
   ```bash
   git clone https://github.com/ZClassified/MoCapSTR.git
   cd MoCapSTR
   ```
2. Python-Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```
3. Flashe den Arduino-Sketch `arduino/trigger_firmware/trigger_firmware.ino` über die Arduino IDE auf deinen Arduino.

---

## Benutzung (Recording Workflow)

Starte die GUI mit:
```bash
python python/main.py
```

### Tab 1: Project & Setup
Hier nimmst du alle wesentlichen Einstellungen für deine Aufnahme-Session vor:

1. **Project & Presets:**
   - Gib dem Projekt einen Namen und wähle den Speicherordner über **Browse...** (Standard: `~/Videos/MoCap_Projects/`).
   - Wähle den Aufnahme-Codec (für maximale Kompatibilität mit FreeMoCap wird MJPEG empfohlen).
   - Lade oder speichere Setup-Presets, um deine Konfiguration für spätere Sessions zu sichern.

2. **Workflow-Auswahl:**
   - **Option 1: Innomaker USB (+ Arduino Trigger)** – für Hardware-Trigger-Kameras (OV9281 o.ä.).
   - **Option 2: Blackmagic SDI (Genlock)** – für professionelle SDI Capture Cards.

3. **Hardware Configuration:**
   - Wähle Auflösung, Ziel-FPS und **USB Polling** (USB Polling passt sich automatisch an, sodass es 1 Stufe über der Ziel-FPS liegt).
   - *(Nur USB)* Stelle die Belichtung über den Slider ein (z.B. `-8` = 1/256s). Ein Warnhinweis erscheint, falls die Belichtungszeit den Framezyklus überschreiten würde.
   - *(Nur USB)* Aktiviere oder deaktiviere den **UVC Hardware Trigger** per Checkbox. Der Arduino COM-Port wird automatisch erkannt, kann aber manuell aus der Dropdown-Liste gewählt und über **Refresh** aktualisiert werden.

4. **Initialize System & Start Preview:** Klicke auf diesen Button, um die Hardware vorzubereiten. Die Software öffnet die Kameras, verbindet sich bei Bedarf mit dem Arduino und startet den Trigger für die Live-Vorschau.

5. **Kalibrierung vs. Motion Take:**
   - Bevor du deine Kalibrierung aufnimmst, setze den Haken bei **Show Calibration (Auto-Detect)** im *Live Preview Tab*. Das Overlay hilft dir zu prüfen, ob das Charuco-Board erkannt wird. Die Aufnahme wird dann automatisch als Kalibrierung vermerkt.
   - Für normale Motion-Takes nimmst du den Haken wieder raus — das spart Performance und verhindert, dass der Take fälschlicherweise als Kalibrierung markiert wird.

### Tab 2: Live Preview
- Zeigt das Live-Bild aller initialisierten Kameras.
- **Top-Bar** mit Aufnahme-Timer, Frame-Counter, Live-FPS-Anzeige und Speicherplatz-Warnung.
  - Nutze die FPS-Anzeige, um zu prüfen, ob die eingestellte FPS mit der tatsächlichen FPS der Kameras übereinstimmt. Viele Webcams unterstützen nativ nur 30 oder 60 FPS (NTSC), nicht 25 oder 50 (PAL). Kameras mit Hardware-Trigger umgehen dieses Problem, da sie auf Zuruf des Arduinos aufnehmen.
- Charuco-Board Parameter (Dictionary, Spalten, Reihen, Quadrat- und Marker-Größe) und Checkbox für die Live-Detection direkt im Bild.
- Individuelle Rotation je Kamera (0°, 90°, 180°, 270°) direkt per Dropdown einstellbar.

### Tab 3: Export & Convert
- Ein unverzichtbarer Schritt für den FreeMoCap Workflow: Da FreeMoCap die hochperformanten raw MJPEG (`.avi`) Aufnahmen nicht immer problemlos einlesen kann, wandelst du hier deine Takes nach der Session gesammelt offline in platzsparende und hochkompatible H.264 (`.mp4`) Videos um.

### Tab 4: Camera Test
- Ein Diagnostik-Tool, mit dem du verbundene Kameras "brute-forcen" kannst, um alle unterstützten Auflösungen, Framerates und Formate (MJPG / YUY2) zu scannen und abzugleichen.

---

## Import in FreeMoCap

Die Aufnahmen werden standardmäßig im Ordner `~/Videos/MoCap_Projects/[Projektname]/` gespeichert.
Wenn du FreeMoCap öffnest:
1. Wähle "Process Pre-recorded Data".
2. Navigiere in deinen Projektordner und wähle entweder den Ordner `calibration` oder einen der Unterordner in `takes/` (z.B. `take_2026-08-10_10-45-00`).
3. FreeMoCap erkennt die synchronisierten Videos (inkl. der `session_info.json`) automatisch und kann mit dem Tracking beginnen.