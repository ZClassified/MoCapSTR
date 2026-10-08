# MoCapSTR V2 Prototyp: Ein Cat-Kabel pro Kamera (USB 2.0 + Trigger + 5 V)

> **Status:** Entwicklungsplan & Bauanleitung für den V2-Prototyp (Revision 3, 2026-10-08)  
> **Ziel:** USB 2.0 High-Speed (480 Mbit/s), Hardware-Trigger (FSIN) und 5 V Versorgung über **ein einziges Cat6a/Cat7-Kabel (Ziel 10 m)** pro Kamera.  
> **Ersetzt:** Das 2-Kabel-System aus V1 (USB-Kabel zum PC + XLR/DC-Triggerkabel über die Splitter-Box).  
> **Skalierbarkeit:** Basisaufbau für 4 Kameras, ein Treiber-IC reicht für bis zu 8 Ports.

> [!IMPORTANT]
> **Nur das Kabel, kein LAN-Protokoll.** Über die Adern laufen USB, Trigger und 5 V. Die Buchsen dürfen **niemals** mit Switch, Router, Netzwerkkarte oder PoE-Injektor verbunden werden. Ein passiver 24-V-PoE-Injektor zerstört die Kamera, ein Ethernet-Port schließt das Trigger-Signal kurz. Alle Buchsen deutlich beschriften (z. B. „MoCap – KEIN LAN“).

> [!WARNING]
> **USB 2.0 über 10 m liegt außerhalb der USB-Spezifikation** (max. 5 m pro Kabelsegment). Die Rechnung (Abschnitt 6) spricht dafür, dass es bei direktem Anschluss an die PCIe-Karte funktioniert. Belegt ist das erst nach den Tests in Abschnitt 8. Deshalb zuerst **einen** Kamerakanal komplett aufbauen und mit verschiedenen Kabeln testen, dann die übrigen.

---

## 1. Systemübersicht

```
                       [ PC ] StarTech P5Q4A (1 Host-Controller pro Port)
                         │ 4x USB-A Kabel (0,5–1 m)
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│                     MoCapSTR V2 MASTER-BOX                         │
│                                                                    │
│  [Arduino Nano] D2 ──> [74ACT244] ──> 1 Ausgang pro Port, je 68 Ω  │
│                 D4 <── Start/Stop-Taster                           │
│  [4x USB vom PC] ──> 5 V, GND, D+, D− direkt auf die Ports         │
│  [4x RJ45 D-Typ Einbaubuchse mit Schraubklemmen]                   │
└───────┬──────────────────┬──────────────────┬──────────────────┬───┘
        │ Cat6a/Cat7       │                  │                  │
        │ 10 m             │                  │                  │
        ▼                  ▼                  ▼                  ▼
┌──────────────────┐  (Kamera 2)          (Kamera 3)          (Kamera 4)
│ KAMERA 1         │
│ - RJ45 D-Typ     │
│ - 10µF + 100nF   │
│ - Original-USB-  │
│   Stecker (5-pol)│
│ - FSIN-Stecker   │
│ - U20CAM-9281M   │
└──────────────────┘
```

### Herstellerdaten der Kamera (Innomaker U20CAM-9281M, Datenblatt Rev. 1.0)

| Merkmal | Wert | Bedeutung für V2 |
| :--- | :--- | :--- |
| Stromaufnahme | 5 V, **86 mA** (0,42 W) | Spannungsabfall auf 10 m unkritisch (Abschnitt 6) |
| USB-Stecker | 1,25 mm 5-polig (SHOU HAN ZZ-MS): 1 = 5 V, 2 = D−, 3 = D+, **4 = GND, 5 = GND** | beide schwarzen Adern sind Masse |
| Trigger-Eingang FSIN | 3,3–5 V; **Optokoppler-LED (Vf ≈ 1,25 V) mit 200 Ω auf der Platine** | Eingang ist galvanisch getrennt und zieht Strom: ~19 mA bei 5 V direkt |
| Trigger-Auslösung | steigende Flanke | wie V1 |

**Änderungen gegenüber Revision 1** (Begründung jeweils im Text):

