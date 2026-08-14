#include <AccelStepper.h>

#define STEP_PIN 3
#define DIR_PIN 4

AccelStepper stepper(1, STEP_PIN, DIR_PIN);

void setup() {

  Serial.begin(9600);
  Serial.println("Stepper Position Control - Input:");

  stepper.setMaxSpeed(32);
  stepper.setAcceleration(1000);
  // stepper.setSpeed(32);
  
}


void loop() {

  stepper.runToPosition();

  if (Serial.available() > 0) {
    int newPos = Serial.parseFloat();   // read the entered number (RPM)
      if (newPos != 0){
        if (newPos == 9999) {newPos = 0;};
        stepper.moveTo(newPos);
        Serial.print("Set new Position to ");
        Serial.println(newPos);
      }   
    
  } 


} // end loop
