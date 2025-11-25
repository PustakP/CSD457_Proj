/*
 * iot_sensor.ino - constrained iot device simulation
 * arduino uno sends sensor data to fog gateway (raspberry pi)
 * 
 * architecture: arduino --[serial]--> rpi fog gateway --[pre]--> cloud
 * 
 * note: arduino uno (2kb sram, 32kb flash) too constrained for kyber
 * so we use lightweight xor enc with psk for device-side protection
 * real security comes from kyber at fog gateway
 */

// ---- config ----
#define BAUD_RATE 9600
#define SENSOR_INTERVAL_MS 5000    // send data every 5 sec
#define MAX_MESSAGE_LEN 128
#define DEVICE_ID "ARDUINO_IOT_001"

// pre-shared key for lightweight enc (shared with gateway)
// in production: use secure provisioning
const byte PSK[16] = {
  0x4B, 0x59, 0x42, 0x45, 0x52, 0x5F, 0x49, 0x4F,  // "KYBER_IO"
  0x54, 0x5F, 0x50, 0x53, 0x4B, 0x5F, 0x30, 0x31   // "T_PSK_01"
};

// ---- simulated sensor pins ----
// if using real sensors, connect to these pins
const int TEMP_SENSOR_PIN = A0;     // analog temp sensor (or pot for sim)
const int HUMIDITY_PIN = A1;        // analog humidity (or pot for sim)
const int LIGHT_SENSOR_PIN = A2;    // photoresistor
const int BUTTON_PIN = 2;           // manual trigger button

// ---- state vars ----
unsigned long lastSendTime = 0;
unsigned long messageCounter = 0;
bool buttonPressed = false;

// ---- function prototypes ----
void readSensors(float &temp, float &humidity, int &light);
void encryptAndSend(const char* data, int len);
void xorEncrypt(byte* data, int len);
int buildMessage(char* buffer, float temp, float humidity, int light);

void setup() {
  // init serial to rpi
  Serial.begin(BAUD_RATE);
  
  // wait for serial ready
  while (!Serial) {
    ; // wait (needed for native usb)
  }
  
  // init pins
  pinMode(TEMP_SENSOR_PIN, INPUT);
  pinMode(HUMIDITY_PIN, INPUT);
  pinMode(LIGHT_SENSOR_PIN, INPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_BUILTIN, OUTPUT);
  
  // startup blink
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(100);
    digitalWrite(LED_BUILTIN, LOW);
    delay(100);
  }
  
  // send init msg
  Serial.println("# INIT: " DEVICE_ID " online");
  delay(1000);
}

void loop() {
  unsigned long now = millis();
  
  // check button for manual trigger
  if (digitalRead(BUTTON_PIN) == LOW && !buttonPressed) {
    buttonPressed = true;
    sendSensorData();
    delay(200);  // debounce
  }
  if (digitalRead(BUTTON_PIN) == HIGH) {
    buttonPressed = false;
  }
  
  // periodic send
  if (now - lastSendTime >= SENSOR_INTERVAL_MS) {
    lastSendTime = now;
    sendSensorData();
  }
  
  // check for cmds from gateway
  if (Serial.available() > 0) {
    handleIncoming();
  }
  
  delay(10);
}

void sendSensorData() {
  float temp, humidity;
  int light;
  char msgBuffer[MAX_MESSAGE_LEN];
  
  // read sensors
  readSensors(temp, humidity, light);
  
  // build json-like msg
  int msgLen = buildMessage(msgBuffer, temp, humidity, light);
  
  // blink led to indicate send
  digitalWrite(LED_BUILTIN, HIGH);
  
  // encrypt and send
  encryptAndSend(msgBuffer, msgLen);
  
  digitalWrite(LED_BUILTIN, LOW);
  
  messageCounter++;
}

