# Blackmagic SDI-Modus: Instandsetzung (geplant für v2.0)

Kommt erst, wenn die Basis mit USB-Kameras und Arduino-Trigger stabil läuft.

**Status (v1.5.1):** Der Modus "Blackmagic SDI" ist **aktuell nicht funktionsfähig**.
Dieses Dokument hält Ursache, getroffene Entscheidungen und den Arbeitsplan fest, damit die Instandsetzung später direkt starten kann.

---

## 1. Warum der Modus kaputt ist

- Der Modus wurde zuletzt mit dem **alten OpenCV-Backend** getestet (eine Kamera, Bild wurde erkannt). Mehrkamera-Aufnahmen wurden nie geprüft.
- Seit der Umstellung auf PyAV (Commit `ff2cb91`) öffnet `camera_manager.py` die Karte mit `av.open(name, format='decklink')`. Die PyAV-Pakete enthalten **kein `decklink`-Format** (geprüft: `'decklink' in av.formats_available` → `False`, `dshow` → `True`).
- Zusätzlich bricht `find_and_open_cameras()` im Blackmagic-Zweig mit `UnboundLocalError` ab: `device_number` wird nur im USB-Zweig gesetzt.
- Ältere Planung: `SDI_INTEGRATION_PLAN.md` in Commit `a944d9b` (inzwischen aus dem Repo entfernt).

## 2. Getroffene Entscheidungen

| Thema | Entscheidung |
|---|---|
| Anbindung | Über **DirectShow** (`format='dshow'`), wie bei den USB-Kameras. Der Desktop-Video-Treiber stellt jeden SDI-Eingang als eigenes Gerät bereit ("Decklink Video Capture", "Decklink Video Capture (2)", …). Kein DeckLink SDK, kein eigener FFmpeg-Build. |
| Aufnahmeformat | Wählbar. **Standard: unkomprimiert** (einfachster und verlustfreier Weg, braucht viel Platz). **Optional: Kodierung auf der Grafikkarte**, herstellerunabhängig: AMD (`h264_amf`/`hevc_amf`), NVIDIA (`h264_nvenc`), Intel (`h264_qsv`). Alle sind in den PyAV-Paketen enthalten. Das Tool bietet nur Encoder an, die sich auf dem PC tatsächlich öffnen lassen. |
| Genlock | **Kein Bestandteil des Tools.** Genlock ist externe Hardware zwischen den Kameras. Das Tool muss mit und ohne Genlock funktionieren. Ohne Genlock können die Belichtungen bis zu einem halben Frame auseinanderliegen. Das ist bei FreeMoCap mit Webcams genauso und funktioniert. |
| Frame-Ausrichtung | Ohne Arduino-Trigger gibt es keinen Stopp/Neustart des Takts. Start und Ende werden **nach der Aufnahme per Ankunftszeitstempel ausgerichtet** (`clip_sync`, die Zeitstempel werden seit v1.5.0 mitgeschrieben). |
| Interlaced | Muss **erkannt** werden, mit Hinweis "Kamera auf progressiv umstellen". PsF darf **nicht** als Fehler gelten (siehe 3.3). |
| Allgemeingültigkeit | Keine kameraspezifischen Annahmen. Formate werden vom Gerät gelesen bzw. gemessen. |

## 3. Technische Eckpunkte

### 3.1 Datenraten (unkomprimiert, 8 Bit 4:2:2 / UYVY = 2 Byte pro Pixel)

| Format | pro Kamera | 4 Kameras | pro Minute (4 Kameras) |
|---|---|---|---|
| 720p50 | ca. 92 MB/s | ca. 370 MB/s | ca. 22 GB |
| 1080PsF25 | ca. 104 MB/s | ca. 415 MB/s | ca. 25 GB |
| 1080p50 | ca. 207 MB/s | ca. 830 MB/s | ca. 50 GB |

- 4× 720p50 schafft eine SATA-SSD knapp, ab 1080p50 braucht es eine NVMe-SSD.
- Falls die Karte 10 Bit (v210) liefert, sind die Raten etwa ein Drittel höher.
- Vor jeder Aufnahme sollte das Tool prüfen, ob Datenrate und freier Platz zusammenpassen, und warnen.

### 3.2 Aufnahmepfad

- **Unkomprimiert:** Die Pakete von DirectShow (rawvideo) unverändert per Stream-Copy in `.avi`/`.mkv` schreiben, wie bisher bei MJPEG. Zu prüfen: Kann FreeMoCap (OpenCV) rawvideo-AVI in dieser Größe flüssig lesen? Bei AVI gibt es eine 4-GB-Grenze pro Datei → für unkomprimiert vermutlich **MKV**.
- **GPU-Kodierung:** Frames dekodieren und mit dem Hardware-Encoder der Grafikkarte kodieren, pro Kamera ein eigener Thread.
  - Verfügbare Encoder beim Start ermitteln: Testweise öffnen und ein paar Frames kodieren. Nur was funktioniert, erscheint in der Auswahl.
  - **DeckLink-PC: AMD Radeon RX 5700 XT** (VCN 2.0) → `h264_amf` oder `hevc_amf`. Kein AV1-Encoder, kein NVENC.
  - Zu prüfen: Schafft der Encoder die Summe aller Kameras in Echtzeit (z. B. 4× 720p50 = 200 Bilder/s, 4× 1080p50 = 200 Bilder/s in Full HD)? Wie viele Encoder-Sitzungen laufen gleichzeitig stabil (bei NVIDIA-GeForce je nach Generation 3 bis 8), und wie hoch ist die Latenz?
  - Falls die GPU nicht reicht: Warnung vor der Aufnahme bzw. Rückfall auf unkomprimiert.
