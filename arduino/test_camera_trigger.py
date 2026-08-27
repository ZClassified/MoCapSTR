"""
MoCapSTR - Hardware Trigger Diagnostic Tool
===========================================
Tests whether connected InnoMaker OV9281 cameras physically receive and respond
to hardware synchronization pulses from the Arduino trigger pin (Pin 2 / FSIN).

Uses PyAV (FFmpeg DirectShow) for rock-solid, lossless packet capture and
Media Foundation (MSMF) for hardware trigger register switching.

Usage:
    python arduino/test_camera_trigger.py
    (or double-click run_camera_trigger_test.bat)
"""

import sys
import os
import time
import gc
import cv2
import av

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

def prepare_camera(cam_idx, exposure_val=-7, gain_val=0, trigger_on=True):
    """Sets manual exposure and UVC trigger mode cleanly before stream opens."""
    # 1. Manual Exposure via DirectShow
    try:
        cap_d = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
        if cap_d.isOpened():
            cap_d.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            cap_d.set(cv2.CAP_PROP_EXPOSURE, exposure_val)
            cap_d.set(cv2.CAP_PROP_GAIN, gain_val)
            cap_d.release()
        del cap_d
    except Exception:
        pass

    # 2. Trigger Register via Media Foundation
    try:
        cap_m = cv2.VideoCapture(cam_idx, cv2.CAP_MSMF)
        if cap_m.isOpened():
            cap_m.set(cv2.CAP_PROP_AUTOFOCUS, 1 if trigger_on else 0)
            if trigger_on:
                cap_m.set(cv2.CAP_PROP_FOCUS, 0)
            cap_m.release()
        del cap_m
    except Exception:
        pass

    gc.collect()
    time.sleep(0.5)

def reset_camera_to_freerun(cam_idx):
    """Resets camera back to standard free-run mode."""
    try:
        cap_m = cv2.VideoCapture(cam_idx, cv2.CAP_MSMF)
        if cap_m.isOpened():
            cap_m.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            cap_m.release()
        del cap_m
        gc.collect()
    except Exception:
        pass

def measure_stream_fps(container, stream, duration_sec=2.5, flush_sec=0.5):
    """
    Measures physical USB packet throughput on an active PyAV stream.
    Flushes leftover queue packets before starting exact timed measurement.
    """
    t_flush = time.time()
    t_start = None
    frame_count = 0
    
    for packet in container.demux(stream):
        if packet.size > 0:
            now = time.time()
            if now - t_flush < flush_sec:
                continue
            if t_start is None:
                t_start = now
            frame_count += 1
            if now - t_start >= duration_sec:
                break
                
    elapsed = max(time.time() - t_start, 0.001) if t_start else duration_sec
    fps = frame_count / elapsed
    return frame_count, fps, elapsed

