import cv2
import time
import sys
import os

# Füge den python-Ordner zum Pfad hinzu, damit wir ArduinoSync importieren können
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'python')))
try:
    from arduino_sync import ArduinoSync
except ImportError:
    print("FEHLER: Konnte arduino_sync.py nicht finden. Stelle sicher, dass du das Skript aus dem MoCapSTR Ordner ausführst.")
    sys.exit(1)

def test_full_trigger_chain(camera_index=0, target_fps=60):
    print("\n--- Starte VOLLSTÄNDIGEN Trigger-Test (Arduino + MSMF) ---")
    
    # 1. ARDUINO INITIALISIEREN
    print("\n1. Suche Arduino...")
    arduino = ArduinoSync()
    port = arduino.auto_detect_port()
    
    if not port:
        print("FEHLER: Kein Arduino gefunden! Ist er eingesteckt?")
        return
        
    print(f"Arduino gefunden an Port: {port}. Verbinde...")
    if not arduino.connect(port):
        print("FEHLER: Konnte nicht mit Arduino verbinden.")
        return
        
    print(f"Arduino verbunden! Setze auf {target_fps} FPS und starte Trigger-Signal...")
    arduino.set_fps(target_fps)
    arduino.start_trigger()
    time.sleep(1) # Kurz warten, damit das Signal stabil läuft
    
    # 2. KAMERA INITIALISIEREN (MSMF)
    print("\n2. Öffne Kamera mit MSMF...")
    cap = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)
    if not cap.isOpened():
        print("FEHLER: Konnte Kamera nicht öffnen.")
        arduino.stop_trigger()
        arduino.disconnect()
        return

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 120) # Wir fordern 120 an, aber der Arduino taktet

    print("\n3. Aktiviere Hardware-Trigger-Modus an der Kamera...")
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 1) # Trigger ON
    cap.set(cv2.CAP_PROP_FOCUS, 0)
    
    print(f"\nAlles läuft! Die Kamera sollte nun EXAKT mit {target_fps} FPS vom Arduino getriggert werden.")
    print("Messe reale FPS... (Drücke 'q' im Videofenster zum Beenden)")

    frame_count = 0
    start_time = time.time()
    last_print_time = start_time

    while True:
        ret, frame = cap.read()
        current_time = time.time()
        
        if ret:
            frame_count += 1
            cv2.imshow("MSMF Trigger + Arduino", frame)
            
        if current_time - last_print_time >= 1.0:
            fps = frame_count / (current_time - last_print_time)
            print(f"  Gemessene FPS: {fps:.2f} (Ziel vom Arduino: {target_fps})")
            frame_count = 0
            last_print_time = current_time

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Aufräumen
    print("\nBeende Test und räume auf...")
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0) # Trigger wieder aus
    cap.release()
    cv2.destroyAllWindows()
    
    arduino.stop_trigger()
    arduino.disconnect()
    print("Fertig!")

if __name__ == "__main__":
    test_full_trigger_chain(camera_index=0, target_fps=25)
