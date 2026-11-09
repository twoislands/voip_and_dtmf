#include <Arduino.h>
#include <RPC.h>

int handleDigit(int digit) {
  // Bench test: the remote caller presses *, and the unit sends 5.
  // Add application actions for other validated digits here.
  if (digit == '*') {
    return '5';
  }
  return 0;
}

void setup() {
  RPC.begin();
  RPC.bind("dtmf_received", handleDigit);
}

void loop() {
  delay(20);
}
