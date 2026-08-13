import cv2
import time

def test_msmf_trigger(camera_index=0, target_fps=120):
    print("\n--- Starte Trigger-Test mit Media Foundation (MSMF) ---")
    print("Bitte warte, Kamera wird initialisiert...")
    
    cap = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)
    if not cap.isOpened():
        print("FEHLER: Konnte Kamera nicht öffnen.")
        return

    # Formate setzen (MSMF liebt 120fps!)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, target_fps)

    # TRIGGER AKTIVIEREN
    # Laut deinem vorherigen Code wird der Trigger über Autofokus gesteuert
    print("\n>>> Aktiviere Hardware-Trigger an der Kamera... <<<")
    # Versuche Autofokus-Trick:
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 1) # Trigger ON
    cap.set(cv2.CAP_PROP_FOCUS, 0)
    
    print("\nKamera sollte jetzt auf den Arduino warten (0 FPS).")
    print("Wenn du den Arduino ansteckst, sollten die echten FPS hochgehen!")
    print("Drücke 'q' im Videofenster zum Beenden.\n")

    frame_count = 0
    start_time = time.time()
    last_print_time = start_time

    while True:
        # Timeout-Schutz: Wenn read() zu lange dauert (weil kein Trigger da ist), 
        # friert Python oft ein. Wir versuchen es trotzdem.
        ret, frame = cap.read()
        
        current_time = time.time()
        
        if ret:
            frame_count += 1
            cv2.imshow("MSMF Trigger Test", frame)
            
        if current_time - last_print_time >= 1.0:
            fps = frame_count / (current_time - last_print_time)
            if fps == 0:
                print(f"  [MSMF] Warte auf Trigger... (0 FPS)")
            else:
                print(f"  [MSMF] Reale gemessene FPS: {fps:.2f} (Kamera wird getriggert!)")
            frame_count = 0
            last_print_time = current_time

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Kamera sauber zurücksetzen (Trigger aus), damit sie beim nächsten Mal normal läuft
    print("\nDeaktiviere Trigger wieder...")
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    test_msmf_trigger()
