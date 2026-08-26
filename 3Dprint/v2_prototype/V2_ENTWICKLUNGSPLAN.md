# MoCapSTR V2 Prototyp: Schlankes All-in-One Cat7 System (10m)

> **Status:** Entwicklungsplan & Bauanleitung für den V2-Prototyp  
> **Ziel:** Zusammenführung von USB 2.0 High-Speed (480 Mbit/s) und Hardware-Trigger (FSIN) in **ein einziges Cat7/Cat6a-Kabel (bis 10m)** pro Kamera.  
> **Ersetzt:** Das 2-Kabel-System aus V1 (separates USB-Kabel zum PC + XLR/DC-Triggerkabel zur Splitter-Box).  
> **Skalierbarkeit:** Basisaufbau für 4 Kameras, modular erweiterbar auf 6, 8 oder 12+ Kameras.

---

## 1. Systemübersicht & Funktionsweise

```
                       [ PC ] (PCIe-Karte mit dedizierten USB-Controllern)
                         │ (4x USB-A Kabel)
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                   MoCapSTR V2 MASTER-BOX                         │
│                                                                  │
│  [Arduino Nano]    ──> Trigger-Puls (Pin D2) über 33Ω Dämpfung   │
│                        an alle Ports (optional 74HCT125 Buffer)  │
│  [Taster Pin D4]   ──> Start/Stop Record-Steuerung               │
│  [4x USB vom PC]   ──> Liefert 5V Bus-Power & Daten für jeden Port│
│  [4x RJ45 / EtherCON geschirmt]                                  │
└───────┬──────────────────┬──────────────────┬──────────────────┬─┘
        │ Port 1           │ Port 2           │ Port 3           │ Port 4
        │ (10m Cat7)       │ (10m Cat7)       │ (10m Cat7)       │ (10m Cat7)
        ▼                  ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ KAMERA 1        │ │ KAMERA 2        │ │ KAMERA 3        │ │ KAMERA 4        │
│ - EtherCON / D  │ │ - EtherCON / D  │ │ - EtherCON / D  │ │ - EtherCON / D  │
│ - FE1.1s Hub    │ │ - FE1.1s Hub    │ │ - FE1.1s Hub    │ │ - FE1.1s Hub    │
│ - 100µF + 100nF │ │ - 100µF + 100nF │ │ - 100µF + 100nF │ │ - 100µF + 100nF │
│ - Innomaker     │ │ - Innomaker     │ │ - Innomaker     │ │ - Innomaker     │
│   OV9281 Sensor │ │   OV9281 Sensor │ │   OV9281 Sensor │ │   OV9281 Sensor │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Entwicklungs- & Teststrategie:
1. **Stufe 1 (Passiver Direkttest):** 
   * D+/D- Adern des 10m Cat7-Kabels zunächst direkt an die Innomaker OV9281 anlöten (ohne Hub-Modul).
   * Dank AWG 23 Kupferquerschnitt und PiMF-Einzelschirmung reicht das bei vielen PCIe-Controllern bereits für stabile 120 FPS.
2. **Stufe 2 (Re-Clocker bei Bedarf):** 
   * Sollten bei 10m Übertragungsfehler oder Resets auftreten, wird das kleine **FE1.1s Hub-Modul** als aktiver Signalauffrischer direkt vor die Kamera gesetzt.

---

## 2. Stückliste (Bill of Materials)

### A. Kameragehäuse (`Cam-BACK-V2`)
*Mengenangaben gelten **pro Kamera**:*

| Bauteil | Bezeichnung / Spezifikation | Bezugsquelle / Suchbegriff | Ca.-Preis |
| :--- | :--- | :--- | :--- |
| **Kamera-Modul** | Innomaker OV9281 Global Shutter USB | Aus V1 | *(vorhanden)* |
| **RJ45 Buchse** | Geschirmte RJ45 D-Typ Einbaubuchse (z. B. Neutrik EtherCON) | `Neutrik NE8FDP` / `RJ45 Panel Mount` | ~4 - 9 € |
| **USB-Hub Modul** | FE1.1s oder CH334P Mini USB 2.0 Hub | `FE1.1s USB Hub Module 4 Port Mini` | ~3 € |
| **Pufferkondensator (LF)**| 1x 100 µF / 16V (oder 25V) Elektrolytkondensator radial | Standard Elko | ~0,15 € |
| **Entstörkondensator (HF)**| 1x 100 nF (0,1 µF) Keramikkondensator (MLCC) | Standard Kerko 50V (RM 2.54 / 5.08) | ~0,05 € |
| **Trigger-Kabel** | JST 1.25mm 2-Pin Buchse mit Litzen (für FSIN Header) | `JST 1.25mm 2-pin cable` | ~0,30 € |
| **Lochrasterplatine**| Punktraster FR4 ca. 25 × 35 mm (optional zur Verdrahtung) | Lochraster FR4 | ~1,50 € |

> [!NOTE]
> **Kondensator-Kombination:**
> - Der **100 µF Elko** puffert Lastwechsel bei Streaming-Start ab.
> - Der **100 nF Keramikkondensator** (parallel geschaltet) besitzt minimale Eigeninduktivität und blockt hochfrequente Störspitzen der kamerainternen Schaltregler.

---

### B. Zentrale Master-Box (`Master_Case-V2`)
*Wird **einmal** für das Gesamtsystem aufgebaut (ausgelegt für 4 Ports, modular erweiterbar):*

| Bauteil | Bezeichnung / Spezifikation | Bezugsquelle / Suchbegriff | Ca.-Preis |
| :--- | :--- | :--- | :--- |
| **Mikrocontroller**| Arduino Nano V3 (CH340 oder FTDI) | Aus V1 | *(vorhanden)* |
| **RJ45 Buchsen** | 4x Geschirmte RJ45 D-Typ Einbaubuchsen (z. B. Neutrik EtherCON) | `Neutrik NE8FDP` | ~16,00 - 32,00 € |
| **Dämpfungswiderstände**| 4x 33 Ω bis 47 Ω Metallschicht (1/4 W) | 33R / 47R Widerstand | ~0,20 € |
| **USB-Zuleitungen**| 4x USB-A Kabel zum PC (0,5m – 1m) | Aus V1 / Standard | *(vorhanden)* |
| **Start/Stop Taster**| 12mm Drucktaster (Schließer / NO) | Aus V1 | ~1,00 € |
| **Status-LED** *(opt.)*| 1x 3mm/5mm LED (Trigger aktiv) + 1x 1 kΩ Widerstand | Standard | ~0,20 € |
| **Puffer-IC** *(opt. >4 Cams)*| 1x 74HCT125 oder 74ACT541 Logiktreiber | `74HCT125 DIP` | ~0,50 € |

---

### C. Verbindungskabel
* **1 bis 4 Stück:** Standard **Cat6a oder Cat7 S/FTP Patchkabel (7m bis 10m)** mit geschirmten Metall-RJ45-Steckern.

---

## 3. RJ45 Pinbelegung (T568B Standard)

Ausnutzung der 4 geschirmten Adernpaare (PiMF):

| RJ45 Pin | Aderfarbe (T568B) | Signal | Funktion & Verbindung |
| :---: | :--- | :--- | :--- |
| **1** | ⚪/🟠 Weiß-Orange | **USB D+** | USB 2.0 High-Speed Datenpaar $\rightarrow$ FE1.1s Upstream D+ |
| **2** | 🟠 Orange | **USB D-** | USB 2.0 High-Speed Datenpaar $\rightarrow$ FE1.1s Upstream D- |
| **3** | ⚪/🟢 Weiß-Grün | **Trigger Signal** | 5V Impuls vom Arduino Pin D2 (über 33–47 Ω) $\rightarrow$ OV9281 FSIN Pin |
| **4** | 🔵 Blau | **USB +5V (1/2)** | 5V Bus-Power vom PC-USB-Kabel (Ader 1 von 2) |
| **5** | ⚪/🔵 Weiß-Blau | **USB +5V (2/2)** | 5V Bus-Power vom PC-USB-Kabel (Ader 2 von 2) |
| **6** | 🟢 Grün | **Trigger GND** | Trigger-Masse vom Arduino $\rightarrow$ OV9281 FSIN GND |
| **7** | ⚪/🟤 Weiß-Braun | **USB GND (1/2)** | Masse vom PC-USB-Kabel (Ader 1 von 2) |
| **8** | 🟤 Braun | **USB GND (2/2)** | Masse vom PC-USB-Kabel (Ader 2 von 2) |
| **Gehäuse** | Metallschirm | **Shield** | Schirmung durchgehend mit PC-USB-Schirm verbunden |

---

## 4. Schaltpläne

### A. Kamera-Modul (`Cam-BACK-V2`)

```
RJ45 / EtherCON Buchse (Kamera)
══════════════════════════════

