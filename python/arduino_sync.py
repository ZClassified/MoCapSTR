import serial
import serial.tools.list_ports
import time
import threading

class ArduinoSync:
    def __init__(self):
        self.serial_conn = None
        self.is_connected = False
        self.is_running = False
        
        self.reader_thread = None
        self.stop_reader = False
        self.last_ping_response = 0
        
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
            self.serial_conn = serial.Serial(port, baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino to reset after connection
            self.is_connected = True
            self.last_ping_response = time.time()
            self.stop_reader = False
            
            # Start background reader thread
            self.reader_thread = threading.Thread(target=self._read_from_serial, daemon=True)
            self.reader_thread.start()
            
            return True
        except serial.SerialException as e:
            print(f"Error connecting to Arduino on {port}: {e}")
            self.is_connected = False
            return False
            
    def _read_from_serial(self):
        while not self.stop_reader and self.is_connected and self.serial_conn and self.serial_conn.is_open:
            try:
                if self.serial_conn.in_waiting:
                    response = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if not response:
                        continue
                        
                    if response == "PONG":
                        self.last_ping_response = time.time()
                    elif response == "<TOGGLE_REC>":
                        if self.on_toggle_rec_callback:
                            self.on_toggle_rec_callback()
                    else:
                        print(f"Arduino response: {response}")
                else:
                    time.sleep(0.01)
            except Exception as e:
                print(f"Serial read error: {e}")
                self.is_connected = False
                break
                
    def disconnect(self):
        self.stop_reader = True
        if self.serial_conn and self.serial_conn.is_open:
            self.stop_trigger()
            time.sleep(0.1) # Give thread a moment to finish sending/reading
            self.serial_conn.close()
        self.is_connected = False
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1.0)
        
    def send_command(self, cmd):
        if not self.is_connected or not self.serial_conn.is_open:
            print("Cannot send command: Arduino not connected.")
            return False
            
        try:
            self.serial_conn.write(f"<{cmd}>\n".encode('utf-8'))
            return True
        except Exception as e:
            print(f"Error sending command to Arduino: {e}")
            self.is_connected = False
            return False
            
    def set_fps(self, fps):
        print(f"Setting Arduino trigger FPS to {fps}")
        return self.send_command(f"FPS:{int(fps)}")
        
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
        if not self.is_connected or not self.serial_conn.is_open:
            return False
            
        try:
            self.serial_conn.write("<PING>\n".encode('utf-8'))
            
            # Check if we got a pong recently (within 5 seconds)
            if time.time() - self.last_ping_response > 5.0:
                print("Arduino ping timeout!")
                self.is_connected = False
                return False
                
            return True
        except Exception as e:
            print(f"Error pinging Arduino: {e}")
            self.is_connected = False
            return False

if __name__ == "__main__":
    # Simple test
    print("Available ports:", ArduinoSync.get_available_ports())
