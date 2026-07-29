#include <ctype.h>
#include <math.h>
#include <stdlib.h>

// Stepper driver pin connections
const int stepPin = 8;
const int dirPin = 9;

// Motor/driver parameters.
// IMPORTANT: microsteps must match the physical driver's MS pin/DIP setting.
// The maintenance baseline uses full-step mode; set this to 16 only when the
// driver is physically configured for 1/16 microstepping.
const unsigned int microsteps = 1;
const unsigned int fullStepsPerRevolution = 200;
const unsigned long stepsPerRevolution =
    (unsigned long)fullStepsPerRevolution * microsteps;
const unsigned int pulseWidthMicros = 10;

double commandedRpm = 0.0;
unsigned long stepIntervalMicros = 0;
unsigned long nextStepMicros = 0;

char commandBuffer[24];
size_t commandLength = 0;


bool setRpm(double newRpm) {
  if (!isfinite(newRpm) || newRpm < 0.0) {
    Serial.println("ERR RPM must be a finite non-negative number");
    return false;
  }

  if (newRpm == 0.0) {
    commandedRpm = 0.0;
    stepIntervalMicros = 0;
    digitalWrite(stepPin, LOW);
    Serial.println("Set RPM = 0");
    return true;
  }

  const double stepsPerSecond =
      newRpm * (double)stepsPerRevolution / 60.0;
  const double requestedInterval = 1000000.0 / stepsPerSecond;

  if (requestedInterval <= pulseWidthMicros) {
    Serial.println("ERR requested RPM exceeds pulse timing limit");
    return false;
  }

  commandedRpm = newRpm;
  stepIntervalMicros = (unsigned long)(requestedInterval + 0.5);
  nextStepMicros = micros();

  Serial.print("Set RPM = ");
  Serial.println(commandedRpm, 3);
  return true;
}


void processCommand() {
  commandBuffer[commandLength] = '\0';

  char *endPointer = NULL;
  const double value = strtod(commandBuffer, &endPointer);

  while (endPointer != NULL && isspace(*endPointer)) {
    endPointer++;
  }

  if (endPointer == commandBuffer || endPointer == NULL || *endPointer != '\0') {
    Serial.println("ERR command must be '<rpm>'");
  } else {
    setRpm(value);
  }

  commandLength = 0;
}


void readSerialCommands() {
  while (Serial.available() > 0) {
    const char incoming = (char)Serial.read();

    if (incoming == '\n' || incoming == '\r') {
      if (commandLength > 0) {
        processCommand();
      }
      continue;
    }

    if (commandLength < sizeof(commandBuffer) - 1) {
      commandBuffer[commandLength++] = incoming;
    } else {
      commandLength = 0;
      Serial.println("ERR command too long");
    }
  }
}


void generateStepPulse() {
  if (commandedRpm <= 0.0 || stepIntervalMicros == 0) {
    return;
  }

  const unsigned long now = micros();
  if ((long)(now - nextStepMicros) < 0) {
    return;
  }

  digitalWrite(stepPin, HIGH);
  delayMicroseconds(pulseWidthMicros);
  digitalWrite(stepPin, LOW);

  // Schedule from the actual pulse time. This supports intervals much longer
  // than delayMicroseconds() and remains safe across micros() wrap-around.
  nextStepMicros = now + stepIntervalMicros;
}


void setup() {
  Serial.begin(9600);

  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
  digitalWrite(stepPin, LOW);
  digitalWrite(dirPin, HIGH);

  setRpm(0.0);
  Serial.print("Stepper ready; command unit=RPM; microsteps=");
  Serial.println(microsteps);
}


void loop() {
  readSerialCommands();
  generateStepPulse();
}
