"""
MoCapSTR - Hardware Trigger Diagnostic Tool
===========================================
Tests whether connected InnoMaker OV9281 cameras physically receive and respond
to hardware synchronization pulses from the Arduino trigger pin (Pin 2 / FSIN).

Usage:
    python arduino/test_camera_trigger.py
    (or double-click run_camera_trigger_test.bat)
"""

import sys
import os
import time
import threading
import cv2

# Set stdout encoding to utf-8 if possible
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add python directory to path
sys.path.append(os.path.abspath('python'))
from arduino_sync import ArduinoSync
from pygrabber.dshow_graph import FilterGraph

def print_header(title):
    print("\n" + "=" * 62)
    print(f" {title}")
    print("=" * 62, flush=True)

def find_cameras():
    try:
        g = FilterGraph()
        devices = g.get_input_devices()
        valid = []
        for idx, name in enumerate(devices):
            if "virtual" in name.lower() or "obs" in name.lower():
                continue
            valid.append((idx, name))
        return valid
    except Exception as e:
        print(f"Fehler bei Kamera-Erkennung: {e}")
        return [(0, "Standard Kamera")]

def read_frame_timeout(cap, timeout_sec=0.3):
    """Reads a single frame with strict timeout to prevent blocking when 0 pulses arrive."""
    res = [False, None]
    def _grab():
        try:
            r, f = cap.read()
            res[0] = r
            res[1] = f
        except Exception:
            pass
    t = threading.Thread(target=_grab, daemon=True)
    t.start()
    t.join(timeout=timeout_sec)
    return res[0], res[1]

def count_frames_over_duration(cap, duration_sec=2.5, warmup_sec=0.8):
    """
    Counts frames after a brief warm-up / stabilization period to ensure
    accurate steady-state FPS measurement.
    """
    # 1. Warm-up / Einschwingphase (USB Puffer synchronisieren)
    if warmup_sec > 0:
        warmup_end = time.time() + warmup_sec
        while time.time() < warmup_end:
            read_frame_timeout(cap, timeout_sec=0.15)
            
    # 2. Steady-State Messung
    start_time = time.time()
    frames_count = 0
    while time.time() - start_time < duration_sec:
        ret, frame = read_frame_timeout(cap, timeout_sec=0.25)
        if ret and frame is not None:
            frames_count += 1
            
    elapsed = max(time.time() - start_time, 0.001)
    fps = frames_count / elapsed
    return frames_count, fps, elapsed

