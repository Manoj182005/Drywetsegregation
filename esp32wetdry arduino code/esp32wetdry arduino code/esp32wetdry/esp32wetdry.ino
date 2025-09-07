#include <WiFi.h>
#include <HTTPClient.h>
#include <NewPing.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// WiFi credentials
const char* ssid = "Shivp";        
const char* password = "ujwal312004"; 
const char* serverUrl = "http://10.48.165.233:5000/classify"; 

// Ultrasonic and Servo
#define TRIGGER_PIN  15  
#define ECHO_PIN     14  
#define SERVO_PIN    16  
#define MAX_DISTANCE 200 

NewPing sonar(TRIGGER_PIN, ECHO_PIN, MAX_DISTANCE);
Servo myservo;

// LCD (16x2 I2C, address 0x27)
LiquidCrystal_I2C lcd(0x27, 16, 2);

void setup() {
  Serial.begin(115200);

  // LCD init
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Smart Dustbin");
  lcd.setCursor(0, 1);
  lcd.print("Connecting WiFi");

  // WiFi connect
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi");
  Serial.println(WiFi.localIP());

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("WiFi Connected");
  lcd.setCursor(0, 1);
  lcd.print(WiFi.localIP().toString());

  // Servo init
  myservo.attach(SERVO_PIN);
  myservo.write(90); 
}

void loop() {
  unsigned int distance = sonar.ping_cm();

  if (distance > 0 && distance < 5) { // Object detected
    delay(2000);

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(serverUrl);
      int httpCode = http.GET();

      if (httpCode == HTTP_CODE_OK) {
        String classification = http.getString();
        classification.trim();  // remove any spaces or newline

        Serial.print("Classification: ");
        Serial.println(classification);

        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("Waste Detected:");

        if (classification == "dry") {
          myservo.write(160);
          lcd.setCursor(0, 1);
          lcd.print("Dry Waste");
          delay(2000);
        } 
        else if (classification == "wet") {
          myservo.write(20);
          lcd.setCursor(0, 1);
          lcd.print("Wet Waste");
          delay(2000);
        } 
        else {
          lcd.setCursor(0, 1);
          lcd.print("Unknown");
        }
      } else {
        Serial.println("HTTP request failed");
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("Server Error");
      }
      http.end();
    }

    myservo.write(90);
    delay(5000);
  }