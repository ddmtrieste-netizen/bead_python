#include <AccelStepper.h>
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define STEP_PIN 3
#define DIR_PIN 4

// Units used by AccelStepper:
//   speed        = step pulses / second
//   acceleration = step pulses / second^2
//   position     = absolute step pulses since startup
const float MAX_SPEED = 200.0;
const float ACCELERATION = 50.0;
const float INITIAL_SPEED = 32.0;
const float FINAL_APPROACH_SPEED = 2.0;

AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

enum ControlMode {
  SPEED_MODE,
  POSITION_MODE,
};

// selectedMode says how the next number will be interpreted. activeMode says
// which algorithm is currently moving the motor. Selecting a word therefore
// never interrupts the current motion.
ControlMode selectedMode = SPEED_MODE;
ControlMode activeMode = SPEED_MODE;

float currentSpeed = INITIAL_SPEED;
float targetSpeed = INITIAL_SPEED;
long requestedPosition = 0;
unsigned long lastRampMicros = 0;

char commandBuffer[32];
size_t commandLength = 0;


const char *modeName(ControlMode mode) {
  return mode == SPEED_MODE ? "SPEED" : "POSITION";
}


void printHelp() {
  Serial.println("Commands (one per line):");
  Serial.println("  SPEED       next number is speed [steps/s]");
  Serial.println("  POSITION    next integer is absolute position [steps]");
  Serial.println("  STOP        smooth stop");
  Serial.println("  HOME        smooth move to absolute position 0");
  Serial.println("  STATUS      print current state");
  Serial.println("  HELP        print this help");
}


void printStatus() {
  Serial.print("Selected mode: ");
  Serial.println(modeName(selectedMode));
  Serial.print("Active mode: ");
  Serial.println(modeName(activeMode));
  Serial.print("Current position [steps]: ");
  Serial.println(stepper.currentPosition());
  Serial.print("Target position [steps]: ");
  Serial.println(requestedPosition);
  Serial.print("Current speed [steps/s]: ");
  Serial.println(stepper.speed(), 3);
  Serial.print("Target speed [steps/s]: ");
  Serial.println(targetSpeed, 3);
}


void startSpeedCommand(float newSpeed) {
  if (!isfinite(newSpeed) || fabs(newSpeed) > MAX_SPEED) {
    Serial.print("ERR speed must be between ");
    Serial.print(-MAX_SPEED, 3);
    Serial.print(" and ");
    Serial.print(MAX_SPEED, 3);
    Serial.println(" steps/s");
    return;
  }

  // Preserve the instantaneous speed when leaving position mode. The ramp
  // starts there, rather than stopping and restarting from zero.
  currentSpeed = stepper.speed();
  targetSpeed = newSpeed;
  activeMode = SPEED_MODE;
  lastRampMicros = micros();

  Serial.print("Target speed [steps/s] = ");
  Serial.println(targetSpeed, 3);
}


void startPositionCommand(long newPosition) {
  // Do not call moveTo() here: it immediately recalculates AccelStepper's
  // internal position-profile speed. Both modes instead share the same
  // currentSpeed and the same non-blocking runSpeed() pulse generator.
  requestedPosition = newPosition;
  activeMode = POSITION_MODE;

  Serial.print("Target position [steps] = ");
  Serial.println(newPosition);
}


void smoothStop() {
  // Continue using the common ramp, whatever mode was active.
  activeMode = SPEED_MODE;
  targetSpeed = 0.0;
  Serial.println("Smooth stop requested");
}


bool parseSpeed(const char *text, float *value) {
  char *endPointer = NULL;
  const double parsed = strtod(text, &endPointer);
  while (endPointer != NULL && isspace(*endPointer)) {
    endPointer++;
  }
  if (endPointer == text || endPointer == NULL || *endPointer != '\0' ||
      !isfinite(parsed)) {
    return false;
  }
  *value = (float)parsed;
  return true;
}


bool parsePosition(const char *text, long *value) {
  char *endPointer = NULL;
  const long parsed = strtol(text, &endPointer, 10);
  while (endPointer != NULL && isspace(*endPointer)) {
    endPointer++;
  }
  if (endPointer == text || endPointer == NULL || *endPointer != '\0') {
    return false;
  }
  *value = parsed;
  return true;
}


