import cv2
import time
import sys
import os
import av

# Robuste Pfad-Einbindung (damit das Skript von überall aus funktioniert)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'python')))
try:
    from arduino_sync import ArduinoSync
    from pygrabber.dshow_graph import FilterGraph
except ImportError as e:
    print(f"FEHLER beim Importieren: {e}")
    input("Drücke Enter zum Beenden...")
    sys.exit(1)

def test_pyav_gui(camera_index=0, target_fps=60):
    try:
        graph = FilterGraph()
        devices = graph.get_input_devices()
        
        if camera_index >= len(devices):
            print(f"FEHLER: Keine Kamera an Index {camera_index} gefunden!")
            return
            
        cam_name = devices[camera_index]
        
        print(f"\n--- Teste 60 FPS mit manueller Belichtung ---")
        print("Du hast gesagt, du hast die Belichtung in OBS eingestellt.")
        print("Stelle bitte sicher, dass OBS jetzt GANZ GESCHLOSSEN ist, damit die Kamera frei ist!")
        
        print("\nStarte jetzt den 60 FPS Test...")
        
        # Arduino starten
        arduino = ArduinoSync()
        port = arduino.auto_detect_port()
        if port and arduino.connect(port):
            arduino.set_fps(target_fps)
            arduino.start_trigger()
            time.sleep(0.5)
        else:
            print("WARNUNG: Konnte Arduino nicht verbinden. Beende Test.")
            return
            
        # MSMF für Trigger (Autofokus) - Belichtung haben wir ja grad manuell gemacht!
        cap_msmf = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)
        if cap_msmf.isOpened():
            cap_msmf.set(cv2.CAP_PROP_AUTOFOCUS, 1)
            cap_msmf.set(cv2.CAP_PROP_FOCUS, 0)
            cap_msmf.release()
            
        time.sleep(0.5)
        
        # PyAV
        options = {'video_size': '1280x720', 'framerate': '120', 'vcodec': 'mjpeg', 'rtbufsize': '256M'}
        try:
            container = av.open(f'video={cam_name}', format='dshow', options=options)
            stream = container.streams.video[0]
        except Exception as e:
            print(f"Fehler beim Öffnen mit PyAV: {e}")
            if port: arduino.stop_trigger(); arduino.disconnect()
            return
            
        print("\nPyAV läuft! Messe echte FPS... (STRG+C zum Beenden)")
        
        frame_count = 0
        start_time = time.time()
        last_print_time = start_time

        try:
            for packet in container.demux(stream):
                if packet.size > 0:
                    frame_count += 1
                    
                    # Zeige das Bild an, damit du prüfen kannst, ob es dunkel (kurze Belichtung) ist!
                    for frame in packet.decode():
                        img = frame.to_ndarray(format='bgr24')
                        cv2.imshow("PyAV Trigger Vorschau", img)
                        cv2.waitKey(1)
                    
                    current_time = time.time()
                    if current_time - last_print_time >= 1.0:
                        fps = frame_count / (current_time - last_print_time)
                        print(f"  [PyAV] Echte FPS: {fps:.2f} (Ziel: {target_fps})")
                        frame_count = 0
                        last_print_time = current_time
        except KeyboardInterrupt:
            print("\nManuell beendet.")

        # Aufräumen
        cap_msmf = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)
        if cap_msmf.isOpened():
            cap_msmf.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            cap_msmf.release()
            
        container.close()
        if port: 
            arduino.stop_trigger()
            arduino.disconnect()
            
    except Exception as e:
        print(f"\nEIN UNERWARTETER FEHLER IST AUFGETRETEN: {e}")
    finally:
        print("Test beendet.")
        input("\nDrücke Enter, um das Fenster zu schließen...")

if __name__ == "__main__":
    test_pyav_gui(0, 60)
