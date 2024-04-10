#include <ADS1115_WE.h>
#include <Wire.h>

#include "Parser.h"
#include "AsyncStream.h"


// SDA: PIN_A4
// SCL: PIN_A5
#define I2C_ADDRESS 0x48


/*
GLOBALS
*/
AsyncStream<50> serial(&Serial, ';');   // указываем обработчик и стоп символ
ADS1115_WE adc = ADS1115_WE(I2C_ADDRESS);


int piezoPin = 11;
int alertPin = 2;

int sampling = 1000;
long duration = 2L * 60L * 1000L;
bool measMode = false;
uint32_t tmr = 0;

void setup() {
  Wire.begin();
  Serial.begin(115200);
  adc.setMeasureMode(ADS1115_CONTINUOUS);
  adc.setConvRate(ADS1115_860_SPS);
}

void loop() {
  parsing();
  if (millis() - tmr >= sampling && duration > 0) {
    duration -= sampling;
    tmr = millis();
    Serial.print(5);
    Serial.print(',');
    Serial.print(millis());
    Serial.print(',');
    Serial.print(readChannel(ADS1115_COMP_0_1));
    Serial.print(',');
    Serial.print(readChannel(ADS1115_COMP_2_3));
    Serial.print(',');
    Serial.println(duration);
  } 
}


float readChannel(ADS1115_MUX channel) {
  float voltage = 0.0;
  adc.setCompareChannels(channel);
  voltage = adc.getResult_mV();
  return voltage;
}

void sendPacket(int key, int* data, int amount) {
  Serial.print(key);
  Serial.print(',');
  for (int i = 0; i < amount; i++) {
    Serial.print(data[i]);
    if (i != amount - 1) Serial.print(',');
  }
  Serial.print('\n');
}

// функция парсинга, опрашивать в лупе
void parsing() {
  if (serial.available()) {
    Parser data(serial.buf, ',');  // отдаём парсеру
    int ints[10];           // массив для численных данных
    data.parseInts(ints);   // парсим в него
    switch (ints[0]) {      // свитч по ключу
      case 0:  // Проверка подключения
        if (!adc.init()) {
          Serial.println("0,0");
          error();
          break;
        }
        tone(piezoPin, 1300, 100); // Пикаем
        Serial.println("0,1");
        break;
      case 1:
        break;
      case 2:
        break;
      case 3:
        break;
      case 4: //запрос на измерения
        melody();
        startRecording(ints[1], ints[2], ints[3]);
        break;
    }
  }
}

void startRecording(int range, int sampl, int dur) {
  switch (range) {
    case 6144:
      adc.setVoltageRange_mV(ADS1115_RANGE_6144);
    case 4096:
      adc.setVoltageRange_mV(ADS1115_RANGE_4096);
    case 2048:
      adc.setVoltageRange_mV(ADS1115_RANGE_2048);
    case 1024:
      adc.setVoltageRange_mV(ADS1115_RANGE_1024);
    case 512:
      adc.setVoltageRange_mV(ADS1115_RANGE_0512);
    case 256:
      adc.setVoltageRange_mV(ADS1115_RANGE_0256);
  }

  sampling = sampl;
  duration = dur * 1000L;
  measMode = 1;
  Serial.println(range);
  Serial.println(sampl);
  Serial.println(dur);
}

void melody() {
  tone(piezoPin, 880, 70);
  delay(70);
  tone(piezoPin, 1109, 70);
  delay(70);
  tone(piezoPin, 1319, 70);
}

void error() {
  tone(piezoPin, 1000, 100);
  delay(120);
  tone(piezoPin, 950, 120);
}