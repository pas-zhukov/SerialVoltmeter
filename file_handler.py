"""
Модуль для работы с файлами данных
"""
import os
import csv
import logging
import datetime
from typing import Optional, List, Tuple


logger = logging.getLogger(__name__)


class DataFileWriter:
    """
    Класс для записи данных измерений в CSV файл
    Обеспечивает буферизованную запись и автоматическое закрытие файла
    """
    
    def __init__(self, filename: Optional[str] = None):
        """
        Args:
            filename: Имя файла для записи. Если None, генерируется автоматически
        """
        self.filename = filename or self._generate_filename()
        self.file = None
        self.writer = None
        self.measurements_written = 0
        
    def _generate_filename(self) -> str:
        """Генерация имени файла на основе текущей даты и времени"""
        now = datetime.datetime.now()
        return f"measurements_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    
    def open(self) -> bool:
        """
        Открыть файл для записи и записать заголовок
        
        Returns:
            bool: True если файл успешно открыт, False иначе
        """
        try:
            self.file = open(self.filename, 'w', newline='', buffering=8192)
            self.writer = csv.writer(self.file)
            self.writer.writerow(['time', 'voltage'])
            self.file.flush()
            self.measurements_written = 0
            logger.info(f"Data file opened: {self.filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to open file {self.filename}: {e}")
            return False
    
    def write_measurement(self, time_val: float, voltage: float):
        """
        Записать одно измерение в файл
        
        Args:
            time_val: Время измерения в секундах
            voltage: Напряжение в милливольтах
        """
        if not self.file or not self.writer:
            logger.warning("Attempt to write to closed file")
            return
        
        try:
            self.writer.writerow([f"{time_val:.6f}", f"{voltage:.2f}"])
            self.measurements_written += 1
            
            # Периодически сбрасываем буфер (каждые 100 измерений)
            if self.measurements_written % 100 == 0:
                self.file.flush()
                
        except Exception as e:
            logger.error(f"Failed to write measurement: {e}")
    
    def close(self) -> Tuple[int, str]:
        """
        Закрыть файл
        
        Returns:
            Tuple[int, str]: (количество записанных измерений, имя файла)
        """
        count = self.measurements_written
        filename = self.filename
        
        if self.file:
            try:
                self.file.flush()
                self.file.close()
                logger.info(f"Data file closed: {filename}, measurements written: {count}")
            except Exception as e:
                logger.error(f"Error closing file: {e}")
            finally:
                self.file = None
                self.writer = None
        
        return count, filename
    
    def is_open(self) -> bool:
        """Проверка, открыт ли файл"""
        return self.file is not None and not self.file.closed


class DataFileReader:
    """
    Класс для чтения данных из CSV файлов
    """
    
    @staticmethod
    def read_file(filename: str) -> Tuple[List[float], List[float], Optional[str]]:
        """
        Прочитать данные из CSV файла
        
        Args:
            filename: Путь к файлу
            
        Returns:
            Tuple[List[float], List[float], Optional[str]]: 
                (times, voltages, error_message)
                error_message будет None при успешном чтении
        """
        times = []
        voltages = []
        
        try:
            with open(filename, 'r') as f:
                # Пропускаем заголовок
                next(f, None)
                
                # Читаем данные
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        try:
                            time_val = float(row[0])
                            voltage = float(row[1])
                            times.append(time_val)
                            voltages.append(voltage)
                        except (ValueError, IndexError):
                            # Пропускаем некорректные строки
                            continue
            
            if not times or not voltages:
                return [], [], "Файл не содержит данных или имеет неверный формат"
            
            logger.info(f"Successfully read {len(times)} measurements from {filename}")
            return times, voltages, None
            
        except FileNotFoundError:
            error_msg = f"Файл не найден: {filename}"
            logger.error(error_msg)
            return [], [], error_msg
        except Exception as e:
            error_msg = f"Ошибка при чтении файла: {str(e)}"
            logger.error(error_msg)
            return [], [], error_msg
    
    @staticmethod
    def get_file_info(filename: str) -> dict:
        """
        Получить информацию о файле
        
        Args:
            filename: Путь к файлу
            
        Returns:
            dict: Словарь с информацией о файле
        """
        info = {
            'filename': os.path.basename(filename),
            'path': filename,
            'exists': False,
            'size_bytes': 0,
            'measurements_count': 0,
            'duration_seconds': 0.0
        }
        
        try:
            if os.path.exists(filename):
                info['exists'] = True
                info['size_bytes'] = os.path.getsize(filename)
                
                # Читаем данные для получения количества и длительности
                times, voltages, error = DataFileReader.read_file(filename)
                if error is None:
                    info['measurements_count'] = len(times)
                    if times:
                        info['duration_seconds'] = max(times)
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
        
        return info
