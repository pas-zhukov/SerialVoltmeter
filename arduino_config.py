"""
Модуль для настройки Arduino и АЦП ADS1115
Поддерживает двунаправленную коммуникацию для изменения параметров
"""
import logging
from PyQt5.QtSerialPort import QSerialPort
from constants import ADS1115_RANGES, ADS1115_SAMPLE_RATES


logger = logging.getLogger(__name__)


class ArduinoConfig:
    """
    Класс для управления конфигурацией Arduino и АЦП
    """
    
    def __init__(self, serial_port: QSerialPort):
        """
        Args:
            serial_port: Открытый Serial порт для связи с Arduino
        """
        self.serial = serial_port
    
    def send_command(self, command: str) -> bool:
        """
        Отправить команду на Arduino
        
        Args:
            command: Команда для отправки (без символа новой строки)
            
        Returns:
            bool: True если команда отправлена успешно
        """
        if not self.serial.isOpen():
            logger.error("Cannot send command: serial port is not open")
            return False
        
        try:
            command_bytes = f"{command}\n".encode('utf-8')
            bytes_written = self.serial.write(command_bytes)
            self.serial.flush()
            
            if bytes_written > 0:
                logger.info(f"Command sent: {command}")
                return True
            else:
                logger.error(f"Failed to send command: {command}")
                return False
                
        except Exception as e:
            logger.error(f"Exception sending command: {e}")
            return False
    
    def set_voltage_range(self, range_mv: int) -> bool:
        """
        Установить диапазон напряжения АЦП
        
        Args:
            range_mv: Диапазон в милливольтах (256, 512, 1024, 2048, 4096, 6144)
            
        Returns:
            bool: True если команда отправлена успешно
        """
        if range_mv not in ADS1115_RANGES:
            logger.error(f"Invalid voltage range: {range_mv}")
            return False
        
        return self.send_command(f"SET_RANGE,{range_mv}")
    
    def set_conversion_rate(self, rate_sps: int) -> bool:
        """
        Установить частоту дискретизации АЦП
        
        Args:
            rate_sps: Частота в SPS (8, 16, 32, 64, 128, 250, 475, 860)
            
        Returns:
            bool: True если команда отправлена успешно
        """
        if rate_sps not in ADS1115_SAMPLE_RATES:
            logger.error(f"Invalid sample rate: {rate_sps}")
            return False
        
        return self.send_command(f"SET_RATE,{rate_sps}")
    
    def set_sampling_interval(self, interval_ms: int) -> bool:
        """
        Установить интервал отправки данных
        
        Args:
            interval_ms: Интервал в миллисекундах (1-1000)
            
        Returns:
            bool: True если команда отправлена успешно
        """
        if interval_ms < 1 or interval_ms > 1000:
            logger.error(f"Invalid sampling interval: {interval_ms}")
            return False
        
        return self.send_command(f"SET_INTERVAL,{interval_ms}")
    
    def get_config(self) -> bool:
        """
        Запросить текущую конфигурацию Arduino
        
        Returns:
            bool: True если команда отправлена успешно
        """
        return self.send_command("GET_CONFIG")
    
    def reset_counter(self) -> bool:
        """
        Сбросить счетчик измерений
        
        Returns:
            bool: True если команда отправлена успешно
        """
        return self.send_command("RESET_COUNTER")


class ArduinoConfigDialog:
    """
    Диалог для настройки параметров Arduino через GUI
    """
    
    @staticmethod
    def show_config_dialog(parent, arduino_config: ArduinoConfig):
        """
        Показать диалог настройки Arduino
        
        Args:
            parent: Родительский виджет
            arduino_config: Экземпляр ArduinoConfig для отправки команд
        """
        from PyQt5 import QtWidgets
        
        dialog = QtWidgets.QDialog(parent)
        dialog.setWindowTitle("Настройка Arduino и АЦП")
        dialog.setMinimumWidth(400)
        
        layout = QtWidgets.QVBoxLayout()
        
        # Диапазон напряжения
        range_group = QtWidgets.QGroupBox("Диапазон напряжения АЦП")
        range_layout = QtWidgets.QHBoxLayout()
        range_label = QtWidgets.QLabel("Диапазон (мВ):")
        range_combo = QtWidgets.QComboBox()
        range_combo.addItems([str(r) for r in ADS1115_RANGES])
        range_combo.setCurrentText("6144")  # По умолчанию
        range_layout.addWidget(range_label)
        range_layout.addWidget(range_combo)
        range_group.setLayout(range_layout)
        layout.addWidget(range_group)
        
        # Частота дискретизации
        rate_group = QtWidgets.QGroupBox("Частота дискретизации АЦП")
        rate_layout = QtWidgets.QHBoxLayout()
        rate_label = QtWidgets.QLabel("Частота (SPS):")
        rate_combo = QtWidgets.QComboBox()
        rate_combo.addItems([str(r) for r in ADS1115_SAMPLE_RATES])
        rate_combo.setCurrentText("860")  # По умолчанию
        rate_layout.addWidget(rate_label)
        rate_layout.addWidget(rate_combo)
        rate_group.setLayout(rate_layout)
        layout.addWidget(rate_group)
        
        # Интервал отправки
        interval_group = QtWidgets.QGroupBox("Интервал отправки данных")
        interval_layout = QtWidgets.QHBoxLayout()
        interval_label = QtWidgets.QLabel("Интервал (мс):")
        interval_spin = QtWidgets.QSpinBox()
        interval_spin.setRange(1, 1000)
        interval_spin.setValue(1)
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(interval_spin)
        interval_group.setLayout(interval_layout)
        layout.addWidget(interval_group)
        
        # Кнопки
        button_layout = QtWidgets.QHBoxLayout()
        
        apply_button = QtWidgets.QPushButton("Применить")
        get_config_button = QtWidgets.QPushButton("Получить конфигурацию")
        reset_button = QtWidgets.QPushButton("Сбросить счетчик")
        close_button = QtWidgets.QPushButton("Закрыть")
        
        button_layout.addWidget(apply_button)
        button_layout.addWidget(get_config_button)
        button_layout.addWidget(reset_button)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        # Обработчики кнопок
        def on_apply():
            voltage_range = int(range_combo.currentText())
            sample_rate = int(rate_combo.currentText())
            interval = interval_spin.value()
            
            success = True
            success &= arduino_config.set_voltage_range(voltage_range)
            success &= arduino_config.set_conversion_rate(sample_rate)
            success &= arduino_config.set_sampling_interval(interval)
            
            if success:
                QtWidgets.QMessageBox.information(
                    dialog, "Успех", 
                    "Настройки успешно отправлены на Arduino"
                )
            else:
                QtWidgets.QMessageBox.warning(
                    dialog, "Ошибка",
                    "Не удалось отправить все настройки"
                )
        
        def on_get_config():
            arduino_config.get_config()
            QtWidgets.QMessageBox.information(
                dialog, "Запрос отправлен",
                "Запрос конфигурации отправлен. Проверьте консоль для получения ответа."
            )
        
        def on_reset():
            if arduino_config.reset_counter():
                QtWidgets.QMessageBox.information(
                    dialog, "Успех",
                    "Счетчик измерений сброшен"
                )
        
        apply_button.clicked.connect(on_apply)
        get_config_button.clicked.connect(on_get_config)
        reset_button.clicked.connect(on_reset)
        close_button.clicked.connect(dialog.accept)
        
        dialog.exec_()
