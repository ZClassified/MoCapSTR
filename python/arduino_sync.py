import serial
import serial.tools.list_ports
import time

class ArduinoSync:
    def __init__(self):
        self.serial_conn = None
        self.is_connected = False
        self.is_running = False
        
    @staticmethod
    def get_available_ports():
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
        
    def connect(self, port, baudrate=115200):
        try:
            self.serial_conn = serial.Serial(port, baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino to reset after connection
            self.is_connected = True
            
            # Read startup message if any
            if self.serial_conn.in_waiting:
                print(f"Arduino: {self.serial_conn.readline().decode('utf-8').strip()}")
                
            return True
        except serial.SerialException as e:
            print(f"Error connecting to Arduino on {port}: {e}")
            self.is_connected = False
            return False
            
    def disconnect(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.stop_trigger()
            self.serial_conn.close()
        self.is_connected = False
        
    def send_command(self, cmd):
        if not self.is_connected or not self.serial_conn.is_open:
            print("Cannot send command: Arduino not connected.")
            return False
            
        try:
            self.serial_conn.write(f"<{cmd}>\n".encode('utf-8'))
            time.sleep(0.05)
            # Read response
            if self.serial_conn.in_waiting:
                response = self.serial_conn.readline().decode('utf-8').strip()
                print(f"Arduino response: {response}")
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

if __name__ == "__main__":
    # Simple test
    print("Available ports:", ArduinoSync.get_available_ports())
