"""
MoCapSTR - Interactive Hardware Trigger Live Optimizer
======================================================
Interactive OpenCV live window to test and fine-tune trigger FPS and pulse width.

Keyboard Shortcuts:
  [1] -> 25 FPS Trigger       [2] -> 30 FPS Trigger       [3] -> 50 FPS Trigger
  [4] -> 60 FPS Trigger       [5] -> 90 FPS Trigger       [6] -> 120 FPS Trigger
  [+] -> +5 FPS               [-] -> -5 FPS
  [P] -> Toggle Pulse Width (100µs -> 250µs -> 500µs -> 1000µs)
  [U] -> Toggle USB Polling Mode (60 vs 120 FPS)
  [R] -> Toggle Resolution (1280x720 vs 640x400)
  [E] -> Toggle Exposure (-10 vs -8 vs -6)
  [0] -> Toggle Free-Run Mode
  [SPACE] -> Start / Pause Trigger
  [ESC / Q] -> Exit

Usage:
    python tests_hardware/test_trigger_fps_live.py
"""

import sys
import os
import time
import gc
import cv2
import av

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'python')))
from arduino_sync import ArduinoSync
from pygrabber.dshow_graph import FilterGraph

def get_camera_list():
    try:
        g = FilterGraph()
        devices = g.get_input_devices()
        valid = []
        for idx, name in enumerate(devices):
            if "virtual" in name.lower() or "obs" in name.lower():
                continue
            valid.append((idx, name))
        return valid
    except Exception:
        return [(0, "USB Camera")]

def set_camera_exposure_and_trigger(cam_idx, exposure_val=-10, gain_val=0, trigger_on=True):
    try:
        cap_d = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
        if cap_d.isOpened():
            cap_d.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            cap_d.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            cap_d.set(cv2.CAP_PROP_EXPOSURE, exposure_val)
            cap_d.set(cv2.CAP_PROP_GAIN, gain_val)
            cap_d.release()
        del cap_d
    except Exception:
        pass

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

