#include <ADS1115_WE.h>
#include <Wire.h>
#include "AsyncStream.h"
#include "Parser.h"

// SDA: PIN_A4
// SCL: PIN_A5
#define I2C_ADDRESS 0x48

// Константы
const int PIEZO_PIN = 11;              // Пин для пьезоэлемента
const int SAMPLING_INTERVAL_MS = 1;    // Частота отправки данных, мс (синхронизировано с АЦП 860 SPS)
const unsigned long SERIAL_BAUD_RATE = 115200;
const int MAX_INIT_ATTEMPTS = 10;      // Максимальное количество попыток инициализации
const int INIT_RETRY_DELAY_MS = 1000;  // Задержка между попытками инициализации

// Глобальные переменные
ADS1115_WE adc = ADS1115_WE(I2C_ADDRESS);
AsyncStream<64> serial(&Serial, '\n', 100);  // Асинхронный парсер Serial команд
uint32_t lastSendTime = 0;             // Время последней отправки данных
uint32_t measurementCounter = 0;       // Счетчик измерений (вместо millis для избежания переполнения)
bool adcInitialized = false;           // Флаг успешной инициализации АЦП

// Изменяемые параметры АЦП
int currentSamplingInterval = SAMPLING_INTERVAL_MS;
ADS1115_RANGE currentVoltageRange = ADS1115_RANGE_6144;
ADS1115_CONV_RATE currentConvRate = ADS1115_860_SPS;

void setup() {
  // Настройка пина пьезоэлемента
  pinMode(PIEZO_PIN, OUTPUT);
  
  // Инициализация I2C и последовательного порта
  Wire.begin();
  Serial.begin(SERIAL_BAUD_RATE);
  
  // Ждем готовности Serial
  delay(100);
  
  // Попытка инициализации АЦП с повторными попытками
  adcInitialized = initializeADC();
  
  if (!adcInitialized) {
    // Если инициализация не удалась после всех попыток, 
    // сообщаем об ошибке и продолжаем работу в режиме ошибки
    Serial.println("ERROR: ADC initialization failed after all attempts");
    error();
  } else {
    // Приветственная мелодия при успешном запуске
    melody();
    Serial.println("READY: ADC initialized successfully");
  }
}

/**
 * Инициализация АЦП с повторными попытками
 * Возвращает true при успешной инициализации, false при неудаче
 */
bool initializeADC() {
  for (int attempt = 1; attempt <= MAX_INIT_ATTEMPTS; attempt++) {
    Serial.print("INFO: Initializing ADC, attempt ");
    Serial.print(attempt);
    Serial.print("/");
    Serial.println(MAX_INIT_ATTEMPTS);
    
    if (adc.init()) {
      // Настройка режима работы АЦП
      adc.setVoltageRange_mV(ADS1115_RANGE_6144); // Диапазон ±6.144V
      adc.setMeasureMode(ADS1115_CONTINUOUS);     // Непрерывное измерение
      adc.setConvRate(ADS1115_860_SPS);           // Частота преобразования
      adc.setCompareChannels(ADS1115_COMP_0_1);   // Использовать канал 0-1
      
      Serial.println("INFO: ADC configuration completed");
      return true;
    }
    
    if (attempt < MAX_INIT_ATTEMPTS) {
      Serial.println("WARNING: ADC init failed, retrying...");
      delay(INIT_RETRY_DELAY_MS);
    }
  }
  
  return false;
}

void loop() {
  // Прием команд от компьютера
  if (serial.available()) {
    handleCommand();
  }
  
  // Если АЦП не инициализирован, пытаемся переинициализировать
  if (!adcInitialized) {
    static unsigned long lastRetryTime = 0;
    if (millis() - lastRetryTime >= 5000) { // Попытка каждые 5 секунд
      Serial.println("INFO: Attempting to reinitialize ADC...");
      adcInitialized = initializeADC();
      lastRetryTime = millis();
      
      if (adcInitialized) {
        Serial.println("INFO: ADC reinitialized successfully");
        melody();
      }
    }
    return; // Не продолжаем пока АЦП не инициализирован
  }
  
  // Отправка данных с заданным интервалом
  if (millis() - lastSendTime >= currentSamplingInterval) {
    lastSendTime = millis();
    
    // Получаем напряжение и отправляем в порт
    float voltage = adc.getResult_mV();
    
    // Формат: counter,voltage
    Serial.print(measurementCounter);
    Serial.print(',');
    Serial.println(voltage, 2);
    
    measurementCounter++;
  }
}

/**
 * Обработка команд от компьютера
 * Поддерживаемые команды:
 * - SET_RANGE,<value> - установить диапазон напряжения (256, 512, 1024, 2048, 4096, 6144)
 * - SET_RATE,<value> - установить частоту дискретизации (8, 16, 32, 64, 128, 250, 475, 860)
 * - SET_INTERVAL,<ms> - установить интервал отправки данных (мс)
 * - GET_CONFIG - получить текущую конфигурацию
 * - RESET_COUNTER - сбросить счетчик измерений
 */
