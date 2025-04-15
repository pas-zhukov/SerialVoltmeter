#include <ADS1115_WE.h>
#include <Wire.h>

// SDA: PIN_A4
// SCL: PIN_A5
#define I2C_ADDRESS 0x48

// Глобальные переменные
ADS1115_WE adc = ADS1115_WE(I2C_ADDRESS);
int piezoPin = 11; // Пин для пьезоэлемента
int sampling = 10; // Частота отправки данных, мс
uint32_t tmr = 0;  // Таймер для контроля частоты отправки

void setup() {
  // Инициализация I2C и последовательного порта
  Wire.begin();
  Serial.begin(115200);
  
  // Настройка АЦП
  if (!adc.init()) {
    error(); // Сигнал ошибки, если инициализация не удалась
    return;
  }
  
  // Настройка режима работы АЦП
  adc.setVoltageRange_mV(ADS1115_RANGE_6144); // Диапазон ±6.144V
  adc.setMeasureMode(ADS1115_CONTINUOUS);     // Непрерывное измерение
  adc.setConvRate(ADS1115_860_SPS);           // Частота преобразования
  adc.setCompareChannels(ADS1115_COMP_0_1);   // Использовать канал 0-1
  
  // Приветственная мелодия при успешном запуске
  melody();
}

void loop() {
  // Отправка данных с заданным интервалом
  if (millis() - tmr >= sampling) {
    tmr = millis();
    
    // Получаем напряжение и отправляем в порт
    float voltage = adc.getResult_mV();
    
    // Формат: millis,voltage
    Serial.print(millis());
    Serial.print(',');
    Serial.println(voltage);
  }
}

// Приветственная мелодия
void melody() {
  tone(piezoPin, 880, 70);
  delay(70);
  tone(piezoPin, 1109, 70);
  delay(70);
  tone(piezoPin, 1319, 70);
}

// Сигнал ошибки
void error() {
  tone(piezoPin, 1000, 100);
  delay(120);
  tone(piezoPin, 950, 120);
}