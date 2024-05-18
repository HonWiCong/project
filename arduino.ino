#include <Servo.h>
#include "DHT.h"

int mode = 0;

// DHT11 Temperature and humidity
DHT dht;
int DHTPin = 5;

// Servo motor
Servo myServo;
int servoPin = 3;

// Sharp IR Sensor
int IRInPin = A2;
int IROutPin = A1;

// Act as the dust sensor
int potentiometerPin = A0;

int fanPin = 11;
int LEDPin = 8;

int petCounter = 0;
bool sensorIn = false;
bool sensorOut = false;

void setup()
{
	dht.setup(DHTPin);
	myServo.attach(servoPin);
	pinMode(potentiometerPin, INPUT);

	pinMode(fanPin, OUTPUT);
	pinMode(LEDPin, OUTPUT);

	Serial.begin(9600);
}

void loop()
{
	// Read IR sensor values
	float voltsIn = analogRead(IRInPin) * 0.0048828125; // value from sensor * (5/1024)
	float voltsOut = analogRead(IROutPin) * 0.0048828125;
	int IRIn = 13 * pow(voltsIn, -1);
	int IROut = 13 * pow(voltsOut, -1);

	// Check when pet comes in
	if (mode == 0)
	{
		if (IRIn > 10)
		{
			unsigned long startTime = millis();
			while (millis() - startTime < 5000)
			{
				float volt = analogRead(IROutPin) * 0.0048828125;
				int Out = 13 * pow(volt, -1);
				if (Out > 10)
				{
					break;
				}
			}

			petCounter++;
			delay(3000);
		}
		else if (IROut > 10)
		{
			unsigned long startTime = millis();
			while (millis() - startTime < 5000)
			{
				float volt = analogRead(IRInPin) * 0.0048828125;
				int In = 13 * pow(volt, -1);
				if (In > 10)
				{
					break;
				}
			}

			petCounter--;
			delay(3000);
		}

		float humidity = dht.getHumidity();
		float temperature = dht.getTemperature();

		Serial.println("Room: Cat Room");
		Serial.print("Total pets inside: ");
		Serial.println(petCounter);

		if (petCounter > 0)
		{
			digitalWrite(LEDPin, HIGH);
			Serial.println("Light: ON");
		}
		else
		{
			digitalWrite(LEDPin, LOW);
			Serial.println("Light: OFF");
		}
	}

	Serial.print("Humidity: ");
	Serial.println(humidity, 1);
	Serial.print("Temperature (C): ");
	Serial.print(temperature, 1);
	Serial.println();
	Serial.print("Temperature (F): ");
	Serial.println(dht.toFahrenheit(temperature), 1);
	int fanSpeed = map(temperature, 28, 35, 180, 255); // Map temperature to fan speed (0-255)

	int dustValue = analogRead(potentiometerPin);
	Serial.print("Dust Level: ");
	Serial.println(dustValue);

	if (temperature > 28 && dustValue > 500)
	{
		myServo.write(180);
		Serial.println("Window: OPEN");
		analogWrite(fanPin, fanSpeed);
		Serial.println("Fan: ON");
		Serial.print("Fan Speed: ");
		Serial.println(fanSpeed);
	}
	else if (temperature > 28 && dustValue <= 500)
	{
		myServo.write(0);
		Serial.println("Window: CLOSE");
		analogWrite(fanPin, fanSpeed);
		Serial.println("Fan: ON");
		Serial.print("Fan Speed: ");
		Serial.println(fanSpeed);
	}
	else if (temperature < 28 && dustValue > 500)
	{
		myServo.write(180);
		Serial.println("Window: OPEN");
		analogWrite(fanPin, 0);
		Serial.println("Fan: OFF");
		Serial.print("Fan Speed: ");
		Serial.println(0);
	}
	else
	{
		myServo.write(0);
		Serial.println("Window: CLOSE");
		Serial.println("Fan: OFF");
		Serial.print("Fan Speed: ");
		Serial.println(0);
	}

	delay(2000);
}