def interactive_live_optimizer():
    cams = get_camera_list()
    if not cams:
        print("Keine Kameras gefunden!")
        return

    cam_idx, cam_name = cams[0]
    print(f"Verwende Kamera: {cam_name} (Index {cam_idx})")

    ard = ArduinoSync()
    port = ard.auto_detect_port() or (ArduinoSync.get_available_ports()[0] if ArduinoSync.get_available_ports() else None)
    if not port or not ard.connect(port):
        print(f"Konnte Arduino nicht verbinden!")
        return

    # Initial settings
    current_fps = 30
    pulse_widths = [100, 250, 500, 1000]
    pulse_idx = 2 # 500µs
    usb_polling_rates = [120, 60]
    poll_idx = 0 # 120 fps
    resolutions = [(1280, 720), (640, 400)]
    res_idx = 0
    exposures = [-10, -8, -6]
    exp_idx = 0
    is_trigger_mode = True

    ard.set_pulse_width(pulse_widths[pulse_idx])
    ard.set_fps(current_fps)
    ard.start_trigger()

    win_name = "MoCapSTR Trigger Live Optimizer - [Tasten: 1..6, +, -, P, U, R, E, SPACE, ESC]"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 1024, 576)

    def open_stream():
        w, h = resolutions[res_idx]
        poll_fps = usb_polling_rates[poll_idx]
        exp_val = exposures[exp_idx]
        set_camera_exposure_and_trigger(cam_idx, exposure_val=exp_val, trigger_on=is_trigger_mode)
        options = {
            'video_size': f'{w}x{h}',
            'framerate': str(poll_fps),
            'vcodec': 'mjpeg',
            'rtbufsize': '256M'
        }
        return av.open(f'video={cam_name}', format='dshow', options=options)

    container = open_stream()
    stream = container.streams.video[0]

    frame_counter = 0
    last_fps_time = time.time()
    live_fps = 0.0
    last_delta_ms = 0.0
    last_pkt_time = time.time()

    needs_reopen = False

    print("\n--- Live-Monitor aktiv! Druecke Tasten im Fenster fuer Echtzeit-Aenderungen ---\n")

    try:
        while True:
            if needs_reopen:
                try:
                    container.close()
                except:
                    pass
                time.sleep(0.3)
                container = open_stream()
                stream = container.streams.video[0]
                frame_counter = 0
                last_fps_time = time.time()
                last_pkt_time = time.time()
                needs_reopen = False

            for packet in container.demux(stream):
                if packet.size > 0:
                    now = time.time()
                    last_delta_ms = (now - last_pkt_time) * 1000.0
                    last_pkt_time = now
                    frame_counter += 1

                    if now - last_fps_time >= 1.0:
                        live_fps = frame_counter / (now - last_fps_time)
                        frame_counter = 0
                        last_fps_time = now

                    for frame in packet.decode():
                        img = frame.to_ndarray(format='bgr24')
                        
                        w, h = resolutions[res_idx]
                        poll_fps = usb_polling_rates[poll_idx]
                        pw = pulse_widths[pulse_idx]
                        exp_val = exposures[exp_idx]

                        diff = abs(live_fps - current_fps) if is_trigger_mode else 0
                        color = (0, 255, 0) if diff <= (current_fps * 0.06) else (0, 0, 255)

                        mode_str = f"HARDWARE TRIGGER ({current_fps} FPS)" if is_trigger_mode else "FREE-RUN"
                        cv2.putText(img, f"Live FPS: {live_fps:.1f}  |  Target: {mode_str}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
                        cv2.putText(img, f"Format: {w}x{h} @ Polling: {poll_fps} fps | Pulse: {pw}us | Exp: {exp_val} | dt: {last_delta_ms:.1f}ms", 
                                    (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
                        
                        help_str = "1=25p 2=30p 3=50p 4=60p 5=90p 6=120p | +/-=FPS | P=Pulse | U=Poll | R=Res | E=Exp | SPACE=Pause | ESC=End"
                        cv2.putText(img, help_str, (15, img.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

                        cv2.imshow(win_name, img)
                        break

                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord('q'):
                    return
                elif key == ord('1'):
                    current_fps = 25
                    is_trigger_mode = True
                    ard.set_fps(current_fps)
                    ard.start_trigger()
                elif key == ord('2'):
                    current_fps = 30
                    is_trigger_mode = True
                    ard.set_fps(current_fps)
                    ard.start_trigger()
                elif key == ord('3'):
                    current_fps = 50
                    is_trigger_mode = True
                    ard.set_fps(current_fps)
                    ard.start_trigger()
                elif key == ord('4'):
                    current_fps = 60
                    is_trigger_mode = True
                    ard.set_fps(current_fps)
                    ard.start_trigger()
                elif key == ord('5'):
                    current_fps = 90
                    is_trigger_mode = True
                    ard.set_fps(current_fps)
                    ard.start_trigger()
                elif key == ord('6'):
                    current_fps = 120
                    is_trigger_mode = True
                    ard.set_fps(current_fps)
                    ard.start_trigger()
                elif key == ord('+') or key == ord('='):
                    current_fps = min(120, current_fps + 5)
                    ard.set_fps(current_fps)
                elif key == ord('-') or key == ord('_'):
                    current_fps = max(10, current_fps - 5)
                    ard.set_fps(current_fps)
                elif key == ord('p') or key == ord('P'):
                    pulse_idx = (pulse_idx + 1) % len(pulse_widths)
                    new_pw = pulse_widths[pulse_idx]
                    resp = ard.set_pulse_width(new_pw)
                    print(f"Arduino response: {resp}")
                elif key == ord('u') or key == ord('U'):
                    poll_idx = (poll_idx + 1) % len(usb_polling_rates)
                    needs_reopen = True
                    break
                elif key == ord('r') or key == ord('R'):
                    res_idx = (res_idx + 1) % len(resolutions)
                    needs_reopen = True
                    break
                elif key == ord('e') or key == ord('E'):
                    exp_idx = (exp_idx + 1) % len(exposures)
                    needs_reopen = True
                    break
                elif key == ord('0'):
                    is_trigger_mode = not is_trigger_mode
                    if is_trigger_mode:
                        ard.start_trigger()
                    else:
                        ard.stop_trigger()
                    needs_reopen = True
                    break
                elif key == 32: # SPACE
                    if ard.is_running:
                        ard.stop_trigger()
                    else:
                        ard.start_trigger()

    except Exception as e:
        print(f"Live monitor error: {e}")
    finally:
        try:
            container.close()
        except:
            pass
        reset_cameras_to_freerun(cams)
        ard.stop_trigger()
        ard.disconnect()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    interactive_live_optimizer()
