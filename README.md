# MoCapSTR: Sync / Trigger / Record for FreeMoCap

> [!CAUTION]
> ### ⚠️ Project Status: Experimental Prototype / Work in Progress
> **Please Note:** This project is currently undergoing active development and testing. It is **NOT YET in a state where it can be easily replicated as a turnkey / plug-and-play solution**. Hardware-level camera synchronization involves specific driver, USB controller bandwidth, and timing considerations. You may encounter issues depending on your hardware environment. Follow the issue tracker or discussions for ongoing updates.

> **Disclaimer:** MoCapSTR is an independent open-source companion tool and is not officially affiliated with the FreeMoCap project.

MoCapSTR is an open-source multi-camera recording tool designed to capture frame-accurate, hardware-synchronized video datasets for [FreeMoCap](https://github.com/freemocap/freemocap). It synchronizes global-shutter USB cameras (e.g. Innomaker OV9281) via an Arduino trigger signal, and also supports Blackmagic SDI capture cards.

---

## The Hardware Sync Challenge (USB Bandwidth)

Hardware-level synchronization has fundamentally different USB bandwidth requirements than standard webcam setups:

- **Free-Running Cameras (Standard Webcams / Standard FreeMoCap):** Cameras run on independent internal clocks. Their frames arrive staggered across time, so the data stream is naturally distributed.
- **Hardware-Triggered Mode (MoCapSTR):** An Arduino fires a 5V square-wave pulse to all cameras simultaneously. All connected cameras expose and push raw frame packets at the **exact same microsecond**.

### The Motherboard Bottleneck & Recommended Setup
Most standard PC motherboards share only 1 or 2 USB host controllers across all external USB ports:
- **Motherboard Limits:** In our testing, standard onboard USB controllers reliably handle a **maximum of 3 cameras** in hardware-trigger mode before bandwidth saturation causes dropped frames.
- **Recommended for 4+ Cameras (Verified Hardware):** We strongly recommend using a **PCIe USB expansion card with dedicated host controllers per port** (e.g. 4 separate USB controller chips on a single PCIe card) to ensure unconstrained bandwidth for all cameras.
  - **Tested & Verified Model:** **StarTech 4-Port USB 3.0 PCIe Card (Model: `P5Q4A-USB-CARD`)** — features 4 independent controller channels, reliably streaming 4 InnoMaker OV9281 cameras simultaneously without frame drops.
- **USB Polling Rate:** In the Setup tab, always set `USB Polling` at least 1 step higher than your target recording FPS (e.g. Target 30 FPS -> USB Polling 60 FPS) to ensure Windows polls the USB buffer fast enough.

<p align="center">
  <img src="3Dprint/v1_prototype/images_assembly/51_trigger_and_splitter_case_connected.jpg" width="480" alt="MoCapSTR Hardware Setup" />
  <br>
  <em>Arduino Trigger Box (with Start/Stop button) connected via XLR cable to the Splitter Box.</em>
</p>

---

## Features

- **Hardware Camera Synchronization:** Synchronous frame capture across all OV9281 cameras via Arduino FSIN pin (with auto-fallback to free-run mode if disconnected).
- **Zero-Copy PyAV Backend:** Writes raw MJPEG streams directly to disk via FFmpeg/PyAV without CPU decoding, minimizing frame drops.
- **Live Preview & Charuco Calibration:** Multi-camera live view with per-camera rotation (0°, 90°, 180°, 270°) and live `cv2.aruco` Charuco board detection overlay.
- **FreeMoCap Folder Structure:** Direct export into FreeMoCap's expected `synchronized_videos/` structure with matching frame counts.
- **Built-in Offline Converter:** Batch-converts raw `.avi` recordings into compatible H.264 (`.mp4`) files.
- **Hardware Diagnostics:** Built-in Camera Test tab to scan connected cameras for supported resolutions, framerates, and pixel formats.

---

## Quick Hardware Overview

1. **Wiring:**
   - Connect Arduino **GND** -> **GND** of all cameras.
   - Connect Arduino **Pin 2** -> **FSIN (Frame Sync In)** of all cameras.
   - *(Optional)* Connect physical Start/Stop push-button between Arduino **Pin 4** and **GND**.
2. **Guides & 3D Models:**
   - 3D printable files, fastener BOM, and step-by-step photo guide: [3Dprint & Assembly Guide](3Dprint/README.md).
   - Detailed wiring guide and splitter box schematic: [HARDWARE_SETUP.md](HARDWARE_SETUP.md).
   - Camera sensor specifications: [CAMERA_SPECS.md](CAMERA_SPECS.md).

---

## Installation

> **Pre-built Executable:** A ready-to-run `.exe` is available under [Releases](https://github.com/ZClassified/MoCapSTR/releases).

### Running from Source
- **Requirements:** Python 3.10+ (and [Blackmagic Desktop Video Drivers](https://www.blackmagicdesign.com/support/) if using SDI).

```bash
git clone https://github.com/ZClassified/MoCapSTR.git
cd MoCapSTR
pip install -r requirements.txt
python python/main.py
```
*(Flash the Arduino sketch from `arduino/trigger_firmware/trigger_firmware.ino` using the Arduino IDE).*

---

## Recording Workflow

1. **Setup Tab:** Choose project name and save folder (`~/Videos/MoCap_Projects/`). Select resolution, target FPS, and the Arduino COM port. Click **Initialize System & Start Preview**.
2. **Live Preview Tab:** Verify all camera feeds and rotations. Enable **Show Calibration (Auto-Detect)** when recording a Charuco calibration take.
3. **Record:** Start/Stop recording via the UI button or the physical button on the trigger box.
4. **Export & Convert Tab:** Batch-convert raw takes into FreeMoCap-compatible H.264 (`.mp4`) files.
5. **Import into FreeMoCap:** In FreeMoCap, select "Process Pre-recorded Data", navigate to your project folder (`calibration` or `takes/take_...`), and start tracking.

---

## License

GPL-3.0 License. See [LICENSE](LICENSE) for details.

---
---

# Deutsche Version

> **Hinweis:** MoCapSTR ist ein unabhängiges Open-Source Companion-Tool und steht nicht in offizieller Verbindung mit dem FreeMoCap-Projekt.

MoCapSTR ist eine Multi-Kamera-Aufnahmesoftware zur Erstellung synchroner, frame-genauer Datensätze für [FreeMoCap](https://github.com/freemocap/freemocap). Sie synchronisiert Global-Shutter USB-Kameras (z. B. Innomaker OV9281) über ein Arduino-Triggersignal und unterstützt zusätzlich Blackmagic SDI Capture Cards.

> [!WARNING]
> **Projektstatus (Beta / Prototyp):**
> Diese Software ist ein aktives Open-Source-Projekt im Prototypen-Stadium. Es können Fehler, Hardware-Inkompatibilitäten oder unerwartetes Verhalten auftreten. Feedback, Bug-Reports und Mithilfe sind über [GitHub Issues](https://github.com/ZClassified/MoCapSTR/issues) ausdrücklich willkommen!

---

## Die Herausforderung bei Hardware-Sync (USB-Bandbreite)

Hardware-Synchronisation stellt völlig andere Anforderungen an den USB-Bus als normale Webcams:

- **Free-Run Modus (Normale Webcams / Standard FreeMoCap):** Jede Kamera läuft auf ihrem eigenen internen Takt. Die Bildübertragungen treffen zeitlich leicht versetzt ein, wodurch sich die USB-Bandbreite natürlich verteilt.
- **Hardware-Trigger Modus (MoCapSTR):** Der Arduino sendet einen 5V-Rechteckimpuls zeitgleich an alle Kameras. Alle Kameras belichten und senden ihre JPEG-Datenpakete in der **exakt selben Mikrosekunde**.

### Der Mainboard-Flaschenhals & Hardware-Empfehlung
Auf herkömmlichen PC-Mainboards teilen sich fast alle USB-Ports nur 1 bis 2 interne USB-Host-Controller:
- **Mainboard-Limit:** In Praxistests schaffen normale Onboard-Controller im Hardware-Trigger-Modus **maximal 3 Kameras** zuverlässig. Bei 4 Kameras kommt es zu Bandbreiten-Staus und Frame-Drops.
- **Empfehlung für 4+ Kameras (Verifizierte Hardware):** Eine **PCIe-USB-Erweiterungskarte mit je einem dedizierten USB-Controller-Chip pro Port** (z. B. 4 getrennte Controller auf einer Karte) wird dringend empfohlen.
  - **Getestetes & verifiziertes Modell:** **StarTech 4-Port USB 3.0 PCIe-Karte (Modell: `P5Q4A-USB-CARD`)** — verfügt über 4 getrennte USB-Host-Controller und betreibt 4 InnoMaker OV9281 Kameras absolut reibungslos ohne Frame-Drops.
- **USB-Polling-Rate:** Im Setup-Tab muss `USB Polling` immer mindestens 1 Stufe höher eingestellt sein als die Ziel-FPS (z. B. Ziel 30 FPS -> Polling 60 FPS), damit Windows die USB-Puffer schnell genug leert.

<p align="center">
  <img src="3Dprint/v1_prototype/images_assembly/51_trigger_and_splitter_case_connected.jpg" width="480" alt="MoCapSTR Hardware Setup" />
  <br>
  <em>Arduino Trigger-Box (mit Start/Stop-Taster) über XLR-Kabel mit der Splitter-Box verbunden.</em>
</p>

---

## Features

- **Hardware-Kamera-Synchronisation:** Zeitgleiche Auslösung aller OV9281-Kameras über den Arduino FSIN-Pin (automatischer Fallback auf Free-Run bei getrenntem Arduino).
- **Zero-Copy PyAV Backend:** Schreibt rohe MJPEG-Streams via FFmpeg/PyAV ohne CPU-Decodierung direkt auf die Festplatte, um Frame-Drops zu vermeiden.
- **Live Preview mit Charuco-Erkennung:** Multi-Kamera-Vorschau mit individueller Bildrotation (0°, 90°, 180°, 270°) und zuschaltbarem `cv2.aruco` Charuco-Erkennungs-Overlay.
- **FreeMoCap-Ordnerstruktur:** Speichert direkt in `synchronized_videos/` mit identischer Frame-Anzahl über alle Kameras.
- **Integrierter Offline-Konverter:** Stapelverarbeitung zur Umwandlung von `.avi`-Aufnahmen in hochkompatible H.264-Videos (`.mp4`).
- **Hardware-Diagnose:** Kamera-Test-Tab zum automatischen Prüfen aller unterstützten Auflösungen, Frameraten und Formate verbundener Kameras.

---

## Schnellanleitung Hardware

1. **Verkabelung:**
   - Arduino **GND** -> **GND** aller Kameras.
   - Arduino **Pin 2** -> **FSIN** aller Kameras.
   - *(Optional)* Physischer Start/Stop-Taster zwischen Arduino **Pin 4** und **GND**.
2. **Anleitungen & 3D-Druck:**
   - Druckdateien, Stückliste und Foto-Montageanleitung: [3D-Druck- & Montage-Guide](3Dprint/README.md).
   - Detaillierte Verkabelung und Splitter-Box: [HARDWARE_SETUP.md](HARDWARE_SETUP.md).
   - Kameraspezifikationen: [CAMERA_SPECS.md](CAMERA_SPECS.md).

---

## Installation

> **Fertige EXE:** Eine ausführbare Windows-Datei (`.exe`) steht unter [Releases](https://github.com/ZClassified/MoCapSTR/releases) zum Download bereit.

### Start aus dem Quellcode
- **Voraussetzungen:** Python 3.10+ (und [Blackmagic Desktop Video Treiber](https://www.blackmagicdesign.com/support/) für SDI).

```bash
git clone https://github.com/ZClassified/MoCapSTR.git
cd MoCapSTR
pip install -r requirements.txt
python python/main.py
```
*(Den Arduino-Sketch aus `arduino/trigger_firmware/trigger_firmware.ino` über die Arduino IDE flashen).*

---

## Aufnahme-Workflow

1. **Setup Tab:** Projektname und Speicherordner wählen. Auflösung, Ziel-FPS und Arduino COM-Port einstellen. Auf **Initialize System & Start Preview** klicken.
2. **Live Preview Tab:** Kamera-Feeds und Rotation prüfen. Bei der Kalibrierungsaufnahme **Show Calibration (Auto-Detect)** aktivieren.
3. **Aufnahme:** Aufnahme über den Software-Button oder den physischen Taster an der Trigger-Box starten/stoppen.
4. **Export & Convert Tab:** Aufnahmen gesammelt in H.264 (`.mp4`) für FreeMoCap umwandeln.
5. **Import in FreeMoCap:** In FreeMoCap "Process Pre-recorded Data" wählen, den Projektordner auswählen und das Tracking starten.

---

## Lizenz

GPL-3.0 Lizenz. Siehe [LICENSE](LICENSE) für Details.