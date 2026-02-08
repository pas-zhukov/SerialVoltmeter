"""
Модуль для обработки Serial коммуникации в отдельном потоке
"""
import logging
from queue import Queue
from PyQt5.QtCore import QThread, pyqtSignal, QIODevice
from PyQt5.QtSerialPort import QSerialPort


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SerialReaderThread(QThread):
    """
    Поток для чтения данных из Serial порта
    Отправляет сигналы при получении данных, ошибок и специальных сообщений
    """
    
    # Сигналы для передачи данных в главный поток
    data_received = pyqtSignal(int, float)  # (counter, voltage)
    error_occurred = pyqtSignal(str)  # сообщение об ошибке
    info_message = pyqtSignal(str)  # информационное сообщение
    connection_lost = pyqtSignal()  # потеря соединения
    
    # Константы
    CONSOLE_UPDATE_INTERVAL = 0.5  # Интервал вывода в консоль (секунды)
    SAMPLING_INTERVAL_MS = 10  # Интервал отправки данных с Arduino (мс)
    
    def __init__(self, serial_port: QSerialPort):
        super().__init__()
        self.serial = serial_port
        self.running = False
        self.last_console_update = 0
        self.measurements_count = 0
        self.errors_count = 0
        
    def run(self):
        """Основной цикл потока для чтения данных"""
        logger.info("Serial reader thread started")
        self.running = True
        self.measurements_count = 0
        self.errors_count = 0
        
        while self.running:
            # Проверяем наличие данных
            if not self.serial.isOpen():
                logger.warning("Serial port closed unexpectedly")
                self.connection_lost.emit()
                break
            
            # Ждем данных с таймаутом
            if self.serial.waitForReadyRead(100):
                self._process_available_data()
            
            # Небольшая задержка для предотвращения загрузки CPU
            self.msleep(1)
        
        logger.info(f"Serial reader thread stopped. Total measurements: {self.measurements_count}, errors: {self.errors_count}")
    
    def _process_available_data(self):
        """Обработка всех доступных данных в буфере"""
        while self.serial.canReadLine():
            try:
                line = str(self.serial.readLine(), 'utf-8').strip()
                
                if not line:
                    continue
                
                # Обработка специальных сообщений от Arduino
                if line.startswith('ERROR:'):
                    error_msg = line[6:].strip()
                    logger.error(f"Arduino error: {error_msg}")
                    self.error_occurred.emit(f"Arduino: {error_msg}")
                    self.errors_count += 1
                    continue
                
                if line.startswith('WARNING:'):
                    warning_msg = line[8:].strip()
                    logger.warning(f"Arduino warning: {warning_msg}")
                    self.info_message.emit(f"⚠ {warning_msg}")
                    continue
                
                if line.startswith('INFO:'):
                    info_msg = line[5:].strip()
                    logger.info(f"Arduino info: {info_msg}")
                    self.info_message.emit(info_msg)
                    continue
                
                if line.startswith('READY:'):
                    ready_msg = line[6:].strip()
                    logger.info(f"Arduino ready: {ready_msg}")
                    self.info_message.emit(f"✓ {ready_msg}")
                    continue
                
                # Разбор данных измерений (формат: counter,voltage)
                parts = line.split(',')
                if len(parts) < 2:
                    logger.debug(f"Invalid data format: {line}")
                    continue
                
                try:
                    # Счетчик измерений
                    counter = int(parts[0])
                    # Напряжение в милливольтах
                    voltage = float(parts[1])
                    
                    # Отправляем данные в главный поток
                    self.data_received.emit(counter, voltage)
                    self.measurements_count += 1
                    
                except (ValueError, IndexError) as e:
                    logger.debug(f"Error parsing measurement data: {line}, error: {e}")
                    self.errors_count += 1
                    
            except UnicodeDecodeError as e:
                logger.debug(f"Unicode decode error: {e}")
                self.errors_count += 1
            except Exception as e:
                logger.error(f"Unexpected error in data processing: {e}")
                self.error_occurred.emit(f"Ошибка обработки данных: {str(e)}")
                self.errors_count += 1
    
    def stop(self):
        """Остановка потока"""
        logger.info("Stopping serial reader thread...")
        self.running = False


class DataBuffer:
    """
    Буфер для хранения и управления данными измерений
    Ограничивает размер данных в памяти
    """
    
    def __init__(self, max_size: int = 100000):
        """
        Args:
            max_size: Максимальное количество точек данных в памяти
        """
        self.max_size = max_size
        self.times = []
        self.voltages = []
        self.lock = None  # Можно добавить threading.Lock() если нужно
    
    def add_data(self, time_val: float, voltage: float):
        """Добавить точку данных"""
        self.times.append(time_val)
        self.voltages.append(voltage)
        
        # Ограничиваем размер буфера
        if len(self.times) > self.max_size:
            # Удаляем старые данные (первую половину)
            remove_count = self.max_size // 2
            self.times = self.times[remove_count:]
            self.voltages = self.voltages[remove_count:]
            logger.info(f"Buffer trimmed: removed {remove_count} oldest points")
    
    def get_windowed_data(self, window_size: float):
        """
        Получить данные за последнее окно времени
        
        Args:
            window_size: Размер окна в секундах
            
        Returns:
            Tuple[List[float], List[float]]: (times, voltages)
        """
        if not self.times:
            return [], []
        
        current_time = self.times[-1]
        min_time = max(0, current_time - window_size)
        
        # Находим индекс первого элемента в окне
        start_idx = 0
        for i in range(len(self.times) - 1, -1, -1):
            if self.times[i] < min_time:
                start_idx = i + 1
                break
        
        return self.times[start_idx:], self.voltages[start_idx:]
    
    def get_all_data(self):
        """Получить все данные"""
        return self.times[:], self.voltages[:]
    
    def clear(self):
        """Очистить буфер"""
        self.times.clear()
        self.voltages.clear()
    
    def size(self):
        """Получить текущий размер буфера"""
        return len(self.times)
