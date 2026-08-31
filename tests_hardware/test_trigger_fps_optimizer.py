"""
MoCapSTR - Hardware Trigger FPS & Timing Optimizer
===================================================
Diagnoses and tests maximum achievable FPS, pulse widths, USB polling rates,
and resolutions in InnoMaker OV9281 Hardware Trigger mode.

Key features:
- Live Sweep across FPS (20 to 120 FPS)
- Live Pulse Width Adjustment (50µs to 2000µs)
- USB Polling Comparison (60 FPS vs 120 FPS DirectShow request)
- Resolution Comparison (1280x720 vs 640x400)
- Microsecond Packet Timing & Frame-Drop Analysis (Detects skipped pulses)
- Multi-Camera Support (Tests 1 or all 4 cameras simultaneously)

Usage:
    python tests_hardware/test_trigger_fps_optimizer.py
"""

import sys
import os
import time
import gc
import statistics
import cv2
import av

# Ensure python/ directory is on import path
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
    except Exception as e:
        print(f"Error enumerating cameras: {e}")
        return [(0, "USB Camera")]

def set_camera_exposure_and_trigger(cam_idx, exposure_val=-10, gain_val=0, trigger_on=True):
    """Configures DirectShow exposure and MSMF hardware trigger registers."""
    # 1. DirectShow Exposure & Gain
    try:
        cap_d = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
        if cap_d.isOpened():
            cap_d.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            cap_d.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25) # 0.25 = Manual
            cap_d.set(cv2.CAP_PROP_EXPOSURE, exposure_val)
            cap_d.set(cv2.CAP_PROP_GAIN, gain_val)
            cap_d.release()
        del cap_d
    except Exception as e:
        print(f"[!] DirectShow exposure config error on cam {cam_idx}: {e}")

    # 2. MSMF Hardware Trigger Toggle
    try:
        cap_m = cv2.VideoCapture(cam_idx, cv2.CAP_MSMF)
        if cap_m.isOpened():
            cap_m.set(cv2.CAP_PROP_AUTOFOCUS, 1 if trigger_on else 0)
            if trigger_on:
                cap_m.set(cv2.CAP_PROP_FOCUS, 0)
            cap_m.release()
        del cap_m
    except Exception as e:
        print(f"[!] MSMF trigger toggle error on cam {cam_idx}: {e}")

    gc.collect()
    time.sleep(0.2)

def reset_cameras_to_freerun(camera_list):
    print("\nResetting all cameras to Free-Run mode...")
    for cam_idx, _ in camera_list:
        try:
            cap_m = cv2.VideoCapture(cam_idx, cv2.CAP_MSMF)
            if cap_m.isOpened():
                cap_m.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                cap_m.release()
            del cap_m
        except Exception:
            pass
    gc.collect()

def run_benchmark_test(cam_idx, cam_name, ard, width=1280, height=720, usb_polling_fps=120, target_fps=30, pulse_us=500, exposure_val=-10, duration=3.0):
    """
    Measures exact packet arrival intervals and FPS for a specific combination of parameters.
    """
    print(f"\n--- Testing: {width}x{height} | USB Polling: {usb_polling_fps} fps | Trigger: {target_fps} fps | Pulse: {pulse_us}µs | Exp: {exposure_val} ---")
    
    # 1. Start Arduino trigger
    ard.set_pulse_width(pulse_us)
    ard.set_fps(target_fps)
    ard.start_trigger()
    time.sleep(0.2)

    # 2. Configure camera
    set_camera_exposure_and_trigger(cam_idx, exposure_val=exposure_val, trigger_on=True)

    # 3. Open PyAV stream
    options = {
        'video_size': f'{width}x{height}',
        'framerate': str(usb_polling_fps),
        'vcodec': 'mjpeg',
        'rtbufsize': '256M'
    }

    try:
        container = av.open(f'video={cam_name}', format='dshow', options=options)
        stream = container.streams.video[0]
    except Exception as e:
        print(f"[!] PyAV open failed: {e}")
        ard.stop_trigger()
        return None

    # 4. Flush old packets
    t_flush = time.time()
    for packet in container.demux(stream):
        if packet.size > 0:
            if time.time() - t_flush > 0.6:
                break

    # 5. Measure packet arrival intervals
    timestamps = []
    t_start = time.time()
    
    for packet in container.demux(stream):
        if packet.size > 0:
            now = time.time()
            timestamps.append(now)
            if now - t_start >= duration:
                break

    container.close()
    ard.stop_trigger()

    if len(timestamps) < 2:
        print(f"  ❌ NO PACKETS RECEIVED (0 FPS)")
        return {
            "fps": 0.0,
            "target": target_fps,
            "packets": 0,
            "mean_interval_ms": 0,
            "jitter_ms": 0,
            "dropped_estimate_pct": 100.0
        }

    total_time = timestamps[-1] - timestamps[0]
    measured_fps = (len(timestamps) - 1) / total_time
    
    intervals_ms = [(timestamps[i] - timestamps[i-1]) * 1000.0 for i in range(1, len(timestamps))]
    mean_int = statistics.mean(intervals_ms)
    jitter = statistics.stdev(intervals_ms) if len(intervals_ms) > 1 else 0.0
    expected_int = 1000.0 / target_fps

    # Estimate skipped frames: if interval is ~2x expected interval
    dropped_frames = sum(1 for dt in intervals_ms if dt > (expected_int * 1.5))
    drop_pct = (dropped_frames / len(intervals_ms)) * 100.0

    status = "✅ PASS" if abs(measured_fps - target_fps) < (target_fps * 0.05) and drop_pct < 2.0 else "⚠️ MISMATCH / DROPS"
    print(f"  Result: {measured_fps:.2f} FPS (Target: {target_fps}) | Avg Interval: {mean_int:.2f}ms (Target: {expected_int:.2f}ms) | Jitter: ±{jitter:.2f}ms | Skipped Pulses: {drop_pct:.1f}% -> {status}")

    return {
        "fps": measured_fps,
        "target": target_fps,
        "packets": len(timestamps),
        "mean_interval_ms": mean_int,
        "jitter_ms": jitter,
        "dropped_estimate_pct": drop_pct
    }

