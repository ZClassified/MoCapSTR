const int TRIGGER_PIN = 2; // Pin connected to FSIN of cameras
const int BTN_REC_PIN = 4;  // Push button to toggle record
const int LED_PIN = 13;    // Onboard LED for visual feedback

bool isRunning = false;
int currentFps = 60;
unsigned long intervalMicros = 1000000 / currentFps;
unsigned long previousMicros = 0;
unsigned long pulseWidthMicros = 1000; // 1ms Puls (= ~1/1000s Belichtung). Per <PULSE:N> Befehl live änderbar.

String inputString = "";
bool stringComplete = false;

// Button state variables
bool lastBtnRecState = HIGH;
unsigned long lastDebounceTimeRec = 0;
const unsigned long debounceDelay = 50; // 50ms debounce

void setup() {
  pinMode(TRIGGER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(TRIGGER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
  
  pinMode(BTN_REC_PIN, INPUT_PULLUP);
  
  Serial.begin(115200);
  inputString.reserve(50);
  
  Serial.println("OV9281 Sync Trigger Ready");
}

void loop() {
  // Handle Buttons
  bool currentBtnRec = digitalRead(BTN_REC_PIN);

  if (currentBtnRec != lastBtnRecState) {
    if (millis() - lastDebounceTimeRec > debounceDelay) {
      lastDebounceTimeRec = millis();
      lastBtnRecState = currentBtnRec;
      if (currentBtnRec == LOW) { // Button pressed (pulled to GND)
        Serial.println("<TOGGLE_REC>");
      }
    }
  }

  // Handle Serial Commands
  if (stringComplete) {
    inputString.trim();
    if (inputString.startsWith("<FPS:")) {
      int fpsIndex = inputString.indexOf(":");
      int endBracketIndex = inputString.indexOf(">");
      if (fpsIndex != -1 && endBracketIndex != -1) {
        String fpsStr = inputString.substring(fpsIndex + 1, endBracketIndex);
        int newFps = fpsStr.toInt();
        if (newFps > 0 && newFps <= 240) {
          currentFps = newFps;
          intervalMicros = 1000000UL / currentFps;
          Serial.print("FPS set to: ");
          Serial.println(currentFps);
          Serial.print("Interval (us): ");
          Serial.println(intervalMicros);
          Serial.print("Pulse width (us): ");
          Serial.println(pulseWidthMicros);
        } else {
          Serial.println("Error: FPS out of range (1-240)");
        }
      }
    } else if (inputString.startsWith("<PULSE:")) {
      int pulseIndex = inputString.indexOf(":");
      int endBracketIndex = inputString.indexOf(">");
      if (pulseIndex != -1 && endBracketIndex != -1) {
        String pulseStr = inputString.substring(pulseIndex + 1, endBracketIndex);
        unsigned long newPulse = pulseStr.toInt();
        if (newPulse > 0 && newPulse < intervalMicros / 2) {
          pulseWidthMicros = newPulse;
          Serial.print("Pulse width set to (us): ");
          Serial.println(pulseWidthMicros);
        } else {
          Serial.println("Error: Pulse must be > 0 and < interval/2");
        }
      }
    } else if (inputString == "<START>") {
      isRunning = true;
      previousMicros = micros();
      Serial.println("Trigger STARTED");
    } else if (inputString == "<STOP>") {
      isRunning = false;
      digitalWrite(TRIGGER_PIN, LOW);
      digitalWrite(LED_PIN, LOW);
      Serial.println("Trigger STOPPED");
    } else if (inputString == "<PING>") {
      Serial.println("PONG");
    } else {
      Serial.println("Error: Unknown command");
    }
    
    inputString = "";
    stringComplete = false;
  }

  // Generate Trigger Pulse
  if (isRunning) {
    unsigned long currentMicros = micros();
    
    if (currentMicros - previousMicros >= intervalMicros) {
      // WICHTIG: += statt = verhindert Timing-Drift.
      // Mit = würde jeder Puls (pulseWidthMicros) zu einem kumulativen Fehler führen.
      previousMicros += intervalMicros;
      
      // Start pulse
      digitalWrite(TRIGGER_PIN, HIGH);
      digitalWrite(LED_PIN, HIGH);
      
      // Blocking wait for pulse width.
      // pulseWidthMicros MUSS deutlich kleiner als intervalMicros sein!
      // Bei 120 FPS: intervalMicros = 8333µs -> 500µs Puls ist sicher.
      delayMicroseconds(pulseWidthMicros);
      
      // End pulse
      digitalWrite(TRIGGER_PIN, LOW);
      digitalWrite(LED_PIN, LOW);
    }
  }
}

void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    inputString += inChar;
    if (inChar == '>') {
      stringComplete = true;
    }
  }
}