def interactive_live_mode(cap, ard, cam_idx):
    """Interactive OpenCV window with real-time FPS overlay and Arduino frequency switching."""
    print_header("INTERAKTIVER LIVE-MONITOR GESTARTET")
    print(" Tastaturbefehle im Kamera-Fenster:")
    print("   [1] -> 10 FPS      [2] -> 25 FPS      [3] -> 30 FPS")
    print("   [4] -> 50 FPS      [5] -> 60 FPS      [0] -> Free-Run")
    print("   [LEERTASTE] -> Trigger Pausieren / Starten")
    print("   [ESC / Q]   -> Beenden & Zurueck zum Menue")
    print("=" * 62, flush=True)
    
    current_fps_setting = 25
    is_trigger_mode = True
    
    ard.set_fps(current_fps_setting)
    ard.start_trigger()
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
    
    frame_counter = 0
    last_fps_time = time.time()
    live_fps = 0.0
    
    win_name = f"MoCapSTR Trigger Live Monitor (Kamera {cam_idx}) - [ESC zum Beenden]"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 960, 540)
    
    while True:
        ret, frame = read_frame_timeout(cap, timeout_sec=0.2)
        now = time.time()
        
        if ret and frame is not None:
            frame_counter += 1
            
        if now - last_fps_time >= 1.0:
            live_fps = frame_counter / (now - last_fps_time)
            frame_counter = 0
            last_fps_time = now
            
        # Wenn kein Bild eintreffen sollte (0 FPS), schwarzes Infobild anzeigen
        if not ret or frame is None:
            display_img = 20 * (cv2.UMat(360, 640, cv2.CV_8UC3).get() if hasattr(cv2, 'UMat') else None)
            if display_img is None:
                import numpy as np
                display_img = np.zeros((360, 640, 3), dtype='uint8')
            msg = "WARTE AUF TRIGGER-PULSE (0 FPS)..."
            cv2.putText(display_img, msg, (40, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            display_img = frame.copy()
            if len(display_img.shape) == 2:
                display_img = cv2.cvtColor(display_img, cv2.COLOR_GRAY2BGR)
                
            # Status Text overlay
            mode_str = f"TRIGGER: {current_fps_setting} FPS" if is_trigger_mode else "FREE-RUN"
            diff = abs(live_fps - current_fps_setting) if is_trigger_mode else 0
            color = (0, 255, 0) if diff <= 1.5 else (0, 0, 255)
            
            overlay_text = f"Live: {live_fps:.1f} FPS  |  Soll: {mode_str}"
            cv2.putText(display_img, overlay_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.putText(display_img, "Tasten: 1=10p | 2=25p | 3=30p | 4=50p | 5=60p | 0=Free-Run | ESC=Ende", 
                        (20, display_img.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
        cv2.imshow(win_name, display_img)
        key = cv2.waitKey(1) & 0xFF
        
        if key == 27 or key == ord('q'): # ESC / Q
            break
        elif key == ord('1'):
            current_fps_setting = 10
            is_trigger_mode = True
            ard.set_fps(10)
            ard.start_trigger()
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        elif key == ord('2'):
            current_fps_setting = 25
            is_trigger_mode = True
            ard.set_fps(25)
            ard.start_trigger()
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        elif key == ord('3'):
            current_fps_setting = 30
            is_trigger_mode = True
            ard.set_fps(30)
            ard.start_trigger()
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        elif key == ord('4'):
            current_fps_setting = 50
            is_trigger_mode = True
            ard.set_fps(50)
            ard.start_trigger()
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        elif key == ord('5'):
            current_fps_setting = 60
            is_trigger_mode = True
            ard.set_fps(60)
            ard.start_trigger()
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        elif key == ord('0'):
            is_trigger_mode = False
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        elif key == 32: # Space
            if ard.is_running:
                ard.stop_trigger()
            else:
                ard.start_trigger()
                
    cv2.destroyAllWindows()

def test_camera_trigger():
    print_header("MoCapSTR: Hardware-Trigger Diagnose-Tool")
    
    # 1. Kameras erkennen
    cameras = find_cameras()
    if not cameras:
        print("[!] Keine physischen Kameras gefunden! Bitte USB-Kabel pruefen.")
        return
        
    print(f"[+] Gefundene Kameras ({len(cameras)}):")
    for idx, name in cameras:
        print(f"    [{idx}] {name}")
        
    # 2. Arduino verbinden
    ard = ArduinoSync()
    port = ard.auto_detect_port()
    if not port:
        avail = ArduinoSync.get_available_ports()
        if avail:
            port = avail[0]
            
    if not port:
        print("\n[!] Kein Arduino COM-Port gefunden! Bitte USB-Kabel der Trigger-Box pruefen.")
        return
        
    print(f"\n[*] Verbinde mit Arduino an {port}...")
    if not ard.connect(port):
        print(f"[!] Verbindung zu Arduino an {port} fehlgeschlagen.")
        return
    print(f"[OK] Arduino erfolgreich verbunden auf {port}!")
    
    # Vor Beginn: Free-Run sicherstellen
    print("\n[*] Initialisiere Kameras im sicheren Free-Run Modus...")
    for idx, _ in cameras:
        try:
            cap_init = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap_init.isOpened():
                cap_init.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                cap_init.release()
        except Exception:
            pass
    time.sleep(0.5)
    
    # 3. Teste jede gefundene Kamera
    for cam_idx, cam_name in cameras:
        print_header(f"TESTE KAMERA [{cam_idx}]: {cam_name}")
        
        cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print(f"[!] Kamera {cam_idx} konnte nicht geoeffnet werden.")
            continue
            
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 0) # Free-Run
        
        # --- TEST 1: Free-Run Modus ---
        print("\n[1/4] Teste Free-Run Modus (Interner Oszillator, AutoFocus=0)...")
        frames_free, fps_free, _ = count_frames_over_duration(cap, duration_sec=1.5, warmup_sec=0.5)
        print(f"      -> Gemessen: {fps_free:.1f} FPS ({frames_free} Frames) [OK]")
        
        # --- TEST 2: Trigger-Ruhetest (Arduino AUS) ---
        print("\n[2/4] Schalte Kamera in Trigger-Modus (AutoFocus=1) bei pausiertem Arduino...")
        ard.stop_trigger()
        time.sleep(0.2)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        cap.set(cv2.CAP_PROP_FOCUS, 0)
        
        frames_silence, _, _ = count_frames_over_duration(cap, duration_sec=1.0, warmup_sec=0.3)
        print(f"      -> Frames ohne Trigger-Pulse: {frames_silence} Frames")
        if frames_silence == 0:
            print("      -> Sensor wartet vorschriftsmaessig auf elektrische Impulse. [OK]")
        else:
            print("      -> Hinweis: Kamera sendet Restpuffer.")
            
        # --- TEST 3: 10 FPS Trigger Puls-Test ---
        print("\n[3/4] Starte Arduino Trigger mit 10 FPS (10 Pulse/Sekunde)...")
        ard.set_fps(10)
        ard.start_trigger()
        
        # Einschwingphase: 0.8s warm-up, danach 2.5s genaue Messung
        frames_10, fps_10, _ = count_frames_over_duration(cap, duration_sec=2.5, warmup_sec=0.8)
        print(f"      -> Soll: 10.0 FPS  |  Gemessen: {fps_10:.1f} FPS ({frames_10} Frames) [OK]")
        
        # --- TEST 4: 25 FPS Trigger Puls-Test ---
        print("\n[4/4] Aendere Arduino Trigger auf 25 FPS (25 Pulse/Sekunde)...")
        ard.set_fps(25)
        
        # Einschwingphase: 0.8s warm-up, danach 2.5s genaue Messung
        frames_25, fps_25, _ = count_frames_over_duration(cap, duration_sec=2.5, warmup_sec=0.8)
        print(f"      -> Soll: 25.0 FPS  |  Gemessen: {fps_25:.1f} FPS ({frames_25} Frames) [OK]")
        
        # --- DIAGNOSE-AUSWERTUNG ---
        print("\n" + "-" * 56)
        print(f" DIAGNOSE-ERGEBNIS FUER KAMERA [{cam_idx}]:")
        print("-" * 56)
        
        diff_10 = abs(fps_10 - 10.0)
        diff_25 = abs(fps_25 - 25.0)
        
        success = False
        if diff_10 <= 2.0 and diff_25 <= 2.5 and frames_25 >= 40:
            success = True
            print(" [+++] ERFOLG: Das Hardware-Trigger-Signal kommt PERFEKT an!")
            print(f"       Die Kamera synchronisiert exakt mit den Arduino-Takten:")
            print(f"       - Bei 10 FPS Soll: {fps_10:.1f} FPS gemessen")
            print(f"       - Bei 25 FPS Soll: {fps_25:.1f} FPS gemessen")
        elif fps_10 < 1.0 and fps_25 < 1.0:
            print(" [---] KEIN TRIGGER-SIGNAL: Der Arduino sendet Pulse, aber an")
            print("       der Kamera kommen 0 Frames an (Sensor wartet vergeblich).")
            print("\n       Bitte pruefen Sie folgende Hardware-Verbindungen:")
            print("       1. 2-Pol-Stecker fest an der Rueckseite der Kamera?")
            print("       2. Polaritaet:")
            print("          - FSIN (+)  -> Arduino Pin 2")
            print("          - FSIN (-)  -> Arduino GND")
            print("       3. XLR-Kabel / Splitter-Box eingesteckt und Massekontakt intakt?")
        elif fps_10 > 25.0 and fps_25 > 25.0:
            print(" [WARN] KAMERA LAEUFT WEITER IM FREE-RUN:")
            print("       Die Kamera ignoriert den Trigger und sendet mit internem Takt.")
        else:
            print(f" [WARN] UNREGELMAESSIG: Gemessen: {fps_10:.1f} FPS (10 Hz) / {fps_25:.1f} FPS (25 Hz).")
            print("       Pruefen Sie die Leitungen auf Wackelkontakt oder Signalstoerungen.")
        print("-" * 56)
        
        # Option fuer interaktiven Live-Monitor
        if success:
            print("\n[?] Moechten Sie einen interaktiven Live-Monitor oeffnen,")
            print("    um Taktraten live per Tastatur durchzuschalten? [J/N]: ", end="", flush=True)
            try:
                # Schnelle Eingabe mit 5s Timeout oder Direktabfrage
                choice = input().strip().lower()
                if choice in ['j', 'y', 'ja', 'yes']:
                    interactive_live_mode(cap, ard, cam_idx)
            except Exception:
                pass
                
        # Reset Kamera auf Free-Run
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        cap.release()
        
    # Arduino stoppen und trennen
    ard.stop_trigger()
    ard.disconnect()
    print("\n[OK] Diagnose abgeschlossen. Kameras wurden sauber auf Free-Run zurueckgesetzt.\n")

if __name__ == '__main__':
    try:
        test_camera_trigger()
    except Exception as e:
        print(f"\n[FEHLER] Unerwarteter Fehler: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n" + "=" * 62)
        try:
            input("Druecken Sie [ENTER], um das Fenster zu schliessen...")
        except Exception:
            pass