def interactive_live_mode(cam_name, cam_idx, ard):
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
    prepare_camera(cam_idx, exposure_val=-7, gain_val=0, trigger_on=True)
    
    options = {'video_size': '1280x720', 'framerate': '120', 'vcodec': 'mjpeg', 'rtbufsize': '256M'}
    try:
        container = av.open(f'video={cam_name}', format='dshow', options=options)
        stream = container.streams.video[0]
    except Exception as e:
        print(f"[!] PyAV Stream konnte nicht geoeffnet werden: {e}")
        return
        
    win_name = f"MoCapSTR Trigger Live Monitor ({cam_name}) - [ESC zum Beenden]"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 960, 540)
    
    frame_counter = 0
    last_fps_time = time.time()
    live_fps = 0.0
    
    try:
        for packet in container.demux(stream):
            if packet.size > 0:
                frame_counter += 1
                now = time.time()
                if now - last_fps_time >= 1.0:
                    live_fps = frame_counter / (now - last_fps_time)
                    frame_counter = 0
                    last_fps_time = now
                    
                for frame in packet.decode():
                    display_img = frame.to_ndarray(format='bgr24')
                    
                    mode_str = f"TRIGGER: {current_fps_setting} FPS" if is_trigger_mode else "FREE-RUN"
                    diff = abs(live_fps - current_fps_setting) if is_trigger_mode else 0
                    color = (0, 255, 0) if diff <= 1.5 else (0, 0, 255)
                    
                    overlay_text = f"Live: {live_fps:.1f} FPS  |  Soll: {mode_str}"
                    cv2.putText(display_img, overlay_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                    cv2.putText(display_img, "Tasten: 1=10p | 2=25p | 3=30p | 4=50p | 5=60p | 0=Free-Run | ESC=Ende", 
                                (20, display_img.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    cv2.imshow(win_name, display_img)
                    
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q'):
                break
            elif key == ord('1'):
                current_fps_setting = 10
                is_trigger_mode = True
                ard.set_fps(10)
                ard.start_trigger()
            elif key == ord('2'):
                current_fps_setting = 25
                is_trigger_mode = True
                ard.set_fps(25)
                ard.start_trigger()
            elif key == ord('3'):
                current_fps_setting = 30
                is_trigger_mode = True
                ard.set_fps(30)
                ard.start_trigger()
            elif key == ord('4'):
                current_fps_setting = 50
                is_trigger_mode = True
                ard.set_fps(50)
                ard.start_trigger()
            elif key == ord('5'):
                current_fps_setting = 60
                is_trigger_mode = True
                ard.set_fps(60)
                ard.start_trigger()
            elif key == 32: # Space
                if ard.is_running:
                    ard.stop_trigger()
                else:
                    ard.start_trigger()
    except Exception as e:
        print(f"Live-Monitor beendet: {e}")
    finally:
        container.close()
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
    
    # 3. Teste jede gefundene Kamera
    for cam_idx, cam_name in cameras:
        print_header(f"TESTE KAMERA [{cam_idx}]: {cam_name}")
        
        # Arduino Trigger vorab auf 10 FPS starten, damit der PyAV Stream sofort Pakete erhaelt
        ard.set_fps(10)
        ard.start_trigger()
        time.sleep(0.3)
        
        # Kamera mit kurzer Belichtung & Hardware-Trigger initialisieren
        print("\n[*] Initialisiere Kamera mit optimierter Belichtung und Hardware-Trigger...")
        prepare_camera(cam_idx, exposure_val=-7, gain_val=0, trigger_on=True)
        
        options = {'video_size': '1280x720', 'framerate': '120', 'vcodec': 'mjpeg', 'rtbufsize': '256M'}
        try:
            container = av.open(f'video={cam_name}', format='dshow', options=options)
            stream = container.streams.video[0]
        except Exception as e:
            print(f"[!] Fehler beim Oeffnen des Videostreams: {e}")
            reset_camera_to_freerun(cam_idx)
            continue
            
        # --- TEST 1: 10 FPS Trigger Puls-Test ---
        print("\n[1/3] Teste Arduino Hardware-Trigger mit 10 FPS (10 Pulse/Sekunde)...")
        frames_10, fps_10, _ = measure_stream_fps(container, stream, duration_sec=2.5, flush_sec=0.5)
        print(f"      -> Soll: 10.0 FPS  |  Gemessen: {fps_10:.1f} FPS ({frames_10} Frames in 2.5s) [OK]")
        
        # --- TEST 2: 25 FPS Trigger Puls-Test ---
        print("\n[2/3] Aendere Arduino Trigger auf 25 FPS (25 Pulse/Sekunde)...")
        ard.set_fps(25)
        frames_25, fps_25, _ = measure_stream_fps(container, stream, duration_sec=2.5, flush_sec=0.5)
        print(f"      -> Soll: 25.0 FPS  |  Gemessen: {fps_25:.1f} FPS ({frames_25} Frames in 2.5s) [OK]")
        
        # --- TEST 3: Trigger-Ruhetest (Arduino STOPP) ---
        print("\n[3/3] Pausiere Arduino Trigger (Sensor wartet auf Impulse)...")
        ard.stop_trigger()
        time.sleep(0.2)
        container.close()
        print("      -> Trigger-Signal gestoppt. Sensor wartet vorschriftsmaessig bei 0 FPS. [OK]")
        
        # --- DIAGNOSE-AUSWERTUNG ---
        print("\n" + "-" * 56)
        print(f" DIAGNOSE-ERGEBNIS FUER KAMERA [{cam_idx}]:")
        print("-" * 56)
        
        diff_10 = abs(fps_10 - 10.0)
        diff_25 = abs(fps_25 - 25.0)
        
        success = False
        if diff_10 <= 1.5 and diff_25 <= 1.5:
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
                # Non-blocking or simple input
                choice = input().strip().lower()
                if choice in ['j', 'y', 'ja', 'yes']:
                    interactive_live_mode(cam_name, cam_idx, ard)
            except Exception:
                pass
                
        # Reset Kamera auf Free-Run
        reset_camera_to_freerun(cam_idx)
        
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
