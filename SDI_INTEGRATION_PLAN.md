# Blackmagic SDI & Genlock Integrationsplan (MoCapSTR)

Dieses Dokument beschreibt die Architektur und den Stufenplan zur Erweiterung der MoCapSTR-Software um professionellen SDI-Kamera-Support via Blackmagic DeckLink Karten sowie die Evaluierung und Umsetzung von Hardware-Synchronisation (Genlock).

## 1. Ausgangssituation & Ziel
Aktuell nutzt MoCapSTR USB-Webcams, die über OpenCV und DirectShow/MSMF angesprochen werden. Dies führt bei mehreren Kameras oft zu USB-Bandbreitenproblemen und leichten Asynchronitäten (Frame-Drift). 
**Ziel:** Die Software soll Blackmagic Capture-Karten (insbesondere DeckLink Duo 2 mit 4x SDI) unterstützen, um unkomprimierte, hochstabile Videostreams für das FreeMoCap-Tracking zu nutzen. Langfristig soll eine Genlock-Synchronisation evaluiert und ggf. als DIY-Hardware-Lösung (Raspberry Pi Pico) umgesetzt werden.

---

## 2. Stufenplan (Phasen)

Wir gehen iterativ vor, um schnell erste Ergebnisse zu haben und unnötige Hardware-Basteleien zu vermeiden, falls die einfache Lösung bereits ausreicht.

### Phase 1: "DeckLink Free Run" (Software Capture & Integration)
In dieser Phase binden wir die DeckLink-Karte direkt in unsere bestehende Python-Software ein. Die Kameras laufen im "Free Run" (ohne Hardware-Sync). Da SDI extrem latenzarm ist und PCIe keine USB-Flaschenhälse hat, ist dies meistens bereits präzise genug für MoCap.

* **Aufgaben:**
  1. **Architektur-Update:** Erstellung einer neuen Klasse (z.B. `decklink_manager.py` oder Erweiterung von `camera_manager.py`), um die DeckLink-Inputs gezielt anzusprechen.
  2. **Treiber-Evaluation:** Testen, ob OpenCV via `cv2.CAP_DSHOW` (über den "Blackmagic WDM Capture"-Treiber) stabil läuft, oder ob wir auf ein spezialisierteres Framework (GStreamer / `pyblackmagic` / PyAV) wechseln müssen.
  3. **UI-Anpassung:** Im Setup-Tab einen Schalter ("USB" vs "Blackmagic SDI") einbauen, damit man nahtlos wechseln kann.
  4. **Recording:** Sicherstellen, dass `recorder.py` die 4 SDI-Streams fehlerfrei und ohne Framedrops auf die Festplatte schreibt.

### Phase 2: "Arduino Software-Trigger" (Präziser Aufnahme-Start)
Um sicherzustellen, dass alle aufgenommenen Videos beim exakt selben Frame starten (wichtig für FreeMoCap), nutzen wir den Arduino als präzisen Taktgeber für die Software.

* **Aufgaben:**
  1. Arduino-Skript so konfigurieren, dass es bei Knopfdruck ein Signal (`"RECORD_START"`) via Serial (COM-Port) an den PC sendet.
  2. Die Python-Software fängt dieses Signal ab und löst in der exakt gleichen Millisekunde das Schreiben der Frames auf die Festplatte für alle 4 Kameras aus.

### Phase 3: "Smart DIY Genlock" (Optionaler Hardware-Sensor-Sync)
Sollte sich nach Phase 1 und 2 herausstellen, dass bei extrem schnellen Bewegungen (z.B. Sport) der fehlende Sensor-Sync (Shutter öffnen sich nicht auf die Mikrosekunde exakt) das Tracking stört, bauen wir unsere eigene Genlock-Box.

* **Konzept:**
  * **Hardware-Herz:** Ein Raspberry Pi Pico (RP2040) generiert mithilfe seiner PIO (Programmable I/O) State Machines das exakte analoge Tri-Level-Sync Videosignal.
  * **Pegel-Anpassung (DAC):** Ein Widerstandsnetzwerk bringt das Signal auf die geforderten +300mV/0V/-300mV.
  * **Video-Verstärker (WICHTIG):** Es werden **5 separate Video-Operationsverstärker** benötigt, um das Signal sauber an die 4 Kameras und die DeckLink zu verteilen, ohne dass die 75-Ohm Impedanz zusammenbricht.
  * **Bauteile-Liste (Entwurf):**
    - 1x Raspberry Pi Pico (Microcontroller)
    - 2x THS7316 (3-Kanal Video Amplifier IC) oder 5x ADA4432-1 (Single Channel). *Alternativ: Eine kommerzielle "1x6 Video Distribution Amplifier" Box kaufen, statt selber zu löten.*
    - 5x 75-Ohm BNC Buchsen (für das Gehäuse)
    - Diverse Präzisions-Widerstände für den Spannungsteiler (DAC).
  * **Software-Integration:** Die Pico-Firmware lauscht am USB-Port. Wenn der Nutzer in unserer Python-Software die Framerate/Auflösung ändert, sendet Python einen Befehl (z.B. `SET:1080p60`) an den Pico. Der Pico passt sein Genlock-Signal in Echtzeit an die Kameras an.

---

## 3. Offene Fragen an den Nutzer
- Hast du die DeckLink Duo 2 und die Kameras aktuell schon verbaut und verkabelt, sodass wir direkt Code ausführen und testen können?
- Welche Kameras nutzt du genau (Modell)? Das hilft bei der Entscheidung, ob wir GStreamer brauchen oder OpenCV reicht.

---
*Status: Geplant - Warten auf User-Freigabe*
