/*
  Gait Measurement Prototype
  Hardware:
  - ESP32-WROOM
  - 2x BNO055 (0x28 thigh, 0x29 calf)
  - Calibration Button GPIO4 -> GND
  - Common Cathode RGB
      R=25 G=26 B=27
*/

#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>

#define BUTTON_PIN 4
#define RED_PIN 25
#define GREEN_PIN 26
#define BLUE_PIN 27

Adafruit_BNO055 thigh(55,0x28);
Adafruit_BNO055 calf(56,0x29);

float thighOffset=0;
float calfOffset=0;

bool calibrated=false;
int steps=0;
bool peak=false;
unsigned long lastStep=0;

void rgb(bool r,bool g,bool b){
  digitalWrite(RED_PIN,r);
  digitalWrite(GREEN_PIN,g);
  digitalWrite(BLUE_PIN,b);
}

void calibrate(){
  rgb(1,1,0); // yellow

  imu::Vector<3> t=thigh.getVector(Adafruit_BNO055::VECTOR_EULER);
  imu::Vector<3> c=calf.getVector(Adafruit_BNO055::VECTOR_EULER);

  thighOffset=t.z();
  calfOffset=c.z();

  calibrated=true;

  Serial.println("\n===== CALIBRATION COMPLETE =====");
  Serial.print("Thigh Offset : ");Serial.println(thighOffset);
  Serial.print("Calf Offset  : ");Serial.println(calfOffset);

  rgb(0,1,0); // green
}

void setup(){

  Serial.begin(115200);

  Wire.begin(21,22);

  pinMode(BUTTON_PIN,INPUT_PULLUP);

  pinMode(RED_PIN,OUTPUT);
  pinMode(GREEN_PIN,OUTPUT);
  pinMode(BLUE_PIN,OUTPUT);

  rgb(0,0,1); // blue boot

  if(!thigh.begin()){
    Serial.println("Thigh sensor failed");
    rgb(1,0,0);
    while(1);
  }

  if(!calf.begin()){
    Serial.println("Calf sensor failed");
    rgb(1,0,0);
    while(1);
  }

  thigh.setExtCrystalUse(true);
  calf.setExtCrystalUse(true);

  Serial.println("Press Calibration Button while standing straight.");
}

void loop(){

  if(digitalRead(BUTTON_PIN)==LOW){
    delay(30);
    if(digitalRead(BUTTON_PIN)==LOW){
      calibrate();
      while(digitalRead(BUTTON_PIN)==LOW);
    }
  }

  imu::Vector<3> t=thigh.getVector(Adafruit_BNO055::VECTOR_EULER);
  imu::Vector<3> c=calf.getVector(Adafruit_BNO055::VECTOR_EULER);

  imu::Vector<3> tg=thigh.getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);
  imu::Vector<3> cg=calf.getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);

  imu::Vector<3> ta=thigh.getVector(Adafruit_BNO055::VECTOR_ACCELEROMETER);
  imu::Vector<3> ca=calf.getVector(Adafruit_BNO055::VECTOR_ACCELEROMETER);

  float thighPitch=t.z()-thighOffset;
  float calfPitch=c.z()-calfOffset;
  float knee=abs(calfPitch-thighPitch);

  // simple demo step detection
  if(calibrated){
    if(knee>35 && !peak){
      peak=true;
    }
    if(knee<15 && peak){
      peak=false;
      steps++;
      lastStep=millis();
    }
  }

  float cadence=0;
  static unsigned long firstStep=0;
  if(steps==1) firstStep=lastStep;
  if(steps>1){
    float mins=(millis()-firstStep)/60000.0;
    if(mins>0) cadence=steps/mins;
  }

  Serial.println("========================================");
  Serial.print("Thigh Roll : ");Serial.println(t.y());
  Serial.print("Thigh Pitch: ");Serial.println(thighPitch);
  Serial.print("Thigh Yaw  : ");Serial.println(t.x());

  Serial.print("Calf Roll  : ");Serial.println(c.y());
  Serial.print("Calf Pitch : ");Serial.println(calfPitch);
  Serial.print("Calf Yaw   : ");Serial.println(c.x());

  Serial.print("Knee Angle : ");Serial.println(knee);

  Serial.print("Thigh Acc : ");
  Serial.print(ta.x());Serial.print(",");
  Serial.print(ta.y());Serial.print(",");
  Serial.println(ta.z());

  Serial.print("Calf Acc : ");
  Serial.print(ca.x());Serial.print(",");
  Serial.print(ca.y());Serial.print(",");
  Serial.println(ca.z());

  Serial.print("Thigh Gyro : ");
  Serial.print(tg.x());Serial.print(",");
  Serial.print(tg.y());Serial.print(",");
  Serial.println(tg.z());

  Serial.print("Calf Gyro : ");
  Serial.print(cg.x());Serial.print(",");
  Serial.print(cg.y());Serial.print(",");
  Serial.println(cg.z());

  Serial.print("Steps : ");Serial.println(steps);
  Serial.print("Cadence (steps/min): ");Serial.println(cadence);

  if(calibrated){
    if(knee<10) Serial.println("State : Standing");
    else if(knee<35) Serial.println("State : Walking");
    else Serial.println("State : Knee Flexion");
  }else{
    Serial.println("State : NOT CALIBRATED");
  }

  delay(100);
}
