import serial
import serial.tools.list_ports
import time
import threading
import sys

def get_arduino_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "Arduino" in p.description or "CH340" in p.description or "ttyACM" in p.device:
            return p.device
    if ports:
        return ports[0].device
    return None

def read_from_port(ser):
    print("\n[LISTENING TO ARDUINO] - Press the physical buttons now!")
    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                if not line:
                    continue
                if line == "<TOGGLE_TRIG>":
                    print("\n=======================================================")
                    print("🟢 ERFOLG: Button 1 (Pin 3) gedrückt! (Trigger Toggle)")
                    print("=======================================================")
                elif line == "<TOGGLE_REC>":
                    print("\n=======================================================")
                    print("🔴 ERFOLG: Button 2 (Pin 4) gedrückt! (Record Toggle)")
                    print("=======================================================")
                else:
                    print(f"[ARDUINO SAGT]: {line}")
        except Exception as e:
            print(f"Verbindungsfehler: {e}")
            break
        time.sleep(0.01)

def main():
    print("Suche Arduino...")
    port = get_arduino_port()
    if not port:
        print("Kein Arduino gefunden! Bitte USB-Verbindung prüfen.")
        return
        
    print(f"Verbinde mit Arduino an Port: {port}...")
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(2) # Warten auf Arduino Neustart nach Serial-Verbindung
    except Exception as e:
        print(f"Konnte nicht verbinden: {e}")
        return
        
    print("Verbindung erfolgreich!\n")
    
    # Thread zum Lesen starten
    thread = threading.Thread(target=read_from_port, args=(ser,), daemon=True)
    thread.start()
    
    print("--- TEST MENÜ ---")
    print("Drücke deine Hardware-Buttons, um zu sehen ob sie funktionieren!")
    print("Tippe 'ping' + ENTER, um die Verbindung zu testen.")
    print("Tippe 'start' + ENTER, um das Trigger-Signal an Pin 2 zu starten (LED 13 sollte leuchten).")
    print("Tippe 'stop' + ENTER, um das Trigger-Signal zu stoppen.")
    print("Tippe 'fps:60' + ENTER, um die Framerate zu ändern.")
    print("Tippe 'quit' + ENTER zum Beenden.")
    
    while True:
        try:
            cmd = input().strip().lower()
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "ping":
                ser.write(b"<PING>")
            elif cmd == "start":
                ser.write(b"<START>")
            elif cmd == "stop":
                ser.write(b"<STOP>")
            elif cmd.startswith("fps:"):
                val = cmd.split(":")[1]
                ser.write(f"<FPS:{val}>".encode('utf-8'))
        except KeyboardInterrupt:
            break

    ser.close()
    print("Test beendet.")

if __name__ == "__main__":
    main()