| Punkt | Rev. 1 | Rev. 3 |
| :--- | :--- | :--- |
| USB-Hub an der Kamera | „Signalauffrischer“, Stufe 2 | **gestrichen** als Standard; ein Hub hilft nur in der Mitte der Strecke (Abschnitt 9) |
| Trigger-Treiber | Arduino-Pin direkt, Puffer optional ab 6 Kameras | **74ACT244 immer**, ein Ausgang pro Port; ein Arduino-Pin kann vier Optokoppler-LEDs (je ~19 mA) nicht treiben |
| Serienwiderstand Trigger | 33–47 Ω | **68 Ω** (LED-Strom ~13 mA, Kurzschlussstrom begrenzt) |
| Pufferkondensator Kamera | 100 µF | **10 µF** + 100 nF (USB-Grenzwert am Geräteeingang; bei 86 mA ausreichend) |
| Buchsen | Neutrik EtherCON NE8FDP (Durchführung, nicht lötbar) | **RJ45 D-Typ mit Schraubklemmen** (vorhanden) |
| Kameraanschluss | 4 Adern, auf die Platine gelötet | **5 Adern** laut Datenblatt, Original-Stecker bleibt steckbar |
| Kabel | „AWG 23“ angenommen | AWG unbekannt → Kabeltest-Matrix (Abschnitt 8) |

---

## 2. Stückliste (Bill of Materials)

### A. Pro Kamera (`Cam-BACK-V2`)

| Bauteil | Spezifikation | Status / Suchbegriff | Ca.-Preis |
| :--- | :--- | :--- | :--- |
| **Kamera-Modul** | Innomaker U20CAM-9281M (OV9281, Global Shutter, USB 2.0) | aus V1 | *(vorhanden)* |
| **RJ45-Buchse** | D-Typ Einbaubuchse, RJ45 mit 8-poliger Schraubklemme, Farbcode T568A/B | **vorhanden** | – |
| **USB-Pigtail** | Original-USB-Kabel der Kamera, ca. 5–8 cm hinter dem 5-poligen Stecker abgeschnitten | aus V1 | *(vorhanden)* |
| **Elko** | 10 µF / 16 V (oder 25 V), radial | Standard Elko | ~0,15 € |
| **Kerko** | 100 nF / 50 V MLCC | Standard Kerko | ~0,05 € |
| **Trigger-Kabel** | 2-poliger Stecker für den FSIN-Header, wie in V1 | aus V1 / wie V1 | ~0,30 € |
| **Aderendhülsen** | 0,14–0,25 mm², für die dünnen USB-Adern in den Schraubklemmen | Sortiment + Crimpzange | – |
| *(optional)* **ESD-Schutz** | USBLC6-2SC6 auf D+/D−/5 V, auf SOT-23-6-Adapterplatine | `USBLC6-2SC6` | ~1 € |

### B. Master-Box (`Master_Case-V2`, einmal für 4 Ports)

| Bauteil | Spezifikation | Status / Suchbegriff | Ca.-Preis |
| :--- | :--- | :--- | :--- |
| **Mikrocontroller** | Arduino Nano V3 | aus V1 | *(vorhanden)* |
| **RJ45-Buchsen** | 4x D-Typ Einbaubuchse mit Schraubklemmen (wie Kamera) | **vorhanden** | – |
| **Trigger-Treiber** | 1x **74ACT244** im DIP-20-Gehäuse (z. B. `SN74ACT244N`) + 20-poliger IC-Sockel. Treibt bis zu 8 Ports. | `74ACT244 DIP-20` | ~1 € |
| **Abblockkondensator** | 1x 100 nF direkt zwischen Pin 20 (VCC) und Pin 10 (GND) des 74ACT244 | Standard Kerko | ~0,05 € |
| **Stützkondensator** | 1x 10 µF an 5 V / GND auf der Lochrasterplatine | Standard Elko | ~0,15 € |
| **Serienwiderstände** | 4x 68 Ω Metallschicht 1/4 W | `68R Widerstand` | ~0,20 € |
| **USB-Zuleitungen** | 4x USB-A Kabel zum PC (0,5–1 m), aufgetrennt | aus V1 / Standard | *(vorhanden)* |
| **Start/Stop-Taster** | 12 mm Drucktaster (Schließer) | aus V1 | *(vorhanden)* |
| *(optional)* **Status-LED** | 3/5 mm LED + 1 kΩ, an einem freien Arduino-Pin | Standard | ~0,20 € |
| **Lochraster** | FR4, ca. 50 × 70 mm für 74ACT244 und Widerstände | Lochraster | ~1,50 € |