void readSensors(float &temp, float &humidity, int &light) {
  /*
   * sensor reading - can use real sensors or simulate
   * for demo: using analog pins with potentiometers or
   * generating simulated values if nothing connected
   */
  
  // read analog vals (0-1023)
  int tempRaw = analogRead(TEMP_SENSOR_PIN);
  int humidRaw = analogRead(HUMIDITY_PIN);
  int lightRaw = analogRead(LIGHT_SENSOR_PIN);
  
  // convert to realistic values
  // temp: map 0-1023 to -10 to 50 celsius
  temp = map(tempRaw, 0, 1023, -100, 500) / 10.0;
  
  // humidity: map 0-1023 to 0-100%
  humidity = map(humidRaw, 0, 1023, 0, 100);
  
  // light: keep as lux approximation
  light = map(lightRaw, 0, 1023, 0, 1000);
  
  // if pins floating (no sensors), generate simulated data
  // detect floating by checking if readings are noisy/mid-range
  static float simTemp = 22.0;
  static float simHumid = 55.0;
  static int simLight = 500;
  
  // simple noise detection - if readings cluster around 512 with variation
  bool maybeFloating = (tempRaw > 400 && tempRaw < 600);
  
  if (maybeFloating) {
    // use simulated values with small variations
    simTemp += random(-10, 11) / 10.0;
    simTemp = constrain(simTemp, 15.0, 35.0);
    
    simHumid += random(-20, 21) / 10.0;
    simHumid = constrain(simHumid, 30.0, 80.0);
    
    simLight += random(-50, 51);
    simLight = constrain(simLight, 100, 900);
    
    temp = simTemp;
    humidity = simHumid;
    light = simLight;
  }
}

int buildMessage(char* buffer, float temp, float humidity, int light) {
  /*
   * build json-style sensor payload
   * format: {"id":"xxx","seq":n,"t":xx.x,"h":xx.x,"l":xxx,"ts":xxx}
   */
  return snprintf(buffer, MAX_MESSAGE_LEN,
    "{\"id\":\"%s\",\"seq\":%lu,\"t\":%.1f,\"h\":%.1f,\"l\":%d,\"ts\":%lu}",
    DEVICE_ID, messageCounter, temp, humidity, light, millis()
  );
}

void xorEncrypt(byte* data, int len) {
  /*
   * lightweight xor enc with psk
   * simple but provides basic confidentiality for wire
   * real sec from kyber at gateway
   */
  for (int i = 0; i < len; i++) {
    data[i] ^= PSK[i % 16];
  }
}

void encryptAndSend(const char* data, int len) {
  /*
   * encrypt data and send over serial
   * format: ENC:<base64_of_encrypted_data>\n
   */
  byte encrypted[MAX_MESSAGE_LEN];
  memcpy(encrypted, data, len);
  
  // xor encrypt
  xorEncrypt(encrypted, len);
  
  // send as hex (simpler than base64 for arduino)
  Serial.print("ENC:");
  for (int i = 0; i < len; i++) {
    if (encrypted[i] < 16) Serial.print('0');
    Serial.print(encrypted[i], HEX);
  }
  Serial.println();
}

void handleIncoming() {
  /*
   * handle commands from gateway
   * supported: PING, CONFIG, ACK
   */
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  
  if (cmd == "PING") {
    Serial.println("PONG:" DEVICE_ID);
  }
  else if (cmd.startsWith("CONFIG:")) {
    // parse config update (e.g., interval)
    String cfg = cmd.substring(7);
    if (cfg.startsWith("INTERVAL:")) {
      // could update SENSOR_INTERVAL_MS here
      Serial.println("ACK:CONFIG");
    }
  }
  else if (cmd == "STATUS") {
    Serial.print("STATUS:");
    Serial.print(DEVICE_ID);
    Serial.print(",msgs:");
    Serial.print(messageCounter);
    Serial.print(",uptime:");
    Serial.println(millis());
  }
}

/* 
 * wiring diagram for real sensors:
 * 
 * TEMP (TMP36):     VCC--[TMP36]--GND, OUT-->A0
 * HUMIDITY (DHT11): VCC--[DHT11]--GND, DATA-->A1 (needs lib)
 * LIGHT (LDR):      VCC--[LDR]--A2--[10k]--GND
 * BUTTON:           PIN2--[BTN]--GND (internal pullup)
 * 
 * for simulation: use potentiometers on A0, A1, A2
 * or just let pins float for auto-simulated data
 */



