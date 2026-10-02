"""
Firmware flasher tests against a simulated STK500v1 bootloader.

Run from the repository root:
    python -m unittest discover tests
"""
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))

from firmware_flasher import (FlashError, Stk500Uploader, bundled_firmware, is_outdated,  # noqa: E402
                              read_intel_hex)



class FakeBootloader:
    """Simulated Optiboot / ATmegaBOOT on the other end of a serial port."""
    def __init__(self, baud=115200, signature=b"\x1e\x95\x0f", corrupt_readback=False):
        self.baud = baud
        self.signature = signature
        self.corrupt_readback = corrupt_readback
        self.flash = bytearray(b"\xff" * 32768)
        self.address = 0
        self.left_progmode = False

    def open(self, port, baud, timeout=None):
        return FakeSerial(self, baud)


class FakeSerial:
    LENGTHS = {0x30: 0, 0x50: 0, 0x51: 0, 0x75: 0, 0x55: 2}

    def __init__(self, bootloader, baud):
        self.bl = bootloader
        self.baud_ok = baud == bootloader.baud
        self.inbuf = b""
        self.outbuf = b""
        self.dtr = self.rts = True

    def write(self, data):
        if not self.baud_ok:
            return len(data)  # wrong baud rate: bootloader sees garbage, answers nothing
        self.inbuf += data
        self._process()
        return len(data)

    def _process(self):
        while self.inbuf:
            cmd = self.inbuf[0]
            if cmd in (0x64, 0x74):
                if len(self.inbuf) < 4:
                    return
                size = (self.inbuf[1] << 8) | self.inbuf[2]
                n_params = 3 + (size if cmd == 0x64 else 0)
            else:
                n_params = self.LENGTHS[cmd]
            if len(self.inbuf) < 1 + n_params + 1:
                return
            params = self.inbuf[1:1 + n_params]
            assert self.inbuf[1 + n_params] == 0x20, "missing CRC_EOP"
            self.inbuf = self.inbuf[2 + n_params:]
            self.outbuf += b"\x14" + self._execute(cmd, params) + b"\x10"

    def _execute(self, cmd, params):
        bl = self.bl
        if cmd == 0x75:
            return bl.signature
        if cmd == 0x55:
            bl.address = (params[0] | (params[1] << 8)) * 2
        elif cmd == 0x64:
            data = params[3:]
            bl.flash[bl.address:bl.address + len(data)] = data
        elif cmd == 0x74:
            size = (params[0] << 8) | params[1]
            data = bytearray(bl.flash[bl.address:bl.address + size])
            if bl.corrupt_readback and bl.address == 256:
                data[5] ^= 0xFF
            return bytes(data)
        elif cmd == 0x51:
            bl.left_progmode = True
        return b""

    def read(self, n):
        data, self.outbuf = self.outbuf[:n], self.outbuf[n:]
        return data

    def reset_input_buffer(self):
        self.outbuf = b""

    def close(self):
        pass


def upload(bootloader, image):
    uploader = Stk500Uploader("COM_TEST", serial_factory=bootloader.open, log=lambda msg: None,
                              sleep=lambda seconds: None)
    uploader.drain_time = 0.01
    progress = []
    uploader.flash(image, progress=progress.append)
    return progress


class UploaderTest(unittest.TestCase):
    def setUp(self):
        hex_path, _ = bundled_firmware()
        self.image = read_intel_hex(hex_path)

    def test_flash_new_bootloader(self):
        bl = FakeBootloader(baud=115200)
        progress = upload(bl, self.image)
        self.assertEqual(bytes(bl.flash[:len(self.image)]), self.image)
        self.assertTrue(bl.left_progmode)
        self.assertAlmostEqual(progress[-1], 1.0)

    def test_flash_old_bootloader_falls_back_to_57600(self):
        bl = FakeBootloader(baud=57600)
        upload(bl, self.image)
        self.assertEqual(bytes(bl.flash[:len(self.image)]), self.image)

    def test_no_bootloader(self):
        with self.assertRaises(FlashError):
            upload(FakeBootloader(baud=9600), self.image)

    def test_unsupported_chip(self):
        with self.assertRaisesRegex(FlashError, "Unsupported"):
            upload(FakeBootloader(signature=b"\x1e\x94\x06"), self.image)  # ATmega168

    def test_verification_failure(self):
        with self.assertRaisesRegex(FlashError, "Verification failed"):
            upload(FakeBootloader(corrupt_readback=True), self.image)


class BundledFirmwareTest(unittest.TestCase):
    def test_version_matches_sketch(self):
        _, version = bundled_firmware()
        with open(os.path.join(ROOT, "arduino", "trigger_firmware", "trigger_firmware.ino"), encoding="utf-8") as f:
            sketch_version = re.search(r'#define\s+FIRMWARE_VERSION\s+"([^"]+)"', f.read()).group(1)
        self.assertEqual(version, sketch_version,
                         "trigger_firmware.hex is outdated - run: python arduino/build_firmware.py")

    def test_hex_is_valid(self):
        hex_path, version = bundled_firmware()
        image = read_intel_hex(hex_path)
        self.assertGreater(len(image), 1000)
        self.assertIn(f"VERSION:".encode(), image)
        self.assertIn(version.encode(), image)

    def test_corrupt_hex_is_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".hex", delete=False) as f:
            f.write(":100000000C9463000C948B000C948B000C948B006D\n:00000001FF\n")  # bad checksum
        try:
            with self.assertRaises(FlashError):
                read_intel_hex(f.name)
        finally:
            os.remove(f.name)


class VersionCompareTest(unittest.TestCase):
    def test_is_outdated(self):
        self.assertTrue(is_outdated(None, "1.5.0"))
        self.assertTrue(is_outdated("1.4.9", "1.5.0"))
        self.assertTrue(is_outdated("garbage", "1.5.0"))
        self.assertFalse(is_outdated("1.5.0", "1.5.0"))
        self.assertFalse(is_outdated("1.10.0", "1.5.0"))


if __name__ == "__main__":
    unittest.main()