> [!NOTE]
> **Warum 74ACT244 und nicht 74HCT125:** Jede Kamera zieht über ihre Optokoppler-LED Strom (Abschnitt 5B). Die ACT-Familie ist für ±24 mA pro Ausgang spezifiziert, HC/HCT nur für ±4–6 mA. „ACT“ (nicht „AC“) ist wichtig, weil nur ACT die Eingangspegel für TTL hat; mit 5 V vom Arduino funktionieren aber beide.

### C. Kabel

| Bauteil | Spezifikation | Status |
| :--- | :--- | :--- |
| **Testkabel 1** | CAT7 S/FTP 4P, LSZH, CPR-Klasse Eca (Aufdruck ohne AWG-Angabe) | **vorhanden**, AWG per Messung bestimmen (Abschnitt 8, Test 0) |
| **Weitere Testkabel** | Cat6a/Cat7 S/FTP, 10 m (und als Vergleich 5 m / 7 m). Bevorzugt mit AWG-Angabe auf dem Mantel, AWG 24 oder dicker. | nach Bedarf |

> [!NOTE]
> **Schirmung:** Die vorhandenen Schraubklemmen-Buchsen haben keinen Schirmkontakt. Der Kabelschirm bleibt daher an beiden Enden unverbunden. Für USB 2.0 reicht die Verdrillung der Paare in der Regel aus. Treten im Test Störungen auf, die mit Kabelführung oder Nähe zu Netzteilen/Licht zusammenhängen, sind geschirmte Cat6a-Keystone-Module in einem D-Typ-Rahmen die Abhilfe (Schirm an beiden Enden auf GND).

---

## 3. Kamera-Anschluss (5-poliger USB-Stecker)

Laut Datenblatt (Abschnitt 2.5) hat der Kamerastecker diese Belegung:

| Stecker-Pin | Signal | Aderfarbe (Original-Kabel) |
| :---: | :--- | :--- |
| 1 | +5 V | Rot |
| 2 | D− | Weiß |
| 3 | D+ | Grün |
| 4 | GND | Schwarz |
| 5 | GND | Schwarz |

Beide schwarzen Adern sind Masse und kommen auf RJ45 Pin 7 und Pin 8.

> [!TIP]
> **Kurzer Gegencheck vor dem Abschneiden** (Kamera stromlos): Mit dem Multimeter Durchgang Rot ↔ Pin 1 des USB-A-Steckers (5 V), Weiß ↔ Pin 2 (D−), Grün ↔ Pin 3 (D+), Schwarz ↔ Pin 4 (GND). Damit ist ausgeschlossen, dass das Kabel abweichend von den Standardfarben konfektioniert ist.

---

## 4. RJ45-Pinbelegung (T568B)

Die Belegung nutzt jedes der 4 Adernpaare für genau eine Aufgabe. Die Stromversorgung liegt wie bei PoE „Mode B“ auf den Paaren 4/5 und 7/8. Das ist die Variante, die bei versehentlichem Einstecken in Netzwerk-Hardware am wenigsten Schaden anrichtet.

