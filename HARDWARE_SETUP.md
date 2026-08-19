# Hardware Setup & Wiring Guide

Dieses Dokument beschreibt die Verkabelung des MoCapSTR Hardware-Triggers über eine XLR-Splitter-Box, basierend auf dem Arduino-Sync-Modul und Innomaker OV9281 Kameras.

## Das Prinzip: XLR-Splitter

Anstatt lange Kabel direkt vom Arduino zu jeder Kamera zu ziehen, wird das 5V-Rechtecksignal des Arduinos über ein XLR-Mikrofonkabel zu einer zentralen Splitter-Box am Set geführt. Von dieser Box gehen dann die Endkabel zu den 4 Kameras. 

Da das Trigger-Signal asymmetrisch ("unbalanced") ist (bestehend aus Signal und Masse), passen wir die 3-polige XLR-Belegung entsprechend an.

---

## 1. Arduino Gehäuse (Sender)

Am Gehäuse des Arduinos werden ein Taster und eine XLR-Buchse (Männlich) verbaut.

### Taster (Fernbedienung)
Der Taster nutzt die interne `INPUT_PULLUP` Funktion des Arduinos.
- **Start/Stop Record Button:** Verbindet Arduino **Pin 4** mit Arduino **GND**.
*(Dieser Taster sendet einen Befehl an die Software. Die Kameras erhalten dauerhaft das Trigger-Signal, wenn der Modus aktiv ist.)*

### XLR-Buchse (Ausgang zur Splitter-Box)
- **XLR Pin 1 (Masse/Schirm):** Mit Arduino **GND** verbinden.
- **XLR Pin 2 (Signal Hot):** Mit Arduino **Pin 2** verbinden.
- **XLR Pin 3 (Signal Cold):** Brücken mit XLR Pin 1 (Masse).

---

## 2. Die Splitter-Box (Verteiler)

Die Splitter-Box hat einen XLR-Eingang (Weiblich) und gibt das Signal an 4 Kabelstränge weiter, die zu den Kameras führen.

### Interne Verdrahtung in der Box:
1. **Das Signal (Hot):** Das ankommende Signal von **XLR Pin 2** wird aufgesplittet und an die **vier roten Adern** der Kamerakabel angelötet. 
2. **Die Masse (GND):** Die ankommende Masse von **XLR Pin 1** wird aufgesplittet und an die **vier weißen/schwarzen Adern** der Kamerakabel angelötet.
3. **Die Schirmung der 4 Kabel:** Die Schirmung (das Drahtgeflecht) der vier abgehenden Kamerakabel wird ebenfalls komplett zusammengeführt und an **XLR Pin 1 (Ground)** angelötet.

*(Pin 3 der XLR-Eingangsbuchse kann hier einfach mit Pin 1 gebrückt werden oder leer bleiben).*

---

## 3. Anschluss an die Kameras (Innomaker)

Die vier Kabel kommen nun von der Splitter-Box an den Kameras an. Wir nutzen die einseitige Schirmerdung, um Brummschleifen (Ground Loops) zu vermeiden!

- **Rote Ader (Signal):** Anschließen an den **FSIN +** Pin der Kamera.
- **Weiße/Schwarze Ader (Masse):** Anschließen an den **FSIN -** Pin der Kamera.
- **Schirmung (Drahtgeflecht):** Bündig abschneiden und gut isolieren! Die Schirmung darf an der Kamera **NICHT** angeschlossen werden oder Metall berühren. 

*Grund:* Die Schirmung fängt elektromagnetische Störungen auf der gesamten Strecke auf und leitet sie über die Splitter-Box und das XLR-Kabel sicher in den Ground des Arduinos ab (Faradayscher Käfig). Wäre sie auf beiden Seiten angeschlossen, könnten Störströme durch das Kabel fließen.

---

## Kabel-Empfehlung
Ein 2-adriges, geschirmtes Audiokabel (z.B. `2x 0.08 mm²` oder DMX-Steuerkabel) ist ideal für die Strecke von der Splitter-Box zu den Kameras. Für die Strecke zwischen Arduino und Box reicht jedes handelsübliche XLR-Mikrofonkabel.
