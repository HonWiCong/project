#include <Servo.h>
#include "DHT.h"
#include <ArduinoJson.h>

StaticJsonDocument<200> outgoing;

DHT dht;
int DHTPin = 5;

Servo myServo;
int servoPin = 3;

int IRInPin = A2;
int IROutPin = A1;

int potentiometerPin = A0;

int fanPin = 11;
int LEDPin = 8;

int petCounter = 0;
bool sensorIn = false;
bool sensorOut = false;

const int BUFFER_SIZE = 512;
char buffer[BUFFER_SIZE];

int mode, fanTemp, dustWindow, petLight, irDistance, light, fan, window;

void setup()
{
	dht.setup(DHTPin);
	myServo.attach(servoPin);
	pinMode(potentiometerPin, INPUT);

	pinMode(fanPin, OUTPUT);
	pinMode(LEDPin, OUTPUT);

	Serial.begin(9600);
	while (!Serial)
		;
}

void getInput()
{
	// Clear buffer before reading
	memset(buffer, 0, BUFFER_SIZE);

	// Read data from serial until newline
	if (Serial.readBytesUntil('\n', buffer, BUFFER_SIZE) > 0)
	{
		StaticJsonDocument<200> jsonDoc;
		DeserializationError error = deserializeJson(jsonDoc, buffer);

		if (!error)
		{
			mode = jsonDoc["control"];
			fanTemp = jsonDoc["fanTemp"];
			dustWindow = jsonDoc["dustWindow"];
			petLight = jsonDoc["petLight"];
			irDistance = jsonDoc["irDistance"];

			light = jsonDoc["light"];
			fan = jsonDoc["fan"];
			window = jsonDoc["window"];

			outgoing["Mode"] = mode;
			outgoing["Fan Temp"] = fanTemp;
			outgoing["Dust Window"] = dustWindow;
			outgoing["Pet Light"] = petLight;
			outgoing["IR Distance"] = irDistance;
			outgoing["Light"] = light;
			outgoing["Fan"] = fan;
			outgoing["Window"] = window;

			serializeJson(outgoing, Serial);
			Serial.print('\n');
		}
		else
		{
			Serial.println("Error deserializing JSON");
		}
	}
}

void loop()
{
	float voltsIn = analogRead(IRInPin) * 0.0048828125;
	float voltsOut = analogRead(IROutPin) * 0.0048828125;
	int IRIn = 13 * pow(voltsIn, -1);
	int IROut = 13 * pow(voltsOut, -1);

	if (Serial.available())
	{
		delay(60);
		getInput();
	}

	if (mode == 0)
	{
		if (IRIn > 10)
		{
			unsigned long startTime = millis();
			// while (millis() - startTime < 5000)
			while (true)
			{
				Serial.println("Inside the loop: in");
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
			// while (millis() - startTime < 5000)
			while (true)
			{
				Serial.println("Inside the loop: out");
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

		outgoing["arduino_petCounter"] = petCounter;
		outgoing["arduino_humidity"] = humidity;
		outgoing["arduino_temperature_C"] = temperature;
		outgoing["arduino_temperature_F"] = dht.toFahrenheit(temperature);

		if (petCounter > petLight)
		{
			digitalWrite(LEDPin, HIGH);
			outgoing["arduino_light"] = "ON";
		}
		else
		{
			digitalWrite(LEDPin, LOW);
			outgoing["arduino_light"] = "OFF";
		}

		serializeJson(outgoing, Serial);
		Serial.print('\n');

		//    Serial.print("Humidity: ");
		//    Serial.println(humidity, 1);
		//    Serial.print("Temperature (C): ");
		//    Serial.print(temperature, 1);
		//    Serial.println();
		//    Serial.print("Temperature (F): ");
		//    Serial.println(dht.toFahrenheit(temperature), 1);
		//    int fanSpeed = map(temperature, 28, 35, 180, 255); // Map temperature to fan speed (0-255)
		//
		int dustValue = analogRead(potentiometerPin);
		//    Serial.print("Dust Level: ");
		//    Serial.println(dustValue);
		outgoing["arduino_dustValue"] = analogRead(potentiometerPin);

		if (temperature > fanTemp && dustValue > dustWindow)
		{
			// Serial.println("Window: OPEN");
			// Serial.println("Fan: ON");
			// Serial.print("Fan Speed: ");
			// Serial.println(fanSpeed);

			myServo.write(180);
			analogWrite(fanPin, fanSpeed);
			outgoing["arduino_window"] = "OPEN";
			outgoing["arduino_fan"] = "ON";
			outgoing["arduino_fanSpeed"] = fanSpeed;
		}
		else if (temperature > fanTemp && dustValue <= dustWindow)
		{
			// Serial.println("Window: CLOSE");
			// Serial.println("Fan: ON");
			// Serial.print("Fan Speed: ");
			// Serial.println(fanSpeed);

			myServo.write(0);
			analogWrite(fanPin, fanSpeed);
			outgoing["arduino_window"] = "CLOSE";
			outgoing["arduino_fan"] = "ON";
			outgoing["arduino_fanSpeed"] = fanSpeed;
		}
		else if (temperature < fanTemp && dustValue > dustWindow)
		{
			// Serial.println("Window: OPEN");
			// Serial.println("Fan: OFF");
			// Serial.print("Fan Speed: ");
			// Serial.println(0);

			myServo.write(180);
			analogWrite(fanPin, 0);
			outgoing["arduino_window"] = "OPEN";
			outgoing["arduino_fan"] = "OFF";
			outgoing["arduino_fanSpeed"] = 0;
		}
		else
		{
			// Serial.println("Window: CLOSE");
			// Serial.println("Fan: OFF");
			// Serial.print("Fan Speed: ");
			// Serial.println(0);

			myServo.write(0);
			analogWrite(fanPin, 0);
			outgoing["arduino_window"] = "CLOSE";
			outgoing["arduino_fan"] = "OFF";
			outgoing["arduino_fanSpeed"] = 0;
		}
		//
		//    delay(2000);
	}
}