/*
 * button_demo.ino - button-triggered sensor simulation for demo
 * arduino uno connected to rpi via usb serial
 * 
 * wiring: button between pin 2 and gnd (uses internal pullup)
 * press button -> triggers simulated sensor data -> rpi does pre + kyber
 */

// ---- config ----
#define BAUD_RATE 9600
#define MAX_MESSAGE_LEN 128
#define DEVICE_ID "ARDUINO_SENSOR_001"
#define DEBOUNCE_MS 300

// psk must match rpi gateway
const byte PSK[16] = {
  0x4B, 0x59, 0x42, 0x45, 0x52, 0x5F, 0x49, 0x4F,  // "KYBER_IO"
  0x54, 0x5F, 0x50, 0x53, 0x4B, 0x5F, 0x30, 0x31   // "T_PSK_01"
};

// ---- pins ----
const int BUTTON_PIN = 2;  // button between pin 2 and gnd

// ---- state ----
unsigned long lastButtonPress = 0;
unsigned long messageCounter = 0;
bool lastButtonState = HIGH;

// ---- simulated sensor values ----
float simTemp = 24.5;
float simHumidity = 55.0;
int simLight = 500;

void setup() {
  // init serial to rpi
  Serial.begin(BAUD_RATE);
  
  // wait for serial ready
  while (!Serial) {
    ;
  }
  
  // init button with internal pullup
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_BUILTIN, OUTPUT);
  
  // startup blink pattern (3 quick + 1 long)
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(100);
    digitalWrite(LED_BUILTIN, LOW);
    delay(100);
  }
  digitalWrite(LED_BUILTIN, HIGH);
  delay(500);
  digitalWrite(LED_BUILTIN, LOW);
  
  // send init msg
  Serial.println("# INIT: " DEVICE_ID " ready");
  Serial.println("# MODE: button-triggered demo");
  Serial.println("# WAITING: press button to send sensor data");
  
  delay(500);
}

void loop() {
  unsigned long now = millis();
  bool buttonState = digitalRead(BUTTON_PIN);
  
  // detect button press (falling edge w/ debounce)
  if (buttonState == LOW && lastButtonState == HIGH) {
    if (now - lastButtonPress > DEBOUNCE_MS) {
      lastButtonPress = now;
      
      // button pressed - trigger sensor data
      Serial.println("# BUTTON: pressed");
      sendSensorData();
    }
  }
  
  lastButtonState = buttonState;
  
  // handle cmds from rpi
  if (Serial.available() > 0) {
    handleIncoming();
  }
  
  delay(10);
}

void sendSensorData() {
  char msgBuffer[MAX_MESSAGE_LEN];
  
  // blink led during send
  digitalWrite(LED_BUILTIN, HIGH);
  
  // update simulated vals with small variations
  simTemp += random(-5, 6) / 10.0;
  simTemp = constrain(simTemp, 18.0, 32.0);
  
  simHumidity += random(-3, 4);
  simHumidity = constrain(simHumidity, 40.0, 75.0);
  
  simLight += random(-30, 31);
  simLight = constrain(simLight, 200, 800);
  
  // build json msg
  int msgLen = snprintf(msgBuffer, MAX_MESSAGE_LEN,
    "{\"id\":\"%s\",\"seq\":%lu,\"t\":%.1f,\"h\":%.1f,\"l\":%d,\"ts\":%lu}",
    DEVICE_ID, messageCounter, simTemp, simHumidity, simLight, millis()
  );
  
  // xor encrypt
  byte encrypted[MAX_MESSAGE_LEN];
  memcpy(encrypted, msgBuffer, msgLen);
  for (int i = 0; i < msgLen; i++) {
    encrypted[i] ^= PSK[i % 16];
  }
  
  // send as hex
  Serial.print("ENC:");
  for (int i = 0; i < msgLen; i++) {
    if (encrypted[i] < 16) Serial.print('0');
    Serial.print(encrypted[i], HEX);
  }
  Serial.println();
  
  digitalWrite(LED_BUILTIN, LOW);
  messageCounter++;
}

void handleIncoming() {
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  
  if (cmd == "PING") {
    Serial.println("PONG:" DEVICE_ID);
  }
  else if (cmd == "STATUS") {
    Serial.print("STATUS:");
    Serial.print(DEVICE_ID);
    Serial.print(",msgs:");
    Serial.print(messageCounter);
    Serial.print(",uptime:");
    Serial.println(millis());
  }
  else if (cmd == "TRIGGER") {
    // remote trigger from rpi (for testing)
    Serial.println("# REMOTE: trigger received");
    sendSensorData();
  }
}

/*
 * WIRING FOR DEMO:
 * 
 * Arduino UNO:
 *   - Pin 2 ----[BUTTON]---- GND
 *   - USB-B connected to Raspberry Pi USB port
 * 
 * That's it! No other components needed.
 * 
 * Button uses internal pullup, so:
 *   - Button open = HIGH (not pressed)
 *   - Button pressed = LOW (gnd connected)
 */