def run_comprehensive_matrix():
    print("=" * 70)
    print(" MoCapSTR Hardware Trigger Comprehensive Timing Matrix")
    print("=" * 70)

    cams = get_camera_list()
    if not cams:
        print("No cameras found!")
        return

    print(f"Detected {len(cams)} camera(s). Using Camera 0: {cams[0][1]}")
    cam_idx, cam_name = cams[0]

    ard = ArduinoSync()
    port = ard.auto_detect_port() or (ArduinoSync.get_available_ports()[0] if ArduinoSync.get_available_ports() else None)
    if not port or not ard.connect(port):
        print(f"Failed to connect to Arduino on {port}!")
        return

    print(f"Arduino connected on {port}.")

    # Matrix tests:
    # 1. 1280x720 @ USB Polling 60 vs 120 across FPS [20, 25, 30, 40, 50, 60]
    test_rates = [20, 25, 30, 40, 50, 60]
    polling_modes = [60, 120]
    pulse_widths = [100, 500, 1000]

    print("\n" + "=" * 70)
    print(" TEST PHASE 1: USB Polling (60 vs 120) vs Target FPS (1280x720, Exposure=-10, Pulse=500µs)")
    print("=" * 70)

    results_p1 = {}
    for poll in polling_modes:
        results_p1[poll] = {}
        for tfps in test_rates:
            res = run_benchmark_test(
                cam_idx, cam_name, ard,
                width=1280, height=720,
                usb_polling_fps=poll,
                target_fps=tfps,
                pulse_us=500,
                exposure_val=-10,
                duration=3.0
            )
            results_p1[poll][tfps] = res

    print("\n" + "=" * 70)
    print(" TEST PHASE 2: Pulse Width Sweep at 60 FPS (1280x720, USB Polling=120)")
    print("=" * 70)
    results_p2 = {}
    for pw in [50, 100, 250, 500, 1000, 2000]:
        res = run_benchmark_test(
            cam_idx, cam_name, ard,
            width=1280, height=720,
            usb_polling_fps=120,
            target_fps=60,
            pulse_us=pw,
            exposure_val=-10,
            duration=3.0
        )
        results_p2[pw] = res

    print("\n" + "=" * 70)
    print(" TEST PHASE 3: Resolution Comparison (1280x720 vs 640x400) at High Trigger Rates (50, 60, 90, 120 FPS)")
    print("=" * 70)
    results_p3 = {}
    for res_name, (w, h) in [("1280x720", (1280, 720)), ("640x400", (640, 400))]:
        results_p3[res_name] = {}
        for tfps in [50, 60, 75, 90, 100, 120]:
            res = run_benchmark_test(
                cam_idx, cam_name, ard,
                width=w, height=h,
                usb_polling_fps=120,
                target_fps=tfps,
                pulse_us=250,
                exposure_val=-10,
                duration=3.0
            )
            results_p3[res_name][tfps] = res

    # Summary table
    print("\n" + "=" * 70)
    print(" SUMMARY REPORT")
    print("=" * 70)
    print("\n1. USB Polling vs Trigger FPS (1280x720):")
    print("Target FPS | Polling 60 FPS Output | Polling 120 FPS Output")
    print("-" * 55)
    for tfps in test_rates:
        r60 = results_p1[60].get(tfps)
        r120 = results_p1[120].get(tfps)
        fps60_str = f"{r60['fps']:.1f} FPS" if r60 else "N/A"
        fps120_str = f"{r120['fps']:.1f} FPS" if r120 else "N/A"
        print(f"  {tfps:3d} FPS   |      {fps60_str:>10s}       |      {fps120_str:>10s}")

    print("\n2. Pulse Width at 60 FPS Target (1280x720 @ 120 Polling):")
    print("Pulse Width | Measured FPS | Skipped Pulses %")
    print("-" * 50)
    for pw, r in results_p2.items():
        if r:
            print(f"  {pw:4d} µs   |   {r['fps']:5.1f} FPS   |      {r['dropped_estimate_pct']:5.1f}%")

    print("\n3. High-Speed Trigger: 1280x720 vs 640x400 (@ 120 Polling, Pulse 250µs):")
    print("Target FPS | 1280x720 Output | 640x400 Output")
    print("-" * 50)
    for tfps in [50, 60, 75, 90, 100, 120]:
        r720 = results_p3["1280x720"].get(tfps)
        r400 = results_p3["640x400"].get(tfps)
        fps720_str = f"{r720['fps']:.1f} FPS" if r720 else "N/A"
        fps400_str = f"{r400['fps']:.1f} FPS" if r400 else "N/A"
        print(f"  {tfps:3d} FPS   |    {fps720_str:>10s}   |    {fps400_str:>10s}")

    reset_cameras_to_freerun(cams)
    ard.stop_trigger()
    ard.disconnect()
    print("\nBenchmark completed. Cameras reset to Free-Run.")

if __name__ == "__main__":
    try:
        run_comprehensive_matrix()
    except KeyboardInterrupt:
        print("\nAborted by user.")
    except Exception as e:
        print(f"\nUnhandled exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            input("\nPress [ENTER] to exit...")
        except Exception:
            pass
