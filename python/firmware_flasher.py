"""
Flashes the bundled trigger firmware onto an Arduino Nano / Uno (ATmega328P)
through its serial bootloader - no Arduino IDE or avrdude required.

Speaks the STK500v1 protocol that both Nano bootloaders understand:
  - Optiboot (Uno, new Nano bootloader)   -> 115200 baud
  - ATmegaBOOT ("Old Bootloader" Nanos)   -> 57600 baud
Both baud rates are tried automatically. Every page is read back and compared.
An interrupted upload cannot damage the bootloader; flashing can simply be
repeated.
"""
import os
import sys
import time

import serial

# --- STK500v1 constants ---
STK_OK = 0x10
STK_INSYNC = 0x14
CRC_EOP = 0x20
STK_GET_SYNC = 0x30
STK_ENTER_PROGMODE = 0x50
STK_LEAVE_PROGMODE = 0x51
STK_LOAD_ADDRESS = 0x55
STK_PROG_PAGE = 0x64
STK_READ_PAGE = 0x74
STK_READ_SIGN = 0x75

PAGE_SIZE = 128              # ATmega328P flash page size in bytes
MAX_APP_SIZE = 30720         # 32 KB flash minus 2 KB (old bootloader, worst case)
BAUD_RATES = (115200, 57600)

SIGNATURES = {
    bytes([0x1E, 0x95, 0x0F]): "ATmega328P",
    bytes([0x1E, 0x95, 0x14]): "ATmega328",
}


class FlashError(Exception):
    pass


