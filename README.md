# MoCapST - OV9281 Hardware Sync & Recording Station

MoCapST ist eine spezialisierte Steuerungs- und Aufnahme-Software für markerloses Motion Capturing (spezifisch optimiert für **FreeMoCap**). Sie ermöglicht die hardware-synchrone Aufzeichnung von mehreren Global-Shutter-Kameras (wie der OV9281) mithilfe eines Arduino-Triggers.

## Features

- **Arduino Hardware Triggering:** Nutzt einen Arduino als hochpräzise Master-Clock, um alle Kameras auf die Millisekunde genau auszulösen.
- **Kamera-Kontrolle:** Voller Zugriff auf Auflösung und manuellen Shutter Speed (Belichtung) über UVC/DirectShow.
- **Multi-Threaded Recording:** Dedizierte Hintergrund-Threads für jede Kamera garantieren eine Aufnahme ohne Frame-Drops, selbst bei 6 Kameras gleichzeitig.
- **FreeMoCap Integration:** Speichert Aufnahmen automatisch in der Ordnerstruktur, die FreeMoCap für "Pre-recorded Data" (`synchronized_videos`) erwartet.
- **Live Preview:** Gleichzeitige Vorschau von bis zu 6 Kameras im Raster-Format.

---

## Hardware Setup

### Benötigte Hardware
- Mehrere USB Global-Shutter Kameras (z.B. Arducam OV9281) mit einem **External Trigger (FSIN)** Pin.
- Einen **Arduino** (z.B. Uno, Nano, Mega).

### Verkabelung
1. Verbinde den **GND**-Pin des Arduinos mit dem **GND**-Pin *aller* Kameras.
2. Verbinde den digitalen **Pin 2** des Arduinos mit dem **FSIN (Frame Sync In)** Pin *aller* Kameras.

---

## Installation

1. Klonen des Repositories:
   ```bash
   git clone https://github.com/ZClassified/MoCapST.git
   cd MoCapST
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

### Tab 1: Setup & Cameras
1. Klicke auf **Scan & Open Cameras**.
2. Wähle die gewünschte Auflösung und den manuellen Shutter Speed aus (z.B. 1/128s für schnelle Bewegungen) und klicke auf **Apply Camera Settings**.
3. Wähle den COM-Port deines Arduinos aus und klicke auf **Connect Arduino**.
4. Setze die gewünschte Framerate (FPS) und starte den Trigger. *(Hinweis: Die Vorschau funktioniert oft erst, wenn der Hardware-Trigger läuft).*

### Tab 2: Project & Recording
1. Gib deinem aktuellen Kamera-Setup einen **Projektnamen**. (Tipp: Wenn du die Kameras physisch verschiebst, lege ein neues Projekt an).
2. Wähle als Aufnahme-Typ entweder **Calibration** (für Aufnahmen des Charuco-Boards) oder **Motion Take**.
3. Wähle den gewünschten Video-Codec (Standard: MJPG .avi für maximale Performance).
4. Klicke auf **START RECORDING**.

### Tab 3: Live Preview
- Hier siehst du das aktuelle Bild aller Kameras (bis zu 6) im Grid.

---

## Import in FreeMoCap

Die Aufnahmen werden standardmäßig im Ordner `~/Videos/MoCap_Projects/[Projektname]/` gespeichert. 
Wenn du FreeMoCap öffnest:
1. Wähle "Process Pre-recorded Data".
2. Navigiere in deinen Projektordner und wähle entweder den Ordner `calibration` oder einen der Unterordner in `takes/` (z.B. `take_2026-08-10_10-45`).
3. FreeMoCap erkennt die synchronisierten Videos automatisch und kann mit dem Tracking beginnen.