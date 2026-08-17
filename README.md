# MoCapSTR: Sync / Trigger / Record for FreeMoCap

MoCapSTR ist eine spezialisierte Steuerungs- und Aufnahme-Software für markerloses Motion Capturing (spezifisch optimiert für **FreeMoCap**). Sie ermöglicht die synchrone Aufzeichnung von mehreren Kameras. Der Fokus liegt dabei auf Kameras mit Hardware-Trigger (z.B. OV9281) in Kombination mit einem Arduino, oder auf professionellen Capture Cards (z.B. Blackmagic Decklink 2 Duo SDI). Normale USB-Webcams (ohne Sync-Pin) können ebenfalls als Fallback genutzt werden, aber dann gibt es keinen signifikanter Vorteil gegenüber der direkten Aufnahme in FreeMoCap selber.

## Features

- **Performantes PyAV Backend:** Nutzt FFmpeg (PyAV), um rohe MJPEG-Streams ohne zusätzliche CPU-Decodierung direkt auf die Festplatte zu schreiben ("Zero-Copy stream muxing"). Das hilft dabei, Frame-Drops auch bei Setups mit vielen Kameras zu minimieren.
- **Breiter Kamera-Support:** Unterstützt USB-Kameras (DirectShow/MSMF) sowie **Blackmagic SDI** Signale. Virtuelle Kameras werden automatisch ignoriert.
- **Arduino Hardware Triggering:** Nutzt einen Arduino, um kompatible Kameras über ein Trigger-Signal (FSIN) absolut zeitgleich auszulösen. Beinhaltet einen automatischen Fallback auf den "Free-Run"-Modus, falls kein Arduino verbunden ist. Unterstützt externe Hardware-Buttons für die Fernsteuerung.
- **Live Preview mit Charuco-Detection:** Multikamera-Ansicht mit individueller Rotation (0°, 90°, 180°, 270°) und zuschaltbarem `cv2.aruco` Overlay zur direkten Überprüfung des Kalibrierungs-Boards. Die Top-Bar zeigt live Dropped Frames und warnt bei wenig Speicherplatz.
- **Preset Manager:** Speichert und lädt alle UI- und Projekt-Einstellungen automatisch über eine `presets.json`.
- **FreeMoCap Integration:** Speichert Aufnahmen in der passenden Ordnerstruktur und generiert automatisch die für FreeMoCap benötigten Metadaten (`session_info.json`).
- **Integrierter Konverter:** Da FreeMoCap rohe AVI-Dateien häufig nicht fehlerfrei verarbeiten kann, bietet die Software einen integrierten Tab, um die Aufnahmen nach der Session bequem offline in hochkompatible H.264-Videos (`.mp4`) umzuwandeln. Ein dedizierter Hardware-Test-Tab hilft zusätzlich bei der Kamera-Diagnostik.

---

## Hardware Setup

### Benötigte Hardware
- Mehrere USB Global-Shutter Kameras (z.B. Innomaker / Arducam OV9281) mit einem **External Trigger (FSIN)** Pin, *oder* Blackmagic SDI Capture Devices.
- Einen **Arduino** (z.B. Uno, Nano, Mega) für den Hardware-Trigger.

### Verkabelung
1. Verbinde den **GND**-Pin des Arduinos mit dem **GND**-Pin *aller* Kameras.
2. Verbinde den digitalen **Pin 2** des Arduinos mit dem **FSIN (Frame Sync In)** Pin *aller* Kameras.
3. *(Optional)* Verbinde einen externen physischen **Start/Stop-Button** mit **Pin 4** des Arduinos.
*(Weitere Details zur Verkabelung einer XLR Splitter Box findest du in `HARDWARE_SETUP.md` und detaillierte Kameraspezifikationen in `CAMERA_SPECS.md`. Fertige 3D-Modelle für den Druck der Hardware-Boxen liegen im Ordner `3Dprint` bereit.)*.

---

## Installation

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
1. **Project & Presets:** Gib dem Projekt einen Namen, wähle den Aufnahme-Typ (Calibration oder Motion Take) und lade ggf. vorherige Setup-Presets.
2. **Hardware Configuration:** 
   - Wähle den Kamera-Typ (USB oder SDI).
   - Definiere Auflösung, FPS (Standard 30), Codec und Belichtung (Exposure, z.B. 1/256s).
   - *Hinweis:* Der Arduino COM-Port wird in der Regel automatisch erkannt, kann hier aber manuell überschrieben werden.
3. **Initialize System:** Klicke auf diesen Button, um die Hardware vorzubereiten. Die Software öffnet die Kameras, verbindet sich bei Bedarf mit dem Arduino und startet den Trigger für die Live-Vorschau.
4. **Recording:** Bevor du deine Kalibrierung aufnimmst, setze den Haken bei **Show Calibration (Auto-Detect)** (im Live Preview Tab). Das Live-Overlay hilft dir, sicherzustellen, dass das Charuco-Board erkannt wird. Wenn du danach deine Bewegung aufnimmst, nimm den Haken wieder raus, da es sonst auch als Kalibrierung vermerkt wird und es Performance kostet.

### Tab 2: Live Preview
- Zeigt das Live-Bild aller initialisierten Kameras.
- Inklusive Top-Bar mit Aufnahme-Timer, Frame-Counter, FPS-Anzeige und Speicherplatz-Warnung. Nutze die FPS anzeige um zu prüfen ob die eingestellte FPS mit der tatsächlichen FPS den Kameras übereinstimmt. Ist das nicht der Fall, kann es dafür mehrere Gründe geben: viele webcams unterstützen nicht alle framerates, wie z.b. 25 oder 50, sondern sie können nativ nur 30 oder 60, sprich NTSC und nicht PAL (prüfbar im "4. Camera Tester" Tab). Kameras mit Trigger können dank des externen Triggers dieses Problem umgehen, da sie quasi auf Zuruf aufnehmen.
- Inklusive Charuco-Board Parametern und Checkbox für die Live-Detection direkt im Bild.

### Tab 3: Export & Convert
- Ein unverzichtbarer Schritt für den FreeMoCap Workflow: Da FreeMoCap die hochperformanten raw MJPEG (`.avi`) Aufnahmen nicht immer problemlos einlesen kann, wandelst du hier deine Takes nach der Session gesammelt offline in platzsparende und hochkompatible H.264 (`.mp4`) Videos um.

### Tab 4: Camera Test
- Ein Diagnostik-Tool, mit dem du verbundene Kameras "brute-forcen" kannst, um alle unterstützten Auflösungen, Framerates und Formate (MJPG / YUY2) zu scannen und abzugleichen.

---

## Import in FreeMoCap

Die Aufnahmen werden standardmäßig im Ordner `~/Videos/MoCap_Projects/[Projektname]/` gespeichert. 
Wenn du FreeMoCap öffnest:
1. Wähle "Process Pre-recorded Data".
2. Navigiere in deinen Projektordner und wähle entweder den Ordner `calibration` oder einen der Unterordner in `takes/` (z.B. `take_2026-08-10_10-45`).
3. FreeMoCap erkennt die synchronisierten Videos (inkl. der `session_info.json`) automatisch und kann mit dem Tracking beginnen.