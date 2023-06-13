// Pin Definitions
#define DATA_PIN 2
#define OBSERVATION_PIN 3

// Pulse durations with tolerance
const unsigned long PACKET_START_LOW_DURATION = 235;
const unsigned long PACKET_START_HIGH_DURATION = 53;
const unsigned long PACKET_START_END_DURATION = 90;
const unsigned long ZERO_BIT_DURATION = 90;
const unsigned long ONE_BIT_DURATION = 170;
const unsigned long NIBBLE_SEPARATION_DURATION = 100;
const unsigned long PACKET_SEPARATION_DURATION = 200;

// Sends a single bit via the Cube World protocol.
// The DATA_PIN must be in OUTPUT mode.
void sendBit(bool bit) {
  digitalWrite(DATA_PIN, LOW);
  digitalWrite(OBSERVATION_PIN, LOW);
  delayMicroseconds(bit ? ONE_BIT_DURATION : ZERO_BIT_DURATION);
  // The data is really contained in the low pulses so the length
  // of the high pulse shouldn't matter. 
  digitalWrite(DATA_PIN, HIGH);
  digitalWrite(OBSERVATION_PIN, HIGH);
}

// Sends a single nibble (4 bits) via the Cube World protocol.
// The DATA_PIN must be in OUTPUT mode.
// \param[in] nibble - The nibble to send, stored in the lower 4 bits
//.  of this integer.
void sendNibble(uint8_t nibble) {
  for (int i = 0; i < 4; i++) {
    bool current_bit = (nibble & 0x08) >> 3;
    sendBit(current_bit);
    if (i < 3) {
      delayMicroseconds(90);
    }
    nibble <<= 1;
  }
}

// Sends a single packet of data (7 nibbles / 28 bits) via the Cube World protocol.
// Sets the DATA_PIN to OUTPUT mode for as long as it takes to send the data, then
// resets the DATA_PIN to INPUT mode to receieve a response.
void sendPacket(uint8_t packet[7]) {
  // SIGNAL THE START OF THE PACKET.
  delayMicroseconds(100);
  pinMode(DATA_PIN, OUTPUT);
  pinMode(OBSERVATION_PIN, OUTPUT);
  
  // SEND THE DATA.
 for (int i = 0; i < 7; i++) {
    sendNibble(packet[i] & 0x0F);

    if (i == 6) {
      digitalWrite(DATA_PIN, HIGH);
      digitalWrite(OBSERVATION_PIN, HIGH);
      delayMicroseconds(37);
    } else if (i == 5) {
      delayMicroseconds(90);
    } else {
      digitalWrite(DATA_PIN, HIGH);
      digitalWrite(OBSERVATION_PIN, HIGH);
      delayMicroseconds(200);
    }
  }
  
  // SIGNAL THE END OF PACKET.
  // TODO: Which device sends this?
  digitalWrite(DATA_PIN, LOW);
  digitalWrite(OBSERVATION_PIN, LOW);
  delayMicroseconds(85);
  pinMode(DATA_PIN, INPUT);
  pinMode(OBSERVATION_PIN, INPUT);
}

// Checks if another cube is listening.

bool pollForCube() {
  pinMode(DATA_PIN, OUTPUT);
  pinMode(OBSERVATION_PIN, OUTPUT);

  digitalWrite(DATA_PIN, LOW);
  digitalWrite(OBSERVATION_PIN, LOW);
  delayMicroseconds(230);

  pinMode(DATA_PIN, INPUT);
  pinMode(OBSERVATION_PIN, INPUT);

  bool pin_pulled_high = pulseIn(DATA_PIN, LOW, 1000) > 0;
  if (pin_pulled_high) {
    return true;
  } else {
    return false;
  }
}

bool readPacket() {
  bool packetStart = false;
  unsigned long packetData = 0;
  int bitCount = 0;

  // Look for the start of packet sequence
  unsigned long pulseDuration = pulseIn(DATA_PIN, LOW);
  if (pulseDuration >= 200 && pulseDuration <= 300) {
    pulseDuration = pulseIn(DATA_PIN, LOW);
    if (pulseDuration >= 80 && pulseDuration <= 100) {
      packetStart = true;
    }
  }

  if (!packetStart) {
    return false;  // Failed to find the start of packet sequence
  }

  // Read the packet data
  while (bitCount < 28) {  // Assuming each packet contains 7 nibbles (28 bits)
    unsigned long pulseDuration = pulseIn(DATA_PIN, LOW);

    if (pulseDuration <= 150) {
      // Received a 0 bit
      packetData = (packetData << 1);  // Shift left by 1 bit
      bitCount++;
    } else if (pulseDuration > 150) {
      // Received a 1 bit
      packetData = (packetData << 1) | 0x01;  // Shift left by 1 bit and set LSB to 1
      bitCount++;
    } else {
      // Invalid bit duration, discard packet
      return false;
    }
  }

  // Successfully read the packet, send the data over serial
  Serial.println(packetData, HEX);

  return true;
}

void setup() {
  Serial.begin(9600);
  pinMode(DATA_PIN, INPUT);
  pinMode(OBSERVATION_PIN, INPUT);
}

void loop() {
  if (pollForCube()) {
    // TODO: Is each packet truly sent by a single device?
    uint8_t packet[7] = {0x1, 0x7, 0x1, 0x6, 0x1, 0x1, 0x9};
    sendPacket(packet);
    //Serial.println("found");
  }
  delay(1000);
}

  //if (readPacket()) {  // Read a complete packet
    // Process the packet data
    // You can modify this section to perform actions based on the received data
    // For example, you can check specific values, convert data, etc.
  //}