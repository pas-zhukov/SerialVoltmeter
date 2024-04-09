#include "Parser.h"       // библиотека парсера
#include "AsyncStream.h"  // асинхронное чтение сериал
AsyncStream<50> serial(&Serial, ';');   // указываем обработчик и стоп символ
int piezoPin = 11;

void setup() {
  Serial.begin(115200);
}

void melody() {
  tone(piezoPin, 880, 70);
  delay(70);
  tone(piezoPin, 1109, 70);
  delay(70);
  tone(piezoPin, 1319, 70);
}

void loop() {
  parsing();
  static uint32_t tmr = 0;
  if (micros() - tmr >= 900) {
    tmr = millis();
    Serial.print(0);
    Serial.print(',');
    Serial.print(analogRead(4));
    Serial.print(',');
    Serial.print("5.136");
    Serial.print(',');
    Serial.println(millis());
  }
}

// функция для отправки пакета на ПК
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
    int ints[5];           // массив для численных данных
    data.parseInts(ints);   // парсим в него
    switch (ints[0]) {      // свитч по ключу
      case 0:  // Проверка подключения
        tone(piezoPin, 1300, 100); // Пикаем
        Serial.println("0,1");
        break;
      case 1: // Настройка параметров записи
        break;
      case 2:
        break;
      case 3:
        break;
    }
  }
}