def firmware_dir():
    """Folder with trigger_firmware.hex / .version (source tree or PyInstaller bundle)."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "arduino", "trigger_firmware")


def bundled_firmware():
    """Returns (hex_path, version) of the firmware shipped with this app version."""
    folder = firmware_dir()
    hex_path = os.path.join(folder, "trigger_firmware.hex")
    with open(os.path.join(folder, "trigger_firmware.version"), encoding="utf-8") as f:
        version = f.read().strip()
    return hex_path, version


def parse_version(text):
    try:
        return tuple(int(part) for part in text.strip().split("."))
    except (AttributeError, ValueError):
        return None


def is_outdated(installed_version, bundled_version):
    """True if the installed firmware is missing/unknown or older than the bundled one."""
    installed = parse_version(installed_version) if installed_version else None
    bundled = parse_version(bundled_version)
    return installed is None or (bundled is not None and installed < bundled)


def read_intel_hex(path):
    """Parses an Intel HEX file into a contiguous bytes image starting at address 0."""
    memory = {}
    base = 0
    with open(path, encoding="ascii") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            if not line.startswith(":"):
                raise FlashError(f"Invalid HEX file (line {line_no})")
            raw = bytes.fromhex(line[1:])
            length, address, record_type = raw[0], (raw[1] << 8) | raw[2], raw[3]
            data = raw[4:4 + length]
            if len(data) != length or (sum(raw) & 0xFF) != 0:
                raise FlashError(f"Corrupt HEX file (checksum, line {line_no})")
            if record_type == 0x00:
                for i, byte in enumerate(data):
                    memory[base + address + i] = byte
            elif record_type == 0x01:
                break
            elif record_type == 0x02:
                base = ((data[0] << 8) | data[1]) << 4
            elif record_type == 0x04:
                base = ((data[0] << 8) | data[1]) << 16
    if not memory:
        raise FlashError("HEX file contains no data")
    size = max(memory) + 1
    if size > MAX_APP_SIZE:
        raise FlashError(f"Firmware too large ({size} bytes)")
    return bytes(memory.get(i, 0xFF) for i in range(size))


class Stk500Uploader:
    def __init__(self, port, serial_factory=serial.Serial, log=print, sleep=time.sleep):
        self.port = port
        self.serial_factory = serial_factory
        self.log = log
        self.sleep = sleep
        self.drain_time = 0.25
        self.conn = None

    # --- low level ---------------------------------------------------------
    def _read_exact(self, n, timeout=1.0):
        data = b""
        deadline = time.time() + timeout
        while len(data) < n and time.time() < deadline:
            data += self.conn.read(n - len(data))
        return data

    def _command(self, payload, response_len=0, timeout=1.0):
        """Sends payload + CRC_EOP, expects INSYNC [response_len bytes] OK."""
        self.conn.write(bytes(payload) + bytes([CRC_EOP]))
        if self._read_exact(1, timeout) != bytes([STK_INSYNC]):
            raise FlashError("Bootloader out of sync")
        data = self._read_exact(response_len, timeout) if response_len else b""
        if len(data) != response_len or self._read_exact(1, timeout) != bytes([STK_OK]):
            raise FlashError("Bootloader did not acknowledge")
        return data

    def _drain(self):
        """Reads and discards input until the line is quiet for `drain_time` seconds."""
        quiet_until = time.time() + self.drain_time
        while time.time() < quiet_until:
            if self.conn.read(64):
                quiet_until = time.time() + self.drain_time

    def _reset_into_bootloader(self):
        # Auto-reset via DTR/RTS, like the Arduino IDE does
        self.conn.dtr = False
        self.conn.rts = False
        self.sleep(0.25)
        self.conn.dtr = True
        self.conn.rts = True
        self.sleep(0.05)

    def _try_sync(self, attempts=3):
        # Optiboot flashes the LED for ~0.3 s after reset and does not read the
        # UART meanwhile. Bytes sent in that window overrun the UART, the garbled
        # command makes the bootloader exit. So, like avrdude: wait, then send
        # two throw-away syncs whose answers are discarded, then sync for real.
        self._drain()
        for _ in range(2):
            self.conn.write(bytes([STK_GET_SYNC, CRC_EOP]))
            self._drain()
        for _ in range(attempts):
            self.conn.write(bytes([STK_GET_SYNC, CRC_EOP]))
            if self._read_exact(2, timeout=0.5) == bytes([STK_INSYNC, STK_OK]):
                return True
            self._drain()
        return False

    def _connect(self):
        for baud in BAUD_RATES:
            try:
                self.conn = self.serial_factory(self.port, baud, timeout=0.1)
            except serial.SerialException as e:
                raise FlashError(f"Cannot open {self.port}: {e}")
            self._reset_into_bootloader()
            if self._try_sync():
                self.log(f"Bootloader found at {baud} baud.")
                return baud
            self.conn.close()
            self.conn = None
        raise FlashError("No bootloader answered. Is an Arduino Nano/Uno (ATmega328P) connected "
                         "and the port not used by another program?")

    def _load_address(self, byte_address):
        word = byte_address >> 1  # STK500 flash addresses are word addresses
        self._command([STK_LOAD_ADDRESS, word & 0xFF, (word >> 8) & 0xFF])

    # --- public ------------------------------------------------------------
    def flash(self, image, progress=None):
        """Writes and verifies `image`. progress(fraction) is called during the upload."""
        pages = [image[i:i + PAGE_SIZE] for i in range(0, len(image), PAGE_SIZE)]
        pages = [page + b"\xFF" * (PAGE_SIZE - len(page)) for page in pages]
        try:
            self._connect()
            signature = self._command([STK_READ_SIGN], response_len=3)
            if signature not in SIGNATURES:
                raise FlashError(f"Unsupported microcontroller (signature {signature.hex()}). "
                                 "Only ATmega328P boards (Nano/Uno) are supported.")
            self._command([STK_ENTER_PROGMODE])

            total = 2 * len(pages)
            for n, page in enumerate(pages):
                self._load_address(n * PAGE_SIZE)
                self._command([STK_PROG_PAGE, 0, PAGE_SIZE, ord("F")] + list(page), timeout=2.0)
                if progress:
                    progress((n + 1) / total)
            for n, page in enumerate(pages):
                self._load_address(n * PAGE_SIZE)
                readback = self._command([STK_READ_PAGE, 0, PAGE_SIZE, ord("F")], response_len=PAGE_SIZE)
                if readback != page:
                    raise FlashError(f"Verification failed at address 0x{n * PAGE_SIZE:04X}")
                if progress:
                    progress((len(pages) + n + 1) / total)

            self._command([STK_LEAVE_PROGMODE])  # bootloader starts the new firmware
            self.log(f"Firmware written and verified ({len(image)} bytes).")
        finally:
            if self.conn is not None:
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = None


def flash_bundled_firmware(port, progress=None, log=print):
    """Flashes the firmware bundled with MoCapSTR. Returns the flashed version."""
    hex_path, version = bundled_firmware()
    image = read_intel_hex(hex_path)
    log(f"Flashing trigger firmware v{version} to {port}...")
    Stk500Uploader(port, log=log).flash(image, progress=progress)
    return version