- Die vorhandene Logik bleibt nutzbar: Aufnahme-Sessions, das Auffüllen verlorener Frames und die Zeitstempel-CSV im FreeMoCap-Format.

### 3.3 Interlaced vs. PsF vs. progressiv

- **Echtes Interlaced (1080i):** Die beiden Halbbilder stammen aus verschiedenen Zeitpunkten, bei Bewegung entsteht Kammartefakt. Für Mocap ungeeignet → **Warnung**.
- **PsF (z. B. 1080PsF25):** Der Bildinhalt ist progressiv, wird aber als zwei Halbbilder übertragen. Die Karte meldet das Signal oft als "interlaced" (z. B. 1080i50). Setzt man die Halbbilder wieder zusammen, entsteht ein sauberes progressives 25p-Bild → **kein Fehler**, nur der Hinweis "PsF erkannt, Bildrate 25".
- **Erkennung, zweistufig:**
  1. **Signal:** Prüfen, ob DirectShow bzw. das Format Halbbilder meldet (Feldreihenfolge/Interlace-Flags im Medientyp, `codec_context.field_order`).
  2. **Bildinhalt:** Den FFmpeg-Filter `idet` (über einen PyAV-Filtergraph) auf einige Sekunden Vorschau anwenden. Er zählt, ob die Frames Kammartefakte haben. Interlaced-Signal mit progressivem Inhalt → PsF (ok). Interlaced-Inhalt → Warnung "auf progressiv umstellen".
- Zu prüfen: Was meldet der Treiber bei PsF genau, und funktioniert `idet` mit Testbildern bzw. bei wenig Bewegung zuverlässig? Die Warnung soll erst nach genug Frames mit Bewegung kommen, um Fehlalarme zu vermeiden.

### 3.4 Synchronität ohne Trigger

- **Mit Genlock:** Die Frames aller Kameras kommen innerhalb weniger Millisekunden an. Die Ausrichtung per Ankunftszeit ist eindeutig, Frame N ist auf allen Kameras derselbe Moment.
- **Ohne Genlock:** Der Versatz zwischen den Kameras liegt bei bis zu ±½ Frame und wandert langsam. Die Ausrichtung nimmt pro Kamera den zeitlich nächstliegenden Frame. Die Clips sind dann gleich lang und höchstens ½ Frame versetzt. Das Tool sollte den gemessenen Versatz anzeigen (Info, kein Fehler).
- Gerätezeitstempel (`device_time_s`) zur Erkennung verlorener Frames: Prüfen, ob der DeckLink-Treiber sinnvolle Zeitstempel liefert.

### 3.5 Hardware-Hinweise

- **DeckLink-PC (Testsystem):** DeckLink Duo 2, AMD Radeon RX 5700 XT, SSD. Python, IDE werden dort eingerichtet, sodass direkt am Gerät getestet und nachgebessert werden kann.
- **DeckLink Duo 2:** 4 SDI-Anschlüsse, einzeln als Ein- oder Ausgang konfigurierbar (in "Blackmagic Desktop Video Setup"), Eingänge bis **1080p60 (3G-SDI), kein UHD**.
- **Panasonic AG-HPX500 / AW-HE870** (vorhanden): liefern 1080PsF25 oder 720p50. **Für Mocap 720p50 empfehlen** (doppelte zeitliche Auflösung, PsF25 ist für schnelle Bewegungen grob).
- **Blackmagic 12K / ARRI Alexa etc:** Den SDI-Ausgang an der Kamera auf **1080p** (progressiv) stellen, da die Duo 2 kein UHD/12G-SDI annimmt. Beide haben Genlock.
- Das Eingangsformat muss zum Signal passen. Zu prüfen: Erkennt der Treiber das Format automatisch, oder muss das Tool es vorgeben?

## 4. Arbeitsplan

1. **Diagnose am DeckLink-PC.** Ein eigenständiges Skript (`tests_hardware/decklink_probe.py`) macht Folgendes und schreibt alles in eine Berichtsdatei:
   - SDI-Geräte und angebotene Formate auflisten (Auflösung, Rate, Pixelformat, Interlace-Flags).
   - Mit 1, 2 und 4 Eingängen gleichzeitig je ein paar Sekunden aufnehmen.
   - Messen: FPS, verlorene Frames, Ankunftsversatz zwischen den Eingängen, Datenrate, Gerätezeitstempel.
   - `idet` auf jedem Eingang laufen lassen.
   - Testen, welche GPU-Encoder sich öffnen lassen (AMF/NVENC/QSV) und wie schnell sie mit 1 bis 4 gleichzeitigen Streams kodieren, zum Vergleich auch MJPEG auf der CPU.
   - Schreibgeschwindigkeit der Ziel-SSD messen.
   - Version des Desktop-Video-Treibers mit in den Bericht schreiben.
2. **Umbau** auf Basis der Messwerte:
   - Blackmagic-Zweig in `camera_manager.py` auf DirectShow umstellen, `device_number` fixen.
   - Formatwahl aus den Gerätedaten statt fester Liste.
   - Aufnahmeoption "Unkomprimiert / GPU-Kodierung (AMF, NVENC, QSV – je nach PC)" im Setup-Tab.
   - Interlace/PsF-Erkennung mit Hinweis in der Vorschau.
   - Ausrichtung per Zeitstempel in `clip_sync` (Modus ohne Trigger) und Prüfung von Datenrate und Speicherplatz vor der Aufnahme.
   - Tests mit simulierten Daten wie bei den USB-Kameras.
3. **Test am DeckLink-PC** schrittweise mit 1, 2 und 4 Kameras, mit und ohne Genlock, mit 720p50 und PsF25. Danach Import in FreeMoCap 2 (gleiche Frame-Zahl, erkannte Bildrate).
