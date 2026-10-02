"""
Compiles trigger_firmware.ino into the pre-built firmware that MoCapSTR can
flash onto an Arduino Nano / Uno (ATmega328P) without the Arduino IDE.

Output (committed to the repository):
    arduino/trigger_firmware/trigger_firmware.hex
    arduino/trigger_firmware/trigger_firmware.version

Requires arduino-cli with the "arduino:avr" core. The arduino-cli bundled with
Arduino IDE 2.x is found automatically.

Usage:
    python arduino/build_firmware.py
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKETCH_DIR = os.path.join(HERE, "trigger_firmware")
SKETCH = os.path.join(SKETCH_DIR, "trigger_firmware.ino")
HEX_OUT = os.path.join(SKETCH_DIR, "trigger_firmware.hex")
VERSION_OUT = os.path.join(SKETCH_DIR, "trigger_firmware.version")
FQBN = "arduino:avr:nano:cpu=atmega328"  # same binary for old and new Nano bootloader


def find_arduino_cli():
    found = shutil.which("arduino-cli")
    if found:
        return found
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"),
        os.path.expandvars(r"%ProgramFiles%\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    sys.exit("arduino-cli not found. Install Arduino IDE 2.x or arduino-cli (with the arduino:avr core).")


def read_sketch_version():
    with open(SKETCH, encoding="utf-8") as f:
        match = re.search(r'#define\s+FIRMWARE_VERSION\s+"([^"]+)"', f.read())
    if not match:
        sys.exit("FIRMWARE_VERSION not found in trigger_firmware.ino")
    return match.group(1)


def main():
    cli = find_arduino_cli()
    version = read_sketch_version()
    with tempfile.TemporaryDirectory() as build_dir:
        cmd = [cli, "compile", "--fqbn", FQBN, "--output-dir", build_dir, SKETCH_DIR]
        print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
        subprocess.run(cmd, check=True)
        hex_files = [p for p in glob.glob(os.path.join(build_dir, "*.ino.hex")) if "with_bootloader" not in p]
        if len(hex_files) != 1:
            sys.exit(f"Unexpected build output: {os.listdir(build_dir)}")
        shutil.copyfile(hex_files[0], HEX_OUT)
    with open(VERSION_OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(version + "\n")
    print(f"Firmware v{version} written to {os.path.relpath(HEX_OUT, os.path.dirname(HERE))}")


if __name__ == "__main__":
    main()
