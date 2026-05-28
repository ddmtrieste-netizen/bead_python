#include <AccelStepper.h>

#define STEP_PIN 3
#define DIR_PIN 4

AccelStepper stepper(1, STEP_PIN, DIR_PIN);

void setup() {

  Serial.begin(9600);
  Serial.println("Stepper Speed Control - Enter RPM:");

  stepper.setMaxSpeed(32);
  stepper.setSpeed(32);
  
}


void loop() {

  stepper.runSpeed();

  if (Serial.available() > 0) {
    int newSpeed = Serial.parseInt();   // read the entered number (RPM)

    if (newSpeed > 0) {                // ensure it's non-negative
      stepper.setSpeed(newSpeed);
      Serial.print("Set new speed to ");
      Serial.println(newSpeed);
    }
  } 


} // end loop