| RJ45 Pin | Aderfarbe (T568B) | Signal | Master-Box (USB-A-Kabel / Treiber) | Kamera (5-pol. Pigtail / FSIN) |
| :---: | :--- | :--- | :--- | :--- |
| **1** | ⚪/🟠 Weiß-Orange | **USB D+** | Grün | Grün |
| **2** | 🟠 Orange | **USB D−** | Weiß | Weiß |
| **3** | ⚪/🟢 Weiß-Grün | **Trigger** | 74ACT244-Ausgang über 68 Ω | FSIN + |
| **4** | 🔵 Blau | **+5 V** | Rot | Rot |
| **5** | ⚪/🔵 Weiß-Blau | **+5 V** | gebrückt mit Pin 4 | gebrückt mit Pin 4 |
| **6** | 🟢 Grün | **Trigger-GND** | Arduino GND | FSIN − |
| **7** | ⚪/🟤 Weiß-Braun | **GND** | Schwarz + Schirmgeflecht des USB-Kabels | Schwarz (Stecker-Pin 4) |
| **8** | 🟤 Braun | **GND** | gebrückt mit Pin 7 | Schwarz (Stecker-Pin 5) |
| **Schirm** | – | – | nicht verbunden (Buchse ohne Schirmkontakt) | nicht verbunden |

> [!TIP]
> Die Aderfarben in Spalte 2 beziehen sich auf das **Cat-Kabel**. An den Schraubklemmen zählen nur die Pin-Nummern 1–8. Beide Kabelenden sind T568B, also 1:1. Selbst konfektionierte Kabel mit einem Netzwerk-Kabeltester prüfen, **bevor** sie an die Buchsen kommen.

---

## 5. Schaltpläne

### A. Kamera (`Cam-BACK-V2`)

```
RJ45 Schraubklemme (Kamera)            5-pol. Pigtail / FSIN zur Kamera
═══════════════════════════            ═══════════════════════════════

PIN 4 ─┬─ (Brücke) ─────────┬──────────> Rot       (+5 V, Stecker-Pin 1)
PIN 5 ─┘                    │
                        [10µF] [100nF]   (direkt an der Klemme, Elko-Minus an GND)
PIN 7 ─┬─ (Brücke) ─────────┴──────────> Schwarz   (GND, Stecker-Pin 4)
PIN 8 ─┘ ──────────────────────────────> Schwarz   (GND, Stecker-Pin 5)

PIN 1 ─────────────────────────────────> Grün      (D+)  ┐ verdrillt lassen,
PIN 2 ─────────────────────────────────> Weiß      (D−)  ┘ max. 1 cm aufgedrillt

PIN 3 ─────────────────────────────────> FSIN +
PIN 6 ─────────────────────────────────> FSIN −
```

*Hinweis:* FSIN − ist wegen des Optokopplers **nicht** mit der Kamera-Masse verbunden. Pin 6 darf deshalb nicht mit Pin 7/8 gebrückt werden. Der Trigger braucht sein eigenes Adernpaar.

### B. Master-Box (`Master_Case-V2`)

```
                 74ACT244 (DIP-20), VCC = Arduino 5V, 100nF direkt an Pin 20/10
                ┌──────────────────────────────┐
Arduino D2 ──┬─ │ 2  1A1                1Y1 18 │ ──[68Ω]──> Port 1 Pin 3
             ├─ │ 4  1A2                1Y2 16 │ ──[68Ω]──> Port 2 Pin 3
             ├─ │ 6  1A3                1Y3 14 │ ──[68Ω]──> Port 3 Pin 3
             └─ │ 8  1A4                1Y4 12 │ ──[68Ω]──> Port 4 Pin 3
                │ 1  /1OE → GND                │
                │                              │
   (Ports 5–8)  │ 11 2A1                2Y1  9 │   Bei nur 4 Ports:
                │ 13 2A2                2Y2  7 │   2A1–2A4 (11,13,15,17) auf GND,
                │ 15 2A3                2Y3  5 │   /2OE (19) auf GND,
                │ 17 2A4                2Y4  3 │   Ausgänge 2Y frei lassen.
                │ 19 /2OE → GND                │
Arduino 5V ──── │ 20 VCC                GND 10 │ ──── Arduino GND
                └──────────────────────────────┘

Arduino GND ──┬──────────────────────────> Port 1 Pin 6
              ├──────────────────────────> Port 2 Pin 6
              ├──────────────────────────> Port 3 Pin 6
              └──────────────────────────> Port 4 Pin 6

Arduino D4 ──── 12mm Taster ──── GND        (INPUT_PULLUP, wie V1)

USB-A Kabel 1 (vom PC) → Port 1:
  Rot   (+5 V) ──> Pin 4 + Pin 5
  Schwarz (GND) + Schirmgeflecht ──> Pin 7 + Pin 8
  Grün  (D+)  ──> Pin 1
  Weiß  (D−)  ──> Pin 2
(Ports 2–4 identisch mit je eigenem USB-Kabel)
```

