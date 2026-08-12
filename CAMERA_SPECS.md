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
- **Externe Trigger:** Unterstützung (Verwenden Sie UVC Parameter "Fokus")

### Pin-Beschreibung (Trigger)
- **`FSIN +`** : Externer Trigger-Eingang (3,3 V–5 V) - *Direkt kompatibel mit 5V Arduino Ausgängen*
- **`FSIN -`** : Externe Masse (GND)

### Pin-Beschreibung (Strobe)
- **`STROBE +`** : Sensor-STROB+ (Signal für externen Blitz)
- **`STROBE -`** : Masse (GND)
