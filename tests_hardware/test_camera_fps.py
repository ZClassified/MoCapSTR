import cv2
import time

def test_camera(backend_name, backend_flag, camera_index=0, target_fps=120):
    print(f"\n--- Starte Test für Treiber: {backend_name} ---")
    
    cap = cv2.VideoCapture(camera_index, backend_flag)
    
    if not cap.isOpened():
        print(f"FEHLER: Konnte Kamera {camera_index} mit {backend_name} nicht öffnen.")
        return

    # WICHTIG: Erst das Format setzen, DANN die Auflösung
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, target_fps)

    # --- BELICHTUNG MANUELL FIXIEREN ---
    # Auto-Exposure ausschalten (Wert 0.25 oder 1 bedeutet meist manuell, je nach Treiber)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25) 
    # Belichtungszeit sehr kurz einstellen (-6 bedeutet meist 2^-6 Sekunden, also ca 1/64s)
    cap.set(cv2.CAP_PROP_EXPOSURE, -6)

    actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    actual_fps_prop = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Einstellungen gemeldet von der Kamera:")
    print(f"  Auflösung: {actual_w} x {actual_h}")
    print(f"  Gemeldete FPS: {actual_fps_prop}")
    print("  Messe reale FPS... (Bitte warten, drücke 'q' im Videofenster zum Beenden)")

    frame_count = 0
    start_time = time.time()
    last_print_time = start_time

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Fehler beim Lesen des Frames!")
            break
            
        frame_count += 1
        current_time = time.time()
        
        if current_time - last_print_time >= 1.0:
            fps = frame_count / (current_time - last_print_time)
            print(f"  [{backend_name}] Reale gemessene FPS: {fps:.2f}")
            frame_count = 0
            last_print_time = current_time

        cv2.imshow(f"Test Window - {backend_name}", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"--- Test für {backend_name} beendet ---\n")

if __name__ == "__main__":
    camera_id = 0
    target = 120
    
    print("Test 1: DirectShow (DSHOW)")
    test_camera("DirectShow", cv2.CAP_DSHOW, camera_index=camera_id, target_fps=target)
    
    print("Test 2: Media Foundation (MSMF)")
    test_camera("Media Foundation", cv2.CAP_MSMF, camera_index=camera_id, target_fps=target)
