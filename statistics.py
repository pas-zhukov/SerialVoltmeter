"""
Модуль для расчета статистики и анализа данных в реальном времени
"""
import numpy as np
import logging
from typing import List, Dict, Optional, Tuple
from collections import deque


logger = logging.getLogger(__name__)


class Statistics:
    """
    Класс для расчета статистики по данным измерений
    """
    
    def __init__(self, window_size: int = 1000):
        """
        Args:
            window_size: Размер скользящего окна для статистики
        """
        self.window_size = window_size
        self.voltage_buffer = deque(maxlen=window_size)
        self.time_buffer = deque(maxlen=window_size)
        
    def add_measurement(self, time_val: float, voltage: float):
        """Добавить измерение для анализа"""
        self.voltage_buffer.append(voltage)
        self.time_buffer.append(time_val)
    
    def get_statistics(self) -> Dict[str, float]:
        """
        Получить статистику по текущим данным
        
        Returns:
            Словарь со статистическими показателями
        """
        if len(self.voltage_buffer) == 0:
            return {
                'min': 0.0,
                'max': 0.0,
                'mean': 0.0,
                'std': 0.0,
                'rms': 0.0,
                'count': 0
            }
        
        voltages = np.array(self.voltage_buffer)
        
        stats = {
            'min': float(np.min(voltages)),
            'max': float(np.max(voltages)),
            'mean': float(np.mean(voltages)),
            'std': float(np.std(voltages)),
            'rms': float(np.sqrt(np.mean(voltages**2))),
            'count': len(voltages)
        }
        
        return stats
    
    def clear(self):
        """Очистить буферы"""
        self.voltage_buffer.clear()
        self.time_buffer.clear()


class PeakDetector:
    """
    Детектор пиков напряжения
    """
    
    def __init__(self, threshold: float = 100.0, min_distance: int = 10):
        """
        Args:
            threshold: Пороговое значение для детекции пика (мВ)
            min_distance: Минимальное расстояние между пиками (количество измерений)
        """
        self.threshold = threshold
        self.min_distance = min_distance
        self.last_peak_index = -min_distance
        self.peaks_detected = []
        self.measurement_index = 0
        
    def add_measurement(self, time_val: float, voltage: float) -> Optional[Tuple[float, float]]:
        """
        Добавить измерение и проверить на пик
        
        Args:
            time_val: Время измерения
            voltage: Напряжение
            
        Returns:
            (time, voltage) если обнаружен пик, иначе None
        """
        self.measurement_index += 1
        
        # Проверяем условия для пика
        if (abs(voltage) > self.threshold and 
            self.measurement_index - self.last_peak_index >= self.min_distance):
            
            self.last_peak_index = self.measurement_index
            peak_info = (time_val, voltage)
            self.peaks_detected.append(peak_info)
            logger.info(f"Peak detected: time={time_val:.3f}s, voltage={voltage:.2f}mV")
            return peak_info
        
        return None
    
    def get_peaks(self) -> List[Tuple[float, float]]:
        """Получить список всех обнаруженных пиков"""
        return self.peaks_detected.copy()
    
    def clear(self):
        """Очистить историю пиков"""
        self.peaks_detected.clear()
        self.last_peak_index = -self.min_distance
        self.measurement_index = 0


class TriggerDetector:
    """
    Детектор триггеров (событий) на основе пороговых значений
    """
    
    def __init__(self, trigger_level: float = 1000.0, trigger_mode: str = 'rising'):
        """
        Args:
            trigger_level: Уровень триггера (мВ)
            trigger_mode: Режим триггера ('rising', 'falling', 'both')
        """
        self.trigger_level = trigger_level
        self.trigger_mode = trigger_mode
        self.last_voltage = 0.0
        self.trigger_events = []
        self.armed = True
        
    def add_measurement(self, time_val: float, voltage: float) -> Optional[str]:
        """
        Добавить измерение и проверить на триггер
        
        Args:
            time_val: Время измерения
            voltage: Напряжение
            
        Returns:
            Тип триггера ('rising' или 'falling') если сработал, иначе None
        """
        trigger_type = None
        
        if self.trigger_mode in ['rising', 'both']:
            if self.last_voltage < self.trigger_level <= voltage and self.armed:
                trigger_type = 'rising'
                self.armed = False
                
        if self.trigger_mode in ['falling', 'both']:
            if self.last_voltage > self.trigger_level >= voltage and self.armed:
                trigger_type = 'falling'
                self.armed = False
        
        # Взводим триггер обратно когда сигнал отошел от порога
        if abs(voltage - self.trigger_level) > abs(self.trigger_level * 0.1):
            self.armed = True
        
        if trigger_type:
            event = {
                'time': time_val,
                'voltage': voltage,
                'type': trigger_type
            }
            self.trigger_events.append(event)
            logger.info(f"Trigger detected: {trigger_type} at time={time_val:.3f}s, voltage={voltage:.2f}mV")
        
        self.last_voltage = voltage
        return trigger_type
    
    def get_events(self) -> List[Dict]:
        """Получить список всех событий триггера"""
        return self.trigger_events.copy()
    
    def clear(self):
        """Очистить историю событий"""
        self.trigger_events.clear()
        self.armed = True


class DataAnalyzer:
    """
    Комплексный анализатор данных, объединяющий статистику, 
    детекцию пиков и триггеров
    """
    
    def __init__(self, stats_window: int = 1000,
                 peak_threshold: float = 100.0,
                 trigger_level: float = 1000.0):
        """
        Args:
            stats_window: Размер окна для статистики
            peak_threshold: Порог для детекции пиков
            trigger_level: Уровень триггера
        """
        self.statistics = Statistics(window_size=stats_window)
        self.peak_detector = PeakDetector(threshold=peak_threshold)
        self.trigger_detector = TriggerDetector(trigger_level=trigger_level)
        
    def analyze_measurement(self, time_val: float, voltage: float) -> Dict:
        """
        Проанализировать одно измерение
        
        Args:
            time_val: Время измерения
            voltage: Напряжение
            
        Returns:
            Словарь с результатами анализа
        """
        # Добавляем в статистику
        self.statistics.add_measurement(time_val, voltage)
        
        # Проверяем на пики
        peak = self.peak_detector.add_measurement(time_val, voltage)
        
        # Проверяем на триггер
        trigger = self.trigger_detector.add_measurement(time_val, voltage)
        
        return {
            'peak_detected': peak is not None,
            'peak_info': peak,
            'trigger_detected': trigger is not None,
            'trigger_type': trigger
        }
    
    def get_full_report(self) -> Dict:
        """
        Получить полный отчет по данным
        
        Returns:
            Словарь с полным отчетом
        """
        stats = self.statistics.get_statistics()
        peaks = self.peak_detector.get_peaks()
        triggers = self.trigger_detector.get_events()
        
        return {
            'statistics': stats,
            'peaks_count': len(peaks),
            'peaks': peaks[-10:],  # Последние 10 пиков
            'triggers_count': len(triggers),
            'triggers': triggers[-10:]  # Последние 10 триггеров
        }
    
    def clear(self):
        """Очистить все данные анализа"""
        self.statistics.clear()
        self.peak_detector.clear()
        self.trigger_detector.clear()