> [!WARNING]
> Unbenutzte Eingänge eines CMOS-ICs (hier 2A1–2A4) nie offen lassen, sondern auf GND legen. Offene Eingänge schwingen und erzeugen Störungen.

**Warum ein Treiber-IC statt des Arduino-Pins:**
* **Strom:** Der FSIN-Eingang ist eine Optokoppler-LED mit 200 Ω auf der Kameraplatine. Direkt an 5 V zieht jede Kamera ~19 mA, vier Kameras also ~75 mA. Ein Arduino-Pin verträgt max. 40 mA (empfohlen 20 mA).
* **LED-Strom mit 68 Ω:** (5 V − 1,25 V − ~0,3 V Treiberabfall) / (200 Ω + 68 Ω) ≈ **13 mA** pro Kamera. Innomaker legt die Beispielschaltung auf 20 mA aus; 10–15 mA reichen für eine sichere Auslösung. Löst eine Kamera nicht zuverlässig aus: 47 Ω (~14,5 mA).
* **Schutz:** Ein Kurzschluss an einem Port (z. B. versehentlich in Netzwerk-Hardware gesteckt) ist durch 68 Ω auf ~70 mA begrenzt und betrifft nur diesen Port. Bei 50 Hz und 250–500 µs Pulsbreite fließt dieser Strom nur 1–2,5 % der Zeit.
* **Signal:** 68 Ω plus Treiber-Ausgangswiderstand liegen nahe an der Impedanz des Adernpaars (100 Ω). Die Flanke kommt ohne nennenswerte Reflexionen an.

---

## 6. Rechnung: Signal und Spannungsabfall

### USB-Signal über 10 m

| Größe | USB-2.0-Spezifikation | 10 m Cat6a/Cat7 | Bewertung |
| :--- | :--- | :--- | :--- |
| Impedanz | 90 Ω ±15 % (76,5–103,5 Ω) | 100 Ω | innerhalb der Toleranz |
| Dämpfung bei ~200 MHz | ≤ 3,2 dB (5-m-Kabel) | ~3–4,5 dB (massive Adern besser, Litze schlechter) | gleiche Größenordnung, grenzwertig |
| Laufzeit | ≤ 26 ns pro Segment | ~50 ns | Budget ist für 5 Hub-Ebenen ausgelegt; bei direktem Anschluss in der Praxis meist unkritisch |

**Folgerung:** Wahrscheinlich machbar, aber nicht garantiert. Dickere Adern und kürzere Kabel verbessern die Reserve. Deshalb die Kabeltest-Matrix in Abschnitt 8.

### Spannungsabfall (je 2 Adern parallel für +5 V und GND)

| Kabel | Widerstand Hin + Rück (10 m) | Abfall bei 86 mA (Datenblatt) | Abfall bei 150 mA (Reserve für 120 FPS) |
| :--- | :--- | :--- | :--- |
| AWG 23 | ~0,7 Ω | ~0,06 V | ~0,11 V |
| AWG 24 | ~0,85 Ω | ~0,07 V | ~0,13 V |
| AWG 26/27 (typisches Patchkabel) | ~1,4 Ω | ~0,12 V | ~0,21 V |

**Folgerung:** Mit 86 mA ist die Stromversorgung über 10 m bei jedem Kabel unkritisch. Ziel an der Kamera: ≥ 4,5 V unter Last (Test 3).

---

## 7. Aufbauanleitung