void processCommand() {
  commandBuffer[commandLength] = '\0';

  char *command = commandBuffer;
  while (isspace(*command)) {
    command++;
  }
  char *last = command + strlen(command);
  while (last > command && isspace(*(last - 1))) {
    last--;
  }
  *last = '\0';

  for (char *character = command; *character != '\0'; character++) {
    *character = (char)toupper(*character);
  }

  if (strcmp(command, "SPEED") == 0) {
    selectedMode = SPEED_MODE;
    Serial.println("Selected SPEED mode; enter speed [steps/s]");
  } else if (strcmp(command, "POSITION") == 0) {
    selectedMode = POSITION_MODE;
    Serial.println("Selected POSITION mode; enter absolute position [steps]");
  } else if (strcmp(command, "STOP") == 0) {
    smoothStop();
  } else if (strcmp(command, "HOME") == 0) {
    selectedMode = POSITION_MODE;
    startPositionCommand(0);
  } else if (strcmp(command, "STATUS") == 0) {
    printStatus();
  } else if (strcmp(command, "HELP") == 0) {
    printHelp();
  } else if (selectedMode == SPEED_MODE) {
    float newSpeed = 0.0;
    if (parseSpeed(command, &newSpeed)) {
      startSpeedCommand(newSpeed);
    } else {
      Serial.println("ERR enter SPEED, POSITION, or a valid number");
    }
  } else {
    long newPosition = 0;
    if (parsePosition(command, &newPosition)) {
      startPositionCommand(newPosition);
    } else {
      Serial.println("ERR position must be an integer number of steps");
    }
  }

  commandLength = 0;
}


void readSerialCommandsWithoutBlocking() {
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


void updateSpeedRamp() {
  const unsigned long now = micros();
  const float elapsedSeconds = (now - lastRampMicros) / 1000000.0;
  lastRampMicros = now;

  const float maximumChange = ACCELERATION * elapsedSeconds;
  const float difference = targetSpeed - currentSpeed;

  if (fabs(difference) <= maximumChange) {
    currentSpeed = targetSpeed;
  } else if (difference > 0.0) {
    currentSpeed += maximumChange;
  } else {
    currentSpeed -= maximumChange;
  }

  stepper.setSpeed(currentSpeed);
}


void updatePositionTargetSpeed() {
  const long distance = requestedPosition - stepper.currentPosition();
  if (distance == 0) {
    targetSpeed = 0.0;
    return;
  }

  // v^2 = 2*a*d: this is the highest speed from which the remaining
  // distance can still be covered while braking at ACCELERATION.
  const float brakingDistance = max(0.0, (double)labs(distance) - 1.0);
  float allowedSpeed = sqrt(2.0 * ACCELERATION * brakingDistance);
  allowedSpeed = constrain(allowedSpeed, FINAL_APPROACH_SPEED, MAX_SPEED);
  targetSpeed = distance > 0 ? allowedSpeed : -allowedSpeed;
}


void updateMotor() {
  if (activeMode == POSITION_MODE) {
    updatePositionTargetSpeed();
  }

  updateSpeedRamp();
  const bool stepped = stepper.runSpeed();

  // Stop on the exact requested step. The approach is already down to
  // FINAL_APPROACH_SPEED, so this final stop is mechanically gentle and cannot
  // overshoot by an additional pulse.
  if (activeMode == POSITION_MODE && stepped &&
      stepper.currentPosition() == requestedPosition) {
    currentSpeed = 0.0;
    targetSpeed = 0.0;
    stepper.setSpeed(0.0);
  }
}


void setup() {
  Serial.begin(9600);

  stepper.setMaxSpeed(MAX_SPEED);
  stepper.setAcceleration(ACCELERATION);
  stepper.setMinPulseWidth(10);
  stepper.setSpeed(INITIAL_SPEED);
  lastRampMicros = micros();

  Serial.println("Stepper ready");
  printHelp();
  printStatus();
}


void loop() {
  readSerialCommandsWithoutBlocking();
  updateMotor();
}
