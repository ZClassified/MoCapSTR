import cv2
import time
import sys
import os
import av

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'python')))
try:
    from arduino_sync import ArduinoSync
except ImportError as e:
    print(f"FEHLER beim Importieren: {e}")
    sys.exit(1)

def test_trigger_sweep(camera_index=0):
    print("\n--- Starte Trigger-Sweep-Test ---")
    
    arduino = ArduinoSync()
    port = arduino.auto_detect_port()
    if port and arduino.connect(port):
        print("Arduino verbunden.")
        # WICHTIG: Starte den Arduino SOFORT blind mit 30 FPS.
        # Wenn die Kamera von einem alten Test noch im Trigger-Modus steckt,
        # friert cv2.VideoCapture() sonst unendlich ein, weil es beim Öffnen auf ein Bild wartet!
        arduino.set_fps(30)
        arduino.start_trigger()
        time.sleep(1.0)
    else:
        print("WARNUNG: Konnte Arduino nicht verbinden.")
        return

    # Trigger kurz aktivieren (Hybrid-Trick)
    cap_msmf = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)
    if cap_msmf.isOpened():
        cap_msmf.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        cap_msmf.set(cv2.CAP_PROP_FOCUS, 0)
        cap_msmf.release()
        
    time.sleep(0.5)

    options = {'video_size': '640x400', 'framerate': '120', 'vcodec': 'mjpeg', 'rtbufsize': '256M'}
    try:
        container = av.open(f'video=USB Camera', format='dshow', options=options)
        stream = container.streams.video[0]
    except Exception as e:
        print(f"Fehler beim Öffnen mit PyAV: {e}")
        arduino.stop_trigger()
        arduino.disconnect()
        return

    test_rates = [40, 50, 60, 90, 120]
    results = {}

    print("\nBeginne Messreihe (jedes Target läuft für ~3 Sekunden). Bitte warten...\n")

    try:
        for target_fps in test_rates:
            print(f">>> Teste Arduino mit {target_fps} FPS (Pulsweite: 500µs)...")
            arduino.set_fps(target_fps)
            arduino.start_trigger() # FEHLTE IM LETZTEN SKRIPT!
            
            # 1. Puffer-Flush: Lese alte Bilder aus dem PyAV-Puffer weg, die sich noch aufgestaut haben
            print("    Leere alten Puffer und lasse Framerate einpegeln...")
            flush_start = time.time()
            while time.time() - flush_start < 2.0:
                # Wir lesen einfach blind, um die alten Bilder loszuwerden
                for packet in container.demux(stream):
                    break
            
            # 2. Die eigentliche Messung starten
            print("    Messe jetzt für 5 Sekunden...")
            frame_count = 0
            start_time = time.time()
            
            # Sammle Frames für exakt 5 Sekunden
            while time.time() - start_time < 5.0:
                for packet in container.demux(stream):
                    if packet.size > 0:
                        frame_count += 1
                    # Kurz abbrechen, wenn 5 Sekunden um sind
                    if time.time() - start_time >= 5.0:
                        break
            
            measured_fps = frame_count / 5.0
            print(f"    Resultat für {target_fps} Ziel-FPS -> Gemessen: {measured_fps:.2f} FPS")
            results[target_fps] = measured_fps
            arduino.stop_trigger()

    except KeyboardInterrupt:
        print("Manuell abgebrochen.")

    print("\n--- ZUSAMMENFASSUNG ---")
    for t, m in results.items():
        print(f"Ziel: {t:3d} FPS | Gemessen: {m:.2f} FPS")

    # Aufräumen
    cap_msmf = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)
    if cap_msmf.isOpened():
        cap_msmf.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        cap_msmf.release()
        
    container.close()
    arduino.disconnect()
    
    print("\nTest abgeschlossen.")
    input("Drücke ENTER, um dieses Fenster zu schließen...")

if __name__ == "__main__":
    test_trigger_sweep(0)
