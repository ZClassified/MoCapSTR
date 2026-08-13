import cv2
import time
import sys
import os
import av

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'python')))
try:
    from arduino_sync import ArduinoSync
except ImportError:
    print("FEHLER: Konnte arduino_sync.py nicht finden.")
    sys.exit(1)

def get_device_name(index=0):
    try:
        from pygrabber.dshow_graph import FilterGraph
        graph = FilterGraph()
        devices = graph.get_input_devices()
        if index < len(devices):
            return devices[index]
    except ImportError:
        print("FEHLER: 'pygrabber' ist nicht installiert, wird aber für PyAV benötigt.")
        sys.exit(1)
    return None

def test_pyav_trigger(camera_index=0, target_fps=60):
    print("\n--- Starte ultimativen PyAV + Arduino Test ---")
    
    cam_name = get_device_name(camera_index)
    if not cam_name:
        print(f"Konnte Kamera mit Index {camera_index} nicht finden.")
        return
    print(f"Verwende Kamera: {cam_name}")

    # 1. Arduino starten
    print("\n1. Suche Arduino und starte Trigger...")
    arduino = ArduinoSync()
    port = arduino.auto_detect_port()
    if port and arduino.connect(port):
        arduino.set_fps(target_fps)
        arduino.start_trigger()
        time.sleep(0.5)
    else:
        print("WARNUNG: Konnte Arduino nicht verbinden. Beende Test.")
        return

    # 2. OpenCV "Hybrid-Trick" anwenden
    print("\n2. Impfe Kamera mit Trigger- & Belichtungs-Befehlen (Hybrid-Trick)...")
    
    # DSHOW für manuelle Belichtung (sonst dropt sie wegen Auto-Exposure FPS)
    cap_dshow = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if cap_dshow.isOpened():
        cap_dshow.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        cap_dshow.set(cv2.CAP_PROP_EXPOSURE, -6)
        cap_dshow.release()
    
    # MSMF für Hardware-Trigger (Autofokus)
    cap_msmf = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)
    if cap_msmf.isOpened():
        cap_msmf.set(cv2.CAP_PROP_AUTOFOCUS, 1) # Trigger ON
        cap_msmf.set(cv2.CAP_PROP_FOCUS, 0)
        cap_msmf.release()
        
    time.sleep(0.5)

    # 3. Stream mit PyAV öffnen
    print("\n3. Öffne Videostream mit PyAV (FFmpeg)...")
    options = {
        'video_size': '1280x720',
        'framerate': '120', # Wir fordern 120 an, aber der Arduino taktet das echte Limit
        'vcodec': 'mjpeg',
        'rtbufsize': '256M'
    }
    
    try:
        container = av.open(f'video={cam_name}', format='dshow', options=options)
        stream = container.streams.video[0]
    except Exception as e:
        print("Fehler beim Öffnen mit PyAV:", e)
        arduino.stop_trigger()
        arduino.disconnect()
        return

    print(f"\nAlles läuft! Wir zählen jetzt physikalisch eintreffende USB-Pakete.")
    print("Breche den Test mit STRG+C ab (im Terminal), da PyAV kein schönes OpenCV-Fenster-Event hat.")

    frame_count = 0
    start_time = time.time()
    last_print_time = start_time

    try:
        # container.demux BLOCKIERT, bis ein echtes neues Bild vom USB Kabel kommt!
        for packet in container.demux(stream):
            if packet.size > 0:
                frame_count += 1
                
                # Wenn du das Bild sehen willst, können wir es dekodieren (Vorsicht, kostet CPU)
                # Für hohe FPS Tests reicht es oft, nur die Pakete zu zählen. Wir dekodieren hier trotzdem:
                for frame in packet.decode():
                    img = frame.to_ndarray(format='bgr24')
                    cv2.imshow("PyAV Trigger Test", img)
                    cv2.waitKey(1)
                
                current_time = time.time()
                if current_time - last_print_time >= 1.0:
                    fps = frame_count / (current_time - last_print_time)
                    print(f"  [PyAV] Echte gemessene FPS: {fps:.2f} (Ziel vom Arduino: {target_fps})")
                    frame_count = 0
                    last_print_time = current_time

    except KeyboardInterrupt:
        print("\nTest manuell abgebrochen.")
    except Exception as e:
        print(f"\nStream beendet: {e}")

    # 4. Aufräumen
    print("\nDeaktiviere Trigger und räume auf...")
    cap_msmf = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)
    if cap_msmf.isOpened():
        cap_msmf.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        cap_msmf.release()
        
    container.close()
    arduino.stop_trigger()
    arduino.disconnect()
    cv2.destroyAllWindows()
    print("Fertig!")

if __name__ == "__main__":
    # Teste mit 25 FPS
    test_pyav_trigger(camera_index=0, target_fps=25)