### Phase 1: Ein Kamerakanal (Kamera 1 + Port 1)
1. **Gegencheck** des Kamerakabels (Abschnitt 3).
2. **Pigtail:** Original-USB-Kabel 5–8 cm hinter dem Kamerastecker abschneiden. Grün/Weiß verdrillt lassen. Aderendhülsen aufcrimpen (Adern nicht verzinnen; Zinn gibt unter Schraubklemmen mit der Zeit nach und die Klemme lockert sich).
3. **Kamera-Buchse** nach Abschnitt 5A verdrahten. Brücken 4–5 und 7–8 an der Klemme. Elko (Polarität!) und Kerko zwischen 5 V und GND.
4. **Trigger:** Pin 3 → FSIN +, Pin 6 → FSIN −. Polarität beachten: Die Optokoppler-LED leitet nur in einer Richtung.
5. **Master-Port 1:** USB-A-Kabel auftrennen, Adern nach Abschnitt 5B auf Port 1. Das Schirmgeflecht des USB-Kabels mit GND (Pin 7) verbinden.
6. **Trigger-Treiber:** 74ACT244 im Sockel auf Lochraster. /1OE und /2OE auf GND, 2A1–2A4 auf GND, 100 nF direkt an Pin 20/10, 68-Ω-Widerstände an 1Y1–1Y4. Für den ersten Test reicht der Widerstand an 1Y1 (Port 1).

### Phase 2: Restliche Kanäle
Erst nach bestandenen Tests 1–6 (Abschnitt 8) die Kanäle 2–4 identisch aufbauen.

---

## 8. Inbetriebnahme & Tests