void handleCommand() {
  Parser parser(serial.buf, ',');
  int parts = parser.split();
  
  if (parts < 1) return;
  
  // Команда SET_RANGE
  if (parser.equals(0, "SET_RANGE") && parts >= 2) {
    int range = parser.getInt(1);
    if (setVoltageRange(range)) {
      Serial.print("INFO: Voltage range set to ");
      Serial.print(range);
      Serial.println(" mV");
    } else {
      Serial.print("ERROR: Invalid voltage range: ");
      Serial.println(range);
    }
  }
  // Команда SET_RATE
  else if (parser.equals(0, "SET_RATE") && parts >= 2) {
    int rate = parser.getInt(1);
    if (setConvRate(rate)) {
      Serial.print("INFO: Conversion rate set to ");
      Serial.print(rate);
      Serial.println(" SPS");
    } else {
      Serial.print("ERROR: Invalid conversion rate: ");
      Serial.println(rate);
    }
  }
  // Команда SET_INTERVAL
  else if (parser.equals(0, "SET_INTERVAL") && parts >= 2) {
    int interval = parser.getInt(1);
    if (interval >= 1 && interval <= 1000) {
      currentSamplingInterval = interval;
      Serial.print("INFO: Sampling interval set to ");
      Serial.print(interval);
      Serial.println(" ms");
    } else {
      Serial.print("ERROR: Invalid interval (must be 1-1000): ");
      Serial.println(interval);
    }
  }
  // Команда GET_CONFIG
  else if (parser.equals(0, "GET_CONFIG")) {
    Serial.print("CONFIG: range=");
    Serial.print(getRangeValue(currentVoltageRange));
    Serial.print(",rate=");
    Serial.print(getRateValue(currentConvRate));
    Serial.print(",interval=");
    Serial.println(currentSamplingInterval);
  }
  // Команда RESET_COUNTER
  else if (parser.equals(0, "RESET_COUNTER")) {
    measurementCounter = 0;
    Serial.println("INFO: Measurement counter reset");
  }
  else {
    Serial.print("ERROR: Unknown command: ");
    Serial.println(parser[0]);
  }
}

/**
 * Установить диапазон напряжения АЦП
 */
bool setVoltageRange(int range_mv) {
  ADS1115_RANGE newRange;
  
  switch (range_mv) {
    case 256:  newRange = ADS1115_RANGE_0256; break;
    case 512:  newRange = ADS1115_RANGE_0512; break;
    case 1024: newRange = ADS1115_RANGE_1024; break;
    case 2048: newRange = ADS1115_RANGE_2048; break;
    case 4096: newRange = ADS1115_RANGE_4096; break;
    case 6144: newRange = ADS1115_RANGE_6144; break;
    default: return false;
  }
  
  currentVoltageRange = newRange;
  adc.setVoltageRange_mV(newRange);
  return true;
}

/**
 * Установить частоту дискретизации АЦП
 */
bool setConvRate(int rate_sps) {
  ADS1115_CONV_RATE newRate;
  
  switch (rate_sps) {
    case 8:   newRate = ADS1115_8_SPS;   break;
    case 16:  newRate = ADS1115_16_SPS;  break;
    case 32:  newRate = ADS1115_32_SPS;  break;
    case 64:  newRate = ADS1115_64_SPS;  break;
    case 128: newRate = ADS1115_128_SPS; break;
    case 250: newRate = ADS1115_250_SPS; break;
    case 475: newRate = ADS1115_475_SPS; break;
    case 860: newRate = ADS1115_860_SPS; break;
    default: return false;
  }
  
  currentConvRate = newRate;
  adc.setConvRate(newRate);
  return true;
}

/**
 * Получить текущее значение диапазона в мВ
 */
int getRangeValue(ADS1115_RANGE range) {
  switch (range) {
    case ADS1115_RANGE_0256: return 256;
    case ADS1115_RANGE_0512: return 512;
    case ADS1115_RANGE_1024: return 1024;
    case ADS1115_RANGE_2048: return 2048;
    case ADS1115_RANGE_4096: return 4096;
    case ADS1115_RANGE_6144: return 6144;
    default: return 0;
  }
}

/**
 * Получить текущее значение частоты в SPS
 */
int getRateValue(ADS1115_CONV_RATE rate) {
  switch (rate) {
    case ADS1115_8_SPS:   return 8;
    case ADS1115_16_SPS:  return 16;
    case ADS1115_32_SPS:  return 32;
    case ADS1115_64_SPS:  return 64;
    case ADS1115_128_SPS: return 128;
    case ADS1115_250_SPS: return 250;
    case ADS1115_475_SPS: return 475;
    case ADS1115_860_SPS: return 860;
    default: return 0;
  }
}

/**
 * Приветственная мелодия при успешной инициализации
 */
void melody() {
  tone(PIEZO_PIN, 880, 70);
  delay(70);
  tone(PIEZO_PIN, 1109, 70);
  delay(70);
  tone(PIEZO_PIN, 1319, 70);
}

/**
 * Сигнал ошибки - двойной звуковой сигнал
 */
void error() {
  for (int i = 0; i < 3; i++) {
    tone(PIEZO_PIN, 1000, 100);
    delay(120);
    tone(PIEZO_PIN, 950, 120);
    delay(200);
  }
}