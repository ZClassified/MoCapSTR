import serial
import serial.tools.list_ports
import time
import threading

class ArduinoSync:
    # Seconds without a PONG before the trigger box is reported as unresponsive.
    PONG_TIMEOUT_SEC = 5.0

    def __init__(self):
        self.serial_conn = None
        # True while the serial port is open and no I/O error occurred.
        # A missing PONG does NOT clear this flag (see is_responsive()).
        self.is_connected = False
        self.is_running = False
        self.current_fps = 60  # Firmware default until set_fps() succeeds

        self.reader_thread = None
        self.stop_reader = False
        self.last_pong_time = 0.0       # 0 = no PONG received since connect()
        self.firmware_version = None    # e.g. "1.5.0"; None for firmware < 1.5.0
        self._write_lock = threading.Lock()

        # Callbacks for hardware buttons
        self.on_toggle_rec_callback = None

    @staticmethod
    def auto_detect_port():
        ports = serial.tools.list_ports.comports()

        # Common identifiers for Arduinos (Uno, Nano, clones)
        arduino_keywords = ["arduino", "ch340", "cp210", "usb serial device"]
        arduino_vids = [0x2341, 0x1A86, 0x0403, 0x10C4]

        best_match = None
        for port in ports:
            # Check by VID first
            if port.vid in arduino_vids:
                return port.device

            # Check by description/manufacturer
            desc = (port.description or "").lower()
            manuf = (port.manufacturer or "").lower()

            for keyword in arduino_keywords:
                if keyword in desc or keyword in manuf:
                    best_match = port.device

        return best_match

    @staticmethod
    def get_available_ports():
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]

        # Move auto-detected port to the front of the list
        detected = ArduinoSync.auto_detect_port()
        if detected and detected in port_list:
            port_list.remove(detected)
            port_list.insert(0, detected)

        return port_list

    def connect(self, port, baudrate=115200):
        try:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.disconnect()
                except Exception:
                    pass
            self.serial_conn = serial.Serial(port, baudrate, timeout=1)
            time.sleep(1.5)  # Wait for Arduino bootloader reset
            self.is_connected = True
            self.is_running = False  # Arduino resets on connect -> trigger is stopped
            self.current_fps = 60    # ...and falls back to its default FPS
            self.last_pong_time = 0.0
            self.firmware_version = None
            self.stop_reader = False

            # Start background reader thread
            self.reader_thread = threading.Thread(target=self._read_from_serial, daemon=True)
            self.reader_thread.start()

            # Repeatedly ping up to 3.5 seconds to catch bootloader readiness
            start_wait = time.time()
            while time.time() - start_wait < 3.5:
                self._write(b"<PING>\n")
                if self.last_pong_time > 0:
                    break
                time.sleep(0.3)

            if self.last_pong_time == 0:
                print(f"Port {port} opened, no PONG received within 3.5s. Proceeding in fallback mode.")
                # Do not abort: the serial port is open and will accept trigger commands!
                return True

            # Query firmware version (firmware < 1.5.0 answers "Error: Unknown command")
            self._write(b"<VERSION>\n")
            version_wait = time.time()
            while self.firmware_version is None and time.time() - version_wait < 0.5:
                time.sleep(0.05)
            return True

        except serial.SerialException as e:
            print(f"Error connecting to Arduino on {port}: {e}")
            self.is_connected = False
            return False

    def _read_from_serial(self):
        while not self.stop_reader and self.serial_conn and self.serial_conn.is_open:
            try:
                if self.serial_conn.in_waiting:
                    response = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if not response:
                        continue

                    if response == "PONG":
                        self.last_pong_time = time.time()
                    elif response.startswith("VERSION:"):
                        self.firmware_version = response.split(":", 1)[1].strip()
                    elif response == "<TOGGLE_REC>":
                        if self.on_toggle_rec_callback:
                            self.on_toggle_rec_callback()
                    else:
                        print(f"Arduino response: {response}")
                else:
                    time.sleep(0.01)
            except Exception as e:
                if not self.stop_reader:
                    print(f"Serial read error: {e}")
                    self.is_connected = False
                break

    def disconnect(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.stop_trigger()
            time.sleep(0.1) # Give thread a moment to finish sending/reading
        self.stop_reader = True
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1.0)
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.is_connected = False
        self.is_running = False

    def _write(self, data: bytes) -> bool:
        """Thread-safe write. Marks the connection as lost on I/O errors."""
        if not self.serial_conn or not self.serial_conn.is_open:
            return False
        try:
            with self._write_lock:
                self.serial_conn.write(data)
            return True
        except Exception as e:
            print(f"Error writing to Arduino: {e}")
            self.is_connected = False
            return False

    def send_command(self, cmd):
        if not self.is_connected:
            print("Cannot send command: Arduino not connected.")
            return False
        return self._write(f"<{cmd}>\n".encode('utf-8'))

    def set_fps(self, fps):
        print(f"Setting Arduino trigger FPS to {fps}")
        success = self.send_command(f"FPS:{int(fps)}")
        if success:
            self.current_fps = int(fps)
        return success

    def set_pulse_width(self, pulse_micros: int):
        """Set the trigger pulse width in microseconds.
        Must be well below the trigger interval (e.g. < interval/2).
        Firmware default: 1000µs."""
        print(f"Setting Arduino pulse width to {pulse_micros}µs")
        return self.send_command(f"PULSE:{int(pulse_micros)}")

    def start_trigger(self):
        if not self.is_running:
            success = self.send_command("START")
            if success:
                self.is_running = True
            return success
        return True

    def stop_trigger(self):
        if self.is_running:
            success = self.send_command("STOP")
            if success:
                self.is_running = False
            return success
        return True

    def ping(self):
        """Sends a PING. The answer is evaluated asynchronously via is_responsive().
        Returns False only if the serial port itself failed."""
        if not self.is_connected:
            return False
        return self._write(b"<PING>\n")

    def is_responsive(self):
        """
        True if a PONG arrived within PONG_TIMEOUT_SEC.
        Returns None if the firmware never answered a PING since connect()
        (fallback mode) - responsiveness is unknown in that case.
        """
        if self.last_pong_time == 0:
            return None
        return (time.time() - self.last_pong_time) <= self.PONG_TIMEOUT_SEC

if __name__ == "__main__":
    # Simple test
    print("Available ports:", ArduinoSync.get_available_ports())
