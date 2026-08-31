# Camera Specifications

**Model:** Innomaker USB 2.0 UVC Camera Module (OV9281)

## Sensor Details
- **Sensor:** 1/4'' OV9281 CMOS Sensor, 1 Mega Pixel, 1280(H) x 800(V), 3μm*3μm
- **Type:** Monochrom (schwarz/weiß Bild)
- **Shutter Type:** Global Shutter
- **S/N Verhältnis / Dynamikbereich:** 38dB / 68dB
- **Empfindlichkeit:** 6500 bis 13000 mV/uW

## Optics
- **FOV:** 140° (H) x 115° (V) x 62° (D)
- **Linsen Sitzbestand:** 18mm

## Video Output & Performance
- **USB-Type:** USB 2.0 High Speed, USB 2.0 OTG, USB Videoklasse (UVC)
- **Ausgabeparameter:** MJPG 1280x720 120fps
- **Ausgabeformat:** MJPG / YUY2
- **MJPG Auflösung & Bildrate:**
  - 1280x800 @ 120, 30, 15, 10 fps
  - 1280x720 @ 120, 60, 30, 20, 15, 10 fps
  - 800x600 @ 120, 60, 30, 20, 15, 10 fps
  - 640x400 @ 120, 60, 30, 20, 15, 10 fps
  - 640x360 @ 120, 60, 30, 20, 15, 10 fps
- **YUY2 Auflösung & Bildrate:**
  - 1280x800 @ 10 fps
  - 1280x720 @ 10 fps
  - 800x600 @ 10 fps
  - 640x480 @ 30, 20, 15, 10 fps
  - 640x400 @ 30, 20, 15, 10 fps
  - 320x240 @ 60, 30, 20, 15, 10 fps
  - 320x200 @ 60, 30, 20, 15, 10 fps

## Control Parameters (UVC)
- **Automatische Parameter:** Automatische Belichtungssteuerung (AEC) / Automatische Weißbilanz (AEB) / Automatische Verstärkungssteuerung (AGC)
- **Steuerbare Parameter:** Helligkeit, Kontrast, Farbton, Sättigung, Schärfe, Gamma, Weißabgleich, Hintergrundbeleuchtungskompensation, Verstärkung, Belichtung, PowerLine Frequenz, Low Light Kompensation

## Hardware & Connection
- **Kabellänge:** 1M
- **Unterstützung OS:** WinXP/Vista/Win7/Win8/Win10, Linux mit UVC (über linux-2.6.26), MAC-OS X 10.4.8 oder höher, Android 4.0 oder höher mit UVC

## External Trigger & Strobe
- **Externe Trigger:** Unterstützung (Aktivierung über UVC-Parameter `AutoFocus = 1` / `Focus = 0`)

### Pin-Beschreibung (Trigger)
- **`FSIN +`** : Externer Trigger-Eingang (3,3 V–5 V) - *Direkt kompatibel mit 5V Arduino Ausgängen*
- **`FSIN -`** : Externe Masse (GND)

### Pin-Beschreibung (Strobe)
- **`STROBE +`** : Sensor-STROB+ (Signal für externen Blitz)
- **`STROBE -`** : Masse (GND)

---

## Hardware-Trigger Frameraten & Timing-Charakteristik

Empirische Benchmark-Messungen mit MoCapSTR haben folgende Leistungsdaten für den InnoMaker OV9281 ermittelt:

| Betriebsmodus | Maximale Framerate | Verhalten |
| :--- | :--- | :--- |
| **Free-Run (Interner Takt)** | **120 FPS** (1280x720 / 1280x800) | Kontinuierliches Sensor-Pipelining, extrem flüssig. |
| **Hardware-Trigger (FSIN-Sync)** | **50 FPS** (1280x720 & 640x400) | Synchroner Frame-Zyklus im USB-ISP mit $\approx 18\text{–}20\text{ ms}$ Lockout. |

### Wichtige Erkenntnisse für den Trigger-Betrieb:
1. **50 FPS Hardware-Limit:** 
   Im Trigger-Modus benötigt der USB-Bridge-Chip der Kamera nach jedem Puls $\approx 18\text{–}20\text{ ms}$ für Belichtung, Zeilenauslese, JPEG-Kompression und USB-Endpunkt-Freigabe, bevor der Trigger-Eingang für den nächsten Frame freigeschaltet wird.
   - **50 Hz Trigger (20,0 ms Periode):** $\rightarrow$ **50.0 FPS** (1:1 sauber).
   - **60 Hz Trigger (16,6 ms Periode):** $\rightarrow$ **30.0 FPS** (1:2, jeder 2. Puls wird verworfen).
   - **90 Hz Trigger (11,1 ms Periode):** $\rightarrow$ **45.0 FPS** (1:2, jeder 2. Puls wird verworfen).
   - **120 Hz Trigger (8,33 ms Periode):** $\rightarrow$ **40.0 FPS** (1:3, 2 von 3 Pulsen werden verworfen).
2. **Empfohlene MoCapSTR-Einstellung:**
   - **Auflösung:** `1280x720 (720p)`
   - **Target FPS:** `50`
   - **USB Polling:** `Auto` (fordert 120 FPS USB-Stream an)
   - **Belichtung:** `-9` (1/512s) oder `-10` (1/1024s)
   - **Trigger-Pulsweite (Arduino):** `250 µs` bis `500 µs`

