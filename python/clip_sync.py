"""
Post-recording verification and alignment of multi-camera clips.

Every recorded clip has a timestamps CSV next to it (written by CameraWorker):

    frame_index, arrival_ns, device_time_s, filler

- arrival_ns:    time.perf_counter_ns() when the packet left the demuxer
                 (same monotonic clock for all cameras of one recording)
- device_time_s: DirectShow sample time of the packet (per-camera clock)
- filler:        1 if the frame is a copy of the previous frame inserted to
                 keep the timeline aligned (e.g. after a queue overflow)

finalize_clips() uses this data to
  1. detect frames the camera never delivered (gap in device_time_s),
  2. fill those gaps with copies of the previous frame when the evidence is
     unambiguous (missing frames == frame deficit vs. the longest clip),
  3. trim all clips to the same length as a last resort.
"""

import csv
import fractions
import os
import statistics
from dataclasses import dataclass

import av

TIMESTAMP_FIELDS = ["frame_index", "arrival_ns", "device_time_s", "filler"]


@dataclass
class RecordingResult:
    path: str
    frames: int
    filled_frames: int = 0       # copies inserted live (queue overflow / mux error)
    dropped_packets: int = 0     # packets lost because the write queue was full
    mux_errors: int = 0
    timestamps_path: str = None
    complete: bool = True        # False if the writer thread did not finish in time


def add_copy_stream(container, template_stream, fps):
    """
    Adds an output stream for lossless stream copy of `template_stream` packets.
    `rate` must be given explicitly: otherwise e.g. Matroska stores 24 FPS as
    frame rate, which OpenCV/FreeMoCap then report as the clip's FPS.
    """
    rate = int(round(fps))
    stream = container.add_stream(template_stream.name, rate=rate)
    stream.width = template_stream.codec_context.width
    stream.height = template_stream.codec_context.height
    if template_stream.codec_context.pix_fmt:
        stream.pix_fmt = template_stream.codec_context.pix_fmt
    # Clean monotonic PTS: frame N has pts N
    stream.time_base = fractions.Fraction(1, rate)
    return stream


def read_timestamps(path):
    """Returns a list of row dicts with typed values, or [] if unavailable."""
    if not path or not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "arrival_ns": int(row["arrival_ns"]) if row["arrival_ns"] else None,
                "device_time_s": float(row["device_time_s"]) if row["device_time_s"] else None,
                "filler": row["filler"] == "1",
            })
    return rows