PIN 4 (Blau) ──────┬───> [+5V Schiene] ───────┬───> FE1.1s Hub [5V IN]
PIN 5 (Weiß-Blau) ─┘                          │
                                              ├───> Innomaker OV9281 [USB 5V]
                                              │
                                           [100µF Elko]  ──┐ (Parallel an 5V/GND,
                                           [100nF Kerko] ──┘  nah am Sensor)
                                              │
PIN 7 (Weiß-Braun) ─┬──> [GND Schiene] ───────┼───> FE1.1s Hub [GND]
PIN 8 (Braun) ──────┘                         │
                                              └───> Innomaker OV9281 [USB GND]

USB-DATEN:
PIN 1 (Weiß-Orange) ──────────────────────────────> FE1.1s Hub [Upstream D+]
PIN 2 (Orange) ───────────────────────────────────> FE1.1s Hub [Upstream D-]

FE1.1s Hub [Downstream D+] ───────────────────────> Innomaker OV9281 [USB D+] (< 3 cm)
FE1.1s Hub [Downstream D-] ───────────────────────> Innomaker OV9281 [USB D-] (< 3 cm)

TRIGGER:
PIN 3 (Weiß-Grün) ────────────────────────────────> Innomaker OV9281 [FSIN Pin 1 (Signal)]
PIN 6 (Grün) ─────────────────────────────────────> Innomaker OV9281 [FSIN Pin 2 (GND)]
```

---

### B. Master-Box (`Master_Case-V2`)

```
[ Arduino Nano ]
  Pin D2 (Trigger) ───┬──[33Ω Widerstand]──> RJ45 Port 1 Pin 3 (Trigger Signal)
                      ├──[33Ω Widerstand]──> RJ45 Port 2 Pin 3 (Trigger Signal)
                      ├──[33Ω Widerstand]──> RJ45 Port 3 Pin 3 (Trigger Signal)
                      └──[33Ω Widerstand]──> RJ45 Port 4 Pin 3 (Trigger Signal)

  Arduino GND ────────┬─────────────────────> RJ45 Port 1 Pin 6 (Trigger GND)
                      ├─────────────────────> RJ45 Port 2 Pin 6 (Trigger GND)
                      ├─────────────────────> RJ45 Port 3 Pin 6 (Trigger GND)
                      └─────────────────────> RJ45 Port 4 Pin 6 (Trigger GND)

  Pin D4 (Taster) ────> 12mm Taster (schaltet gegen GND, interner INPUT_PULLUP)

