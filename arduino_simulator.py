"""
Симулятор Arduino с АЦП ADS1115 для тестирования Serial Voltmeter
Эмулирует работу устройства через виртуальный Serial порт
"""
import time
import random
import math
import logging
import argparse
from typing import Optional
import serial
import serial.tools.list_ports


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ADS1115Simulator:
    """Симулятор АЦП ADS1115"""
    
    # Доступные диапазоны напряжения (мВ)
    RANGES = {
        256: 0.125,
        512: 0.25,
        1024: 0.5,
        2048: 1.0,
        4096: 2.0,
        6144: 3.0
    }
    
    # Доступные частоты дискретизации (SPS)
    SAMPLE_RATES = [8, 16, 32, 64, 128, 250, 475, 860]
    
    def __init__(self):
        self.voltage_range = 6144  # мВ
        self.sample_rate = 860  # SPS
        self.noise_level = 5.0  # Уровень шума в мВ
        
    def set_range(self, range_mv: int) -> bool:
        """Установить диапазон напряжения"""
        if range_mv in self.RANGES:
            self.voltage_range = range_mv
            logger.info(f"ADC range set to {range_mv} mV")
            return True
        return False
    
    def set_sample_rate(self, rate: int) -> bool:
        """Установить частоту дискретизации"""
        if rate in self.SAMPLE_RATES:
            self.sample_rate = rate
            logger.info(f"ADC sample rate set to {rate} SPS")
            return True
        return False
    
    def read_voltage(self, counter: int) -> float:
        """
        Генерировать измерение напряжения
        Симулирует синусоиду с шумом
        """
        # Базовый сигнал: синусоида 1 Гц
        t = counter * 0.001  # время в секундах
        base_signal = 1000 * math.sin(2 * math.pi * 1.0 * t)  # 1000 мВ амплитуда
        
        # Добавляем шум
        noise = random.gauss(0, self.noise_level)
        
        # Добавляем медленный дрейф
        drift = 100 * math.sin(2 * math.pi * 0.1 * t)
        
        # Итоговое напряжение
        voltage = base_signal + noise + drift
        
        # Ограничиваем диапазоном
        max_v = self.voltage_range / 2
        voltage = max(-max_v, min(max_v, voltage))
        
        return voltage