def write_timestamps(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(TIMESTAMP_FIELDS)
        for i, row in enumerate(rows):
            writer.writerow([
                i,
                "" if row["arrival_ns"] is None else row["arrival_ns"],
                "" if row["device_time_s"] is None else f"{row['device_time_s']:.6f}",
                1 if row["filler"] else 0,
            ])


def find_missing_frames(rows):
    """
    Detects frames the camera never delivered, based on gaps in device_time_s.

    Returns {frame_index: missing_count}: `missing_count` frames are missing
    directly before `frame_index`. Filler frames already present in the clip are
    taken into account. A long interval that is immediately followed by a very
    short one is treated as delivery jitter (frame arrived late), not a gap.
    """
    real = [(i, r["device_time_s"]) for i, r in enumerate(rows)
            if not r["filler"] and r["device_time_s"] is not None]
    if len(real) < 10:
        return {}

    unit_deltas = [t2 - t1 for (i1, t1), (i2, t2) in zip(real, real[1:]) if i2 == i1 + 1]
    if len(unit_deltas) < 5:
        return {}
    frame_dt = statistics.median(unit_deltas)
    if frame_dt <= 0:
        return {}

    missing = {}
    for k in range(len(real) - 1):
        (i1, t1), (i2, t2) = real[k], real[k + 1]
        dt = t2 - t1
        if dt < 1.5 * frame_dt * (i2 - i1):
            continue
        n_missing = round(dt / frame_dt) - (i2 - i1)
        if n_missing < 1:
            continue
        # Late delivery shows up as long interval + very short next interval
        if k + 2 < len(real):
            (i3, t3) = real[k + 2]
            if (t3 - t2) < 0.5 * frame_dt * (i3 - i2):
                continue
        missing[i2] = n_missing
    return missing


def remux_clip(path, fps, keep_frames, insert_before=None, timestamps_path=None):
    """
    Lossless stream-copy re-mux of a clip:
      - inserts copies of the previous frame (insert_before = {src_index: count})
      - truncates the clip to `keep_frames` frames
    The timestamps CSV is rewritten to match. The original file is only replaced
    after the new file was written successfully. Returns the new frame count.
    """
    insert_before = insert_before or {}
    root, ext = os.path.splitext(path)
    tmp_path = f"{root}.syncfix{ext}"  # Keep the extension: PyAV picks the muxer from it
    time_base = fractions.Fraction(1, int(round(fps)))

    src_rows = read_timestamps(timestamps_path)
    new_rows = []
    out_idx = 0
    try:
        with av.open(path) as src:
            src_stream = src.streams.video[0]
            with av.open(tmp_path, mode="w") as dst:
                dst_stream = add_copy_stream(dst, src_stream, fps)

                def write(data):
                    packet = av.Packet(data)
                    packet.stream = dst_stream
                    packet.time_base = time_base
                    packet.pts = out_idx
                    packet.dts = out_idx
                    packet.is_keyframe = True  # MJPEG: every frame is intra-coded
                    dst.mux(packet)

                src_idx = 0
                last_data = None
                for packet in src.demux(src_stream):
                    if packet.dts is None:
                        continue
                    for _ in range(insert_before.get(src_idx, 0)):
                        if out_idx >= keep_frames or last_data is None:
                            break
                        write(last_data)
                        new_rows.append({"arrival_ns": None, "device_time_s": None, "filler": True})
                        out_idx += 1
                    if out_idx >= keep_frames:
                        break
                    last_data = bytes(packet)
                    write(last_data)
                    if src_idx < len(src_rows):
                        new_rows.append(src_rows[src_idx])
                    out_idx += 1
                    src_idx += 1

        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

    if timestamps_path and src_rows:
        write_timestamps(timestamps_path, new_rows)
    return out_idx


def finalize_clips(results, fps, hardware_trigger):
    """
    Verifies and aligns all clips of one recording.

    Args:
        results:          {cam_idx: RecordingResult}
        fps:              recording frame rate
        hardware_trigger: True if the clips were recorded with the Arduino trigger.
                          Gap repair is only done in that mode, because only then
                          frame N of every camera belongs to the same trigger pulse.

    Returns:
        (final_counts {cam_idx: frames}, messages [(level, text)])
        level is "info", "success" or "error".
    """
    messages = []
    counts = {idx: r.frames for idx, r in results.items()}

    for idx, r in sorted(results.items()):
        if r.filled_frames:
            messages.append(("error",
                f"Cam {idx}: {r.dropped_packets + r.mux_errors} Frame(s) gingen beim Schreiben verloren "
                f"und wurden durch Kopien des Vorframes ersetzt (Timing bleibt synchron)."))
        if not r.complete:
            messages.append(("error", f"Cam {idx}: Schreiben wurde nicht rechtzeitig beendet - Datei evtl. unvollständig."))

    if not counts:
        return counts, messages

    # --- 1. Detect frames the camera never delivered ---------------------------
    missing = {}
    for idx, r in results.items():
        gaps = find_missing_frames(read_timestamps(r.timestamps_path))
        if gaps:
            missing[idx] = gaps

    # --- 2. Repair gaps where the evidence is unambiguous -----------------------
    if hardware_trigger and len(counts) > 1 and missing:
        target = max(counts.values())
        for idx, gaps in sorted(missing.items()):
            deficit = target - counts[idx]
            total_missing = sum(gaps.values())
            where = ", ".join(f"vor Frame {i}" + (f" ({n}x)" if n > 1 else "") for i, n in sorted(gaps.items()))
            if deficit > 0 and total_missing == deficit:
                try:
                    r = results[idx]
                    counts[idx] = remux_clip(r.path, fps, keep_frames=target,
                                             insert_before=gaps, timestamps_path=r.timestamps_path)
                    messages.append(("error",
                        f"Cam {idx}: {total_missing} fehlende(r) Trigger-Frame(s) erkannt ({where}) "
                        f"und mit Kopien des Vorframes aufgefüllt."))
                except Exception as e:
                    messages.append(("error", f"Cam {idx}: Auffüllen fehlgeschlagen ({e})."))
            else:
                messages.append(("error",
                    f"Cam {idx}: Mögliche Frame-Lücke(n) erkannt ({where}), aber nicht eindeutig "
                    f"zuzuordnen - nicht automatisch repariert. Bitte Clip prüfen."))
    elif missing:
        for idx, gaps in sorted(missing.items()):
            messages.append(("error", f"Cam {idx}: {sum(gaps.values())} Frame(s) von der Kamera nicht geliefert."))

    # --- 3. Equal length as last resort ----------------------------------------
    if len(counts) > 1:
        min_frames = min(counts.values())
        delta = max(counts.values()) - min_frames
        if delta > 0:
            for idx, r in sorted(results.items()):
                if counts[idx] <= min_frames:
                    continue
                try:
                    counts[idx] = remux_clip(r.path, fps, keep_frames=min_frames,
                                             timestamps_path=r.timestamps_path)
                except Exception as e:
                    messages.append(("error", f"Cam {idx}: Kürzen fehlgeschlagen ({e}). Original behalten."))
            messages.append(("error",
                f"Clip-Längen wichen um bis zu {delta} Frame(s) ab - alle Clips am Ende auf "
                f"{min_frames} Frames gekürzt. Bei Abweichungen mitten in der Aufnahme kann ein "
                f"Versatz bleiben."))

    if len(set(counts.values())) == 1:
        level = "success" if not any(lvl == "error" for lvl, _ in messages) else "info"
        messages.append((level, "Alle Clips gleich lang: " +
                         ", ".join(f"Cam {i}: {n}" for i, n in sorted(counts.items())) + " Frames."))
    else:
        messages.append(("error", "Clips sind NICHT gleich lang: " +
                         ", ".join(f"Cam {i}: {n}" for i, n in sorted(counts.items()))))
    return counts, messages