| # | Test | Bestanden, wenn |
| :---: | :--- | :--- |
| 0 | **Kabel-AWG bestimmen** (Kabel nur zwischen den beiden noch unverdrahteten Buchsen): an der fernen Buchse Klemme 1 und 2 mit einem Drahtstück brücken, an der nahen Buchse Widerstand zwischen 1 und 2 messen; vorher Messleitungen kurzschließen und deren Widerstand abziehen. Ergebnis in die Matrix unten eintragen. | 10 m: **~1,3 Ω → AWG 23**, ~1,7 Ω → AWG 24, ~2,7 Ω → AWG 26, ~3,4 Ω → AWG 27 |
| 1 | **Durchgang & Kurzschluss** (alles stromlos, Kabel eingesteckt): Pin für Pin von USB-A-Stecker bis Kamerastecker; 5 V ↔ GND; Trigger ↔ D+/D−; Pin 6 ↔ Pin 7 (muss offen sein) | richtige Verbindungen, kein Kurzschluss |
| 2 | **Erkennung über 10 m:** Kamera allein, direkt an die PCIe-Karte. Prüfen mit [USB Device Tree Viewer](https://www.uwe-sieber.de/usbtreeview_e.html): Geschwindigkeit „High-Speed“ | Kamera erscheint als High-Speed, nicht Full-Speed |
| 3 | **Spannung an der Kamera** unter Last (Stream läuft), an den Klemmen 4/7 der Kamera-Buchse | ≥ 4,5 V |
| 4 | **Free-Run 120 FPS** (1280×720), 30 min Aufnahme in MoCapSTR mit deaktiviertem Hardware-Trigger; Kurzcheck vorab mit `tests_hardware/test_camera_fps.py` | keine Abbrüche/Resets, FPS stabil |
| 5 | **Trigger 50 FPS** (1280×720), 30 min Aufnahme in MoCapSTR | Clip-Prüfung im Log ohne Füllframes; `timestamps/cam*_timestamps.csv` ohne Lücken |
| 6 | **Steckzyklen:** 20x Cat-Kabel im Betrieb ziehen und stecken | Kamera kommt jedes Mal wieder, PC ohne Fehler |
| 7 | **Alle 4 Kanäle gleichzeitig**, Test 5 wiederholen; zusätzlich gemischt mit einer Kamera am Original-USB-Kabel | alle Clips gleich lang, keine Füllframes |

Treten Fehler nur über 10 m auf, aber nicht mit einem kurzen Kabel (1–2 m), liegt es an der Strecke. Dann Abschnitt 9.

### Kabeltest-Matrix

Für jedes Kabel Tests 0 und 2–5 durchführen und hier eintragen. So ist später nachvollziehbar, welche Kabel funktionieren.

| Kabel (Aufdruck) | Länge | Leiter (massiv / Litze) | R Paar 1–2 | ≈ AWG | Test 2 | Test 3 (V) | Test 4 | Test 5 | Bemerkung |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| CAT7 S/FTP 4P LSZH Eca | | | | | | | | | |
| | | | | | | | | | |
| | | | | | | | | | |

---

## 9. Plan B, falls 10 m nicht stabil laufen

In dieser Reihenfolge, vom günstigsten zum aufwendigsten:

1. **Besseres oder kürzeres Kabel:** AWG 23/24 statt 26/27; 7 m statt 10 m.
2. **Hub in der Mitte der Strecke:** Ein USB-2.0-Hub erzeugt das Signal neu, aber nur **hinter** sich. Direkt an der Kamera bringt er deshalb nichts, denn die kritische 10-m-Strecke liegt davor. In einer kleinen Kupplungsbox bei 5 m (zwei 5-m-Kabel, Box mit zwei RJ45-Buchsen) halbiert er die Strecke. Trigger- und Stromadern laufen in der Box einfach durch, der Hub nimmt sich seine 5 V von den Stromadern.
   * Vorhanden: ein grünes Hub-Modul ohne Typenbezeichnung, mit schwarzem Chip und silbernem Quarz (typisch FE1.1s oder CH334). Die Chip-Aufschrift mit Lupe oder Handyfoto prüfen; ein **USB-2.0-High-Speed**-Hub ist Pflicht. Ein USB-1.1-Hub würde die Kamera auf Full-Speed (12 Mbit/s) bremsen.
3. **Aktiver USB-über-Cat-Extender** (Sender- und Empfängerbox). Vor dem Kauf prüfen: echtes USB 2.0 **High-Speed** (viele günstige sind nur USB 1.1) und Unterstützung für **isochrone Übertragung / UVC-Webcams**. Der Trigger bräuchte dann ein eigenes Kabel oder freie Adern, je nach Gerät.

---

## 10. Skalierung (> 4 Kameras)

* **USB:** Pro Kamera ein eigener Host-Controller (StarTech P5Q4A: 4 Controller). Ab 5 Kameras eine zweite Karte. MJPEG 1280×720 braucht im Trigger-Betrieb (50 FPS) ca. 40–50 Mbit/s, im Free-Run (120 FPS) ca. 80–100 Mbit/s. Ein eigener Controller pro Kamera verhindert, dass sich die reservierte USB-Bandbreite gegenseitig blockiert.
* **Trigger:** Ports 5–8 über die zweite Hälfte des 74ACT244 (2A1–2A4 an D2 statt GND, je 68 Ω an 2Y1–2Y4). Ab 9 Ports ein zweiter 74ACT244, Eingänge ebenfalls an D2.
* **Strom:** 8 Kameras × 13 mA ≈ 105 mA Trigger-Strom aus dem 5-V-Pin des Arduino. Das kommt aus dessen USB-Anschluss (max. 500 mA) und ist unkritisch.

---

## 11. Hinweise zum Gehäusebau

* **Kamera:** Bautiefe hinter dem Flansch für die Schraubklemme einplanen, plus Platz für Schraubendreher, Kondensatoren und eine Zugentlastung des USB-Pigtails.
* **Master-Box:** Arduino Nano, Lochraster mit 74ACT244 (IC-Sockel zugänglich lassen), 4x D-Typ-Buchse, 4x Kabeldurchführungen mit Zugentlastung für die USB-A-Kabel, 12-mm-Taster.
* Ports nummerieren und beschriften („MoCap – KEIN LAN“).

---

## 12. Offene Punkte

- [ ] AWG des vorhandenen CAT7-Kabels per Test 0 bestimmen
- [ ] Weitere Testkabel beschaffen (Abschnitt 2C)
- [ ] Chip-Aufschrift des vorhandenen Hub-Moduls prüfen (nur relevant für Plan B)
- [ ] Bestellung: 74ACT244 (DIP-20) + Sockel, 68-Ω-Widerstände, 10-µF-Elkos, 100-nF-Kerkos, Lochraster, Aderendhülsen 0,14–0,25 mm²
