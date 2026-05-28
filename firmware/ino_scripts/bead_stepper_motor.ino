// Define pin connections
const int stepPin = 8;       // Arduino pin for STEP pulse
const int dirPin  = 9;       // Arduino pin for DIRECTION
// (Optional) const int enaPin  = 4;    // Arduino pin for ENABLE, if used

// Motor/driver parameters
const int microsteps = 1;        // microstepping setting (1/16)
const int stepsPerRev = 200;      // full steps per revolution for NEMA 17 (1.8° step)
const int stepsPerRevMicro = stepsPerRev * microsteps;  // = 3200 steps/rev @1/16

int rpm = 0;                      // current speed in RPM (0 = stop)
unsigned long stepDelayMicros = 0; // delay between step pulses in microseconds
const int pulseWidthMicros = 10;   // pulse width for step signal (microseconds)

void setup() {
  Serial.begin(9600);
  Serial.println("Stepper Speed Control - Enter RPM:");

  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
  // pinMode(enaPin, OUTPUT);  // if using enable
  digitalWrite(dirPin, HIGH);    // set direction (HIGH or LOW). Only one direction used.
  // digitalWrite(enaPin, HIGH); // enable driver (if ENA active low, HIGH keeps it enabled)

  // Start with motor stopped (rpm=0)
  rpm = 0;
  stepDelayMicros = 0;
}

void loop() {
  // Check for user input from serial
  if (Serial.available() > 0) {
    int newSpeed = Serial.parseInt();   // read the entered number (RPM)
    if (newSpeed >= 0) {                // ensure it's non-negative
      rpm = newSpeed;
      if (rpm > 0) {
        // Calculate delay between steps in microseconds for the given RPM
        float stepsPerSec = (rpm * (float)stepsPerRevMicro) / 60.0;
        stepDelayMicros = (unsigned long)(1000000.0 / stepsPerSec);
      } else {
        stepDelayMicros = 0;  // rpm = 0, motor stopped
      }
      Serial.print("Set RPM = ");
      Serial.println(rpm);
    }
    // Clear any leftover input
    Serial.flush();
  }

  // If RPM is set (non-zero), generate step pulses at the calculated interval
  if (rpm > 0 && stepDelayMicros > 0) {
    // Step pulse HIGH
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(pulseWidthMicros);       // short pulse to meet driver requirements
    // Step pulse LOW
    digitalWrite(stepPin, LOW);
    // Wait for the rest of the step period
    delayMicroseconds(stepDelayMicros - pulseWidthMicros);
    // (Using delayMicroseconds for fine resolution. For very long delays >16383 μs, use delay().)
  } 
  else {
    // Motor is stopped; small delay to avoid busy-waiting
    delay(10);
  }
}