[ 4x USB-A Kabel zum PC / PCIe-Karte ]
  USB 1 (+5V, Rot)     ───> RJ45 Port 1 Pin 4 & Pin 5
  USB 1 (GND, Schwarz) ───> RJ45 Port 1 Pin 7 & Pin 8
  USB 1 (D+, Grün)     ───> RJ45 Port 1 Pin 1 (D+)
  USB 1 (D-, Weiß)     ───> RJ45 Port 1 Pin 2 (D-)
  USB 1 (Schirm)       ───> RJ45 Port 1 Metallgehäuse / Schirm

  *(Gleicher Aufbau für Ports 2, 3 und 4)*
```

---

## 5. Aufbauanleitung

### Phase 1: Kamera-Modul (`Cam-BACK-V2`)
1. **Hub vorbereiten:** Litzen für 5V, GND, D+, D- an die Upstream-Pads des FE1.1s löten. D+/D- verdrillen und kurz halten (< 15 mm).
2. **RJ45 verbinden:**
   * Pin 1 (D+) & Pin 2 (D-) an FE1.1s Upstream.
   * Pin 4 & 5 (+5V) an FE1.1s 5V und OV9281 5V.
   * Pin 7 & 8 (GND) an FE1.1s GND und OV9281 GND.
   * 100 µF Elko und 100 nF Keramikkondensator parallel zwischen 5V und GND setzen.
3. **Kamera & Trigger:**
   * FE1.1s Downstream-Port mit D+/D- der OV9281 verbinden.
   * Pin 3 (Signal) und Pin 6 (GND) über JST 1.25mm Kabel an den FSIN-Header der Kamera stecken.

---

### Phase 2: Master-Box (`Master_Case-V2`)
1. **Arduino & Taster montieren:**
   * Arduino Nano im Gehäuse fixieren.
   * 12mm Taster an **Pin D4** und **GND** anschließen.
2. **Trigger verdrahten:**
   * Von **Pin D2** 4 Abzweige mit je einem **33 Ω bis 47 Ω Widerstand** in Reihe an Pin 3 der Buchsen 1–4 führen.
   * Arduino GND an Pin 6 aller Buchsen legen.
3. **USB-Zuleitungen:**
   * 4 USB-Kabel abisolieren und Adern (5V, GND, D+, D-, Schirm) direkt an die zugehörigen Pins der 4 RJ45-Buchsen anlöten.

---

## 6. Skalierbarkeit (> 4 Kameras)

### A. USB-Bandbreite
* Jede Kamera arbeitet als eigener USB-Endpunkt über ihr eigenes Cat7-Kabel.
* Bei 120 FPS @ 1280x800 benötigt jede Kamera ~80–100 Mbit/s.
* Das System skaliert linear durch Einsatz von PCIe-Karten mit mehreren dedizierten Host-Controllern (z. B. Quad-Controller PCIe-Karten).

### B. Trigger-Signal
* **Bis 4 Kameras:** Direkte Ansteuerung über Pin D2 mit den 33–47 Ω Schutzwiderständen.
* **Ab 6–12+ Kameras:** Um die zunehmende Leitungskapazität (ca. 450 pF pro 10m Kabel) zu treiben, wird ein Standard-Bustreiber (z. B. **74HCT125** oder **74ACT541**) zwischen Arduino Pin D2 und die Vorwiderstände gesetzt. Dies garantiert auch bei vielen parallelen Kabeln steile Flanken ohne Jitter.

---

## 7. Inbetriebnahme & Tests

- [ ] **Test 1 (Durchgang & Kurzschluss):**
  * Multimeter-Messung zwischen 5V (Pin 4/5) und GND (Pin 7/8) vor dem Einstecken.
- [ ] **Test 2 (USB-Erkennung über 10m):**
  * Port 1 per Cat7 verbinden. Im Geräte-Manager prüfen: FE1.1s Hub und OV9281 Kamera werden fehlerfrei erkannt.
- [ ] **Test 3 (Streaming-Stabilität):**
  * Test-Skript (`tests_hardware/test_trigger_pyav.py` oder `python/main.py`) mit 1280x800 @ 120 FPS starten und auf Framedrops prüfen.
- [ ] **Test 4 (Hardware-Trigger):**
  * Taster betätigen und synchrone Bildauslösung aller Kameras verifizieren.

---

## 8. Gehäusehinweise (FreeCAD / 3D-Druck)

1. **`Cam-BACK-V2.FCStd`:**
   * Ausschnitt für die Neutrik EtherCON / RJ45 D-Typ Einbaubuchse (24 mm Lochkreis mit 2x M3 Befestigungslöchern).
   * Haltestege für FE1.1s Modul und Kondensatoren.
2. **`Master_Case-V2.FCStd`:**
   * Gehäuseaufnahme für Arduino Nano, 4x Neutrik EtherCON Buchsen, 4x Kabelauslässe und 12mm Taster.