class ArduinoSimulator:
    """Симулятор Arduino с поддержкой команд"""
    
    def __init__(self, port: str, baud_rate: int = 115200):
        """
        Args:
            port: Имя Serial порта для подключения
            baud_rate: Скорость передачи данных
        """
        self.port = port
        self.baud_rate = baud_rate
        self.serial: Optional[serial.Serial] = None
        self.running = False
        
        # Параметры
        self.sampling_interval_ms = 1  # Интервал отправки данных
        self.measurement_counter = 0
        
        # АЦП
        self.adc = ADS1115Simulator()
        
        # Состояние
        self.initialized = False
        
    def connect(self) -> bool:
        """Подключиться к Serial порту"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=0.1,
                write_timeout=1.0
            )
            logger.info(f"Connected to {self.port} at {self.baud_rate} baud")
            time.sleep(2)  # Даем время на инициализацию (как у реального Arduino)
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Отключиться от порта"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("Disconnected from port")
    
    def send_message(self, message: str):
        """Отправить сообщение в Serial порт"""
        if self.serial and self.serial.is_open:
            try:
                self.serial.write(f"{message}\n".encode('utf-8'))
                self.serial.flush()
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
    
    def initialize(self):
        """Симулировать инициализацию Arduino"""
        logger.info("Initializing Arduino simulator...")
        
        # Симулируем процесс инициализации
        for attempt in range(1, 4):
            self.send_message(f"INFO: Initializing ADC, attempt {attempt}/10")
            time.sleep(0.1)
        
        self.send_message("INFO: ADC configuration completed")
        self.send_message("READY: ADC initialized successfully")
        self.initialized = True
        logger.info("Arduino simulator initialized")
    
    def handle_command(self, command: str):
        """Обработать команду от компьютера"""
        parts = command.strip().split(',')
        if not parts:
            return
        
        cmd = parts[0]
        
        if cmd == "SET_RANGE" and len(parts) >= 2:
            try:
                range_val = int(parts[1])
                if self.adc.set_range(range_val):
                    self.send_message(f"INFO: Voltage range set to {range_val} mV")
                else:
                    self.send_message(f"ERROR: Invalid voltage range: {range_val}")
            except ValueError:
                self.send_message("ERROR: Invalid range value")
        
        elif cmd == "SET_RATE" and len(parts) >= 2:
            try:
                rate = int(parts[1])
                if self.adc.set_sample_rate(rate):
                    self.send_message(f"INFO: Conversion rate set to {rate} SPS")
                else:
                    self.send_message(f"ERROR: Invalid conversion rate: {rate}")
            except ValueError:
                self.send_message("ERROR: Invalid rate value")
        
        elif cmd == "SET_INTERVAL" and len(parts) >= 2:
            try:
                interval = int(parts[1])
                if 1 <= interval <= 1000:
                    self.sampling_interval_ms = interval
                    self.send_message(f"INFO: Sampling interval set to {interval} ms")
                else:
                    self.send_message(f"ERROR: Invalid interval (must be 1-1000): {interval}")
            except ValueError:
                self.send_message("ERROR: Invalid interval value")
        
        elif cmd == "GET_CONFIG":
            self.send_message(
                f"CONFIG: range={self.adc.voltage_range},"
                f"rate={self.adc.sample_rate},"
                f"interval={self.sampling_interval_ms}"
            )
        
        elif cmd == "RESET_COUNTER":
            self.measurement_counter = 0
            self.send_message("INFO: Measurement counter reset")
        
        else:
            self.send_message(f"ERROR: Unknown command: {cmd}")
    
    def read_commands(self):
        """Читать команды из Serial порта"""
        if not self.serial or not self.serial.is_open:
            return
        
        try:
            if self.serial.in_waiting > 0:
                line = self.serial.readline().decode('utf-8').strip()
                if line:
                    logger.info(f"Received command: {line}")
                    self.handle_command(line)
        except Exception as e:
            logger.debug(f"Error reading commands: {e}")
    
    def send_measurement(self):
        """Отправить измерение"""
        voltage = self.adc.read_voltage(self.measurement_counter)
        message = f"{self.measurement_counter},{voltage:.2f}"
        self.send_message(message)
        self.measurement_counter += 1
    
    def run(self):
        """Главный цикл симулятора"""
        if not self.connect():
            return
        
        try:
            # Инициализация
            self.initialize()
            
            self.running = True
            last_send_time = time.time()
            
            logger.info("Simulator running. Press Ctrl+C to stop.")
            
            while self.running:
                current_time = time.time()
                
                # Читаем команды
                self.read_commands()
                
                # Отправляем измерения с заданным интервалом
                if (current_time - last_send_time) >= (self.sampling_interval_ms / 1000.0):
                    self.send_measurement()
                    last_send_time = current_time
                
                # Небольшая задержка для снижения нагрузки на CPU
                time.sleep(0.0001)
        
        except KeyboardInterrupt:
            logger.info("\nStopping simulator...")
            self.running = False
        
        finally:
            self.disconnect()


def list_available_ports():
    """Показать доступные Serial порты"""
    ports = serial.tools.list_ports.comports()
    print("\n📋 Доступные Serial порты:")
    if ports:
        for port in ports:
            print(f"  - {port.device}: {port.description}")
    else:
        print("  Нет доступных портов")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Arduino Simulator for Serial Voltmeter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Примеры использования:

  1. Показать доступные порты:
     python arduino_simulator.py --list

  2. Запустить симулятор на COM3:
     python arduino_simulator.py --port COM3

  3. Запустить с кастомной скоростью:
     python arduino_simulator.py --port COM3 --baud 9600

  4. Запустить с подробным логированием:
     python arduino_simulator.py --port COM3 --verbose

Для Windows рекомендуется использовать виртуальные порты:
  - com0com (https://sourceforge.net/projects/com0com/)
  - Virtual Serial Port Driver

Для Linux:
  - socat (socat -d -d pty,raw,echo=0 pty,raw,echo=0)

Для macOS:
  - Встроенная поддержка /dev/tty*
        '''
    )
    
    parser.add_argument(
        '--port', '-p',
        type=str,
        help='Serial порт для подключения (например, COM3, /dev/ttyUSB0)'
    )
    
    parser.add_argument(
        '--baud', '-b',
        type=int,
        default=115200,
        help='Скорость передачи данных (по умолчанию: 115200)'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='Показать доступные Serial порты'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробное логирование (DEBUG уровень)'
    )
    
    args = parser.parse_args()
    
    # Настройка уровня логирования
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Показать доступные порты
    if args.list:
        list_available_ports()
        return
    
    # Проверка порта
    if not args.port:
        print("❌ Ошибка: укажите Serial порт с помощью --port")
        print("\nИспользуйте --list для просмотра доступных портов")
        print("Или --help для справки")
        return
    
    # Запуск симулятора
    print(f"\n🚀 Запуск симулятора Arduino на {args.port}")
    print(f"⚡ Скорость: {args.baud} baud")
    print(f"📊 Симулируется синусоида 1 Гц с шумом")
    print(f"\nДля остановки нажмите Ctrl+C\n")
    
    simulator = ArduinoSimulator(args.port, args.baud)
    simulator.run()


if __name__ == "__main__":
    main()
