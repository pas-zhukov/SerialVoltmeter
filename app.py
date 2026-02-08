import typing
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtCore import QIODevice, QTimer
from PyQt5.QtSerialPort import QSerialPort
import time
import serial.tools.list_ports
import datetime
import shutil
import os
import pandas as pd
import csv
import sys
import pyqtgraph as pg
import math
import logging

matplotlib.use('Qt5Agg')

from models import TimeUnits
from constants import *
from serial_handler import SerialReaderThread, DataBuffer
from file_handler import DataFileWriter, DataFileReader
from plot_widget import PlotManager
from arduino_config import ArduinoConfig, ArduinoConfigDialog

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT
)
logger = logging.getLogger(__name__)


def resource_path(relative_path):
    """Получает абсолютный путь к ресурсу, работает для dev и для PyInstaller"""
    try:
        # PyInstaller создает временную папку и хранит путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class FileViewerWindow(QtWidgets.QDialog):
    """Окно для просмотра файла записи с полным графиком и элементами навигации"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Просмотр данных")
        # Устанавливаем начальный размер окна
        self.resize(900, 600)
        
        # Устанавливаем флаги окна для поддержки разворачивания на весь экран
        self.setWindowFlags(
            QtCore.Qt.Window |  # Делаем независимым окном
            QtCore.Qt.WindowMinimizeButtonHint |  # Кнопка минимизации
            QtCore.Qt.WindowMaximizeButtonHint |  # Кнопка максимизации
            QtCore.Qt.WindowCloseButtonHint  # Кнопка закрытия
        )
        
        # Разрешаем изменение размера окна
        self.setSizeGripEnabled(True)
        
        self.setup_ui()
    
    def setup_ui(self):
        # Создаем основной layout
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # Создаем график matplotlib
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        
        # Добавляем панель инструментов навигации
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        # Добавляем элементы в layout
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        # Добавляем информационную панель снизу
        info_layout = QtWidgets.QHBoxLayout()
        self.file_info_label = QtWidgets.QLabel("Файл: ")
        self.data_info_label = QtWidgets.QLabel("Точек: 0")
        self.time_info_label = QtWidgets.QLabel("Время записи: 0 с")
        
        info_layout.addWidget(self.file_info_label)
        info_layout.addWidget(self.data_info_label)
        info_layout.addWidget(self.time_info_label)
        
        layout.addLayout(info_layout)
        
        # Устанавливаем политику размера для canvas, чтобы он растягивался вместе с окном
        self.canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        
        # Устанавливаем минимальный размер окна
        self.setMinimumSize(600, 400)
    
    def resizeEvent(self, event):
        """Обработчик изменения размера окна"""
        super().resizeEvent(event)
        # Обновляем график при изменении размера окна
        self.figure.tight_layout()
        self.canvas.draw()
    
    def load_data(self, filename):
        """Загружает данные из файла CSV и отображает их на графике"""
        try:
            # Используем DataFileReader для чтения файла
            times, data, error = DataFileReader.read_file(filename)
            
            if error:
                QtWidgets.QMessageBox.warning(self, "Ошибка", error)
                logger.error(f"Failed to load data from {filename}: {error}")
                return False
            
            # Очищаем график
            self.ax.clear()
            
            # Строим график
            self.ax.plot(times, data, '-', linewidth=1)
            
            # Настраиваем оси
            self.ax.set_xlabel('Время, с')
            self.ax.set_ylabel('Напряжение, мВ')
            self.ax.grid(True)
            
            # Масштабируем график, чтобы видеть все данные
            self.ax.set_xlim(min(times), max(times))
            
            if len(data) > 1:
                min_voltage = min(data)
                max_voltage = max(data)
                padding = (max_voltage - min_voltage) * 0.1
                if padding < 10:
                    padding = 10
                self.ax.set_ylim(min_voltage - padding, max_voltage + padding)
            
            # Заголовок графика
            self.ax.set_title(f'Данные из файла: {os.path.basename(filename)}')
            
            # Обновляем информационные метки
            self.file_info_label.setText(f"Файл: {os.path.basename(filename)}")
            self.data_info_label.setText(f"Точек: {len(data)}")
            
            if times:
                duration = max(times)
                self.time_info_label.setText(f"Время записи: {duration:.1f} с")
            
            # Обновляем canvas
            self.canvas.draw()
            
            return True
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл: {str(e)}")
            return False


class ComSelectorDialog(QtWidgets.QDialog):
    """Диалог для ручного выбора COM порта"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = uic.loadUi(resource_path("comSelector.ui"), self)
        self.setWindowTitle("Выбор COM порта")
        
        # Заполняем список доступных портов
        self.refresh_ports()
        
        # Подключаем обработчики
        self.ui.openB.clicked.connect(self.accept)
        self.ui.closeB.clicked.connect(self.reject)
        
        # Устанавливаем размер окна
        self.setFixedSize(self.size())
    
    def refresh_ports(self):
        """Обновляет список доступных COM портов"""
        self.ui.comL.clear()
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.ui.comL.addItems(ports)
    
    def get_selected_port(self):
        """Возвращает выбранный COM порт"""
        return self.ui.comL.currentText()


class SerialVoltmeterApp(QtWidgets.QApplication):
    def __init__(self, argv: typing.List[str]):
        super().__init__(argv)
        logger.info("Starting Serial Voltmeter application")
        
        # Файл записи
        self.file_writer = None
        self.recording = False
        
        # Данные
        self.data_buffer = DataBuffer(max_size=MAX_DATA_BUFFER_SIZE)
        self.start_counter = None  # Начальный счетчик измерений
        self.system_start_time = None  # Системное время начала записи
        self.last_console_update_time = 0
        
        # Настройки
        self.window_size = DEFAULT_WINDOW_SIZE_S
        self.show_current_values = True
        self.skip_measurements = 0
        self.measurement_skip_counter = 0
        
        # Статистика
        self.received_data_count = 0
        self.saved_data_count = 0
        
        # Таймер записи
        self.record_timer = None
        self.timed_recording = False
        
        # Serial поток
        self.serial_thread = None
        
        # Arduino конфигурация
        self.arduino_config = None
        
        # UI
        self.ui = uic.loadUi(resource_path("mainForm.ui"))
        self.ui.setWindowTitle("Serial Voltmeter v2.0")
        
        # Явно создаем меню, если оно не было создано при загрузке UI
        if not hasattr(self.ui, 'menubar') or not self.ui.menubar:
            self.ui.menubar = QtWidgets.QMenuBar(self.ui)
            self.ui.setMenuBar(self.ui.menubar)
        
        # Создаем меню "Файл", если его нет
        # if not hasattr(self.ui, 'menuFile') or not self.ui.file:
        #     self.ui.file = QtWidgets.QMenu("Файл", self.ui.menubar)
        #     self.ui.menubar.addMenu(self.ui.file)
        
        # Создаем действие "Выход", если его нет
        if not hasattr(self.ui, 'exit') or not self.ui.exit:
            self.ui.exit = QtWidgets.QAction("Выход", self.ui)
            self.ui.exit.triggered.connect(self.exit)
            self.ui.file.addAction(self.ui.exit)
        
        # Serial порт
        self.serial = QSerialPort()
        self.serial.setBaudRate(SERIAL_BAUD_RATE)

        # Настройка графика (используем pyqtgraph для производительности)
        self.plot_manager = PlotManager(self.ui.plot, use_pyqtgraph=True)

        # Таймер для обновления графика
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot_from_buffer)
        self.update_timer.start(PLOT_UPDATE_INTERVAL_MS)

        # Таймер для вывода статистики
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.show_stats)
        self.stats_timer.start(STATS_UPDATE_INTERVAL_MS)

        self.init_gui()
        self.lastWindowClosed.connect(self.stop_recording)

        self.ui.show()
        logger.info("Application UI initialized")
        self.exec()

    def init_gui(self):
        self.ui.connectButton.clicked.connect(self.connect_device)
        self.ui.disconnectButton.clicked.connect(self.disconnect_device)
        self.ui.exit.triggered.connect(self.exit)
        self.ui.startButton.clicked.connect(self.start_recording)
        self.ui.stopButton.clicked.connect(self.stop_recording)
        self.ui.refreshPortsButton.clicked.connect(self.refresh_ports)
        
        # Добавляем действие "Открыть файл записи" в меню "Файл"
        self.ui.open_file_action = QtWidgets.QAction("Открыть файл записи", self.ui)
        self.ui.open_file_action.triggered.connect(self.open_file)
        
        # Добавляем действие в меню Файл перед действием "Выход"
        self.ui.menuFile.insertAction(self.ui.exit, self.ui.open_file_action)
        # Добавляем разделитель
        self.ui.menuFile.insertSeparator(self.ui.exit)
        
        # Добавляем действие "Настройка Arduino" в меню (если есть меню настроек)
        if hasattr(self.ui, 'menuSettings'):
            self.ui.arduinoConfigAction = QtWidgets.QAction("⚙ Настройка Arduino и АЦП", self.ui)
            self.ui.arduinoConfigAction.triggered.connect(self.show_arduino_config)
            self.ui.arduinoConfigAction.setEnabled(False)  # Отключено до подключения
            self.ui.menuSettings.addAction(self.ui.arduinoConfigAction)
        else:
            # Создаем меню настроек если его нет
            self.ui.menuSettings = QtWidgets.QMenu("Настройки", self.ui.menubar)
            self.ui.menubar.addMenu(self.ui.menuSettings)
            self.ui.arduinoConfigAction = QtWidgets.QAction("⚙ Настройка Arduino и АЦП", self.ui)
            self.ui.arduinoConfigAction.triggered.connect(self.show_arduino_config)
            self.ui.arduinoConfigAction.setEnabled(False)
            self.ui.menuSettings.addAction(self.ui.arduinoConfigAction)
        
        # Инициализируем список COM портов
        self.refresh_ports()
        
        # Показываем элементы интерфейса для выбора времени записи
        try:
            # Восстанавливаем видимость элементов
            self.ui.recordLength.setVisible(True)
            self.ui.recordLengthTimeUnits.setVisible(True)
            if hasattr(self.ui, 'label_4'):
                self.ui.label_4.setVisible(True)
                
            # Устанавливаем значения по умолчанию
            self.ui.recordLength.setValue(5)  # 5 минут по умолчанию
            self.ui.recordLengthTimeUnits.clear()
            self.ui.recordLengthTimeUnits.addItems(["секунды", "минуты", "часы"])
            self.ui.recordLengthTimeUnits.setCurrentIndex(1)  # Минуты по умолчанию
            
            # Добавляем флажок для записи по времени
            self.ui.timedRecordCheckBox = QtWidgets.QCheckBox("Запись по времени")
            self.ui.timedRecordCheckBox.setChecked(False)
            
            # Добавляем флажок на форму рядом с элементами выбора времени
            if hasattr(self.ui, 'gridLayout'):
                self.ui.gridLayout.addWidget(self.ui.timedRecordCheckBox, 0, 3)
            
            # Соединяем сигнал изменения состояния флажка с функцией-обработчиком
            self.ui.timedRecordCheckBox.stateChanged.connect(self.on_timed_record_changed)
            
            # Начальная блокировка элементов выбора продолжительности записи
            self.ui.recordLength.setEnabled(False)
            self.ui.recordLengthTimeUnits.setEnabled(False)
            
            # Настройка элементов управления графиком
            self.ui.windowSize.valueChanged.connect(self.on_window_size_changed)
            self.ui.yAxisRange.currentIndexChanged.connect(self.on_y_axis_range_changed)
            self.ui.yAxisMin.valueChanged.connect(self.on_y_axis_min_changed)
            self.ui.yAxisMax.valueChanged.connect(self.on_y_axis_max_changed)
            
            # Устанавливаем значение размера окна по умолчанию
            self.window_size = self.ui.windowSize.value()
            
            # Добавляем чекбокс под консолью
            self.ui.showValuesCheckBox = QtWidgets.QCheckBox("Выводить текущие значения")
            self.ui.showValuesCheckBox.setChecked(True)  # По умолчанию включен
            
            # Добавляем чекбокс под консоль
            if hasattr(self.ui, 'gridLayout_3'):
                self.ui.gridLayout_3.addWidget(self.ui.showValuesCheckBox, 1, 0)
            else:
                # Если не нашли gridLayout_3, добавляем в основной лейаут консоли
                layout = QtWidgets.QVBoxLayout()
                layout.addWidget(self.ui.console)
                layout.addWidget(self.ui.showValuesCheckBox)
                self.ui.consoleBox.setLayout(layout)
            
            # Соединяем сигнал изменения состояния флажка с функцией-обработчиком
            self.ui.showValuesCheckBox.stateChanged.connect(self.on_show_values_changed)
            
        except Exception as e:
            self.ui.console.appendPlainText(f"Ошибка при инициализации интерфейса: {str(e)}")
        
        # Подключаем обработчик закрытия окна
        self.ui.closeEvent = self.closeEvent
    
    def open_file(self):
        """Открывает диалог выбора файла и отображает данные из файла"""
        try:
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(
                self.ui,
                "Открыть файл записи",
                "",
                "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
            )
            
            if filename:
                # Создаем окно просмотра файла
                viewer = FileViewerWindow(self.ui)
                
                # Загружаем данные
                if viewer.load_data(filename):
                    # Показываем окно, если данные успешно загружены
                    viewer.exec_()
                else:
                    viewer.close()
                
        except Exception as e:
            self.ui.console.appendPlainText(f"Ошибка при открытии файла: {str(e)}")
    
    def on_show_values_changed(self, state):
        """Обработчик изменения состояния флажка вывода текущих значений"""
        try:
            self.show_current_values = state == QtCore.Qt.Checked
            if self.show_current_values:
                self.ui.console.appendPlainText("Вывод текущих значений включен")
            else:
                self.ui.console.appendPlainText("Вывод текущих значений отключен")
        except Exception as e:
            self.ui.console.appendPlainText(f"Ошибка при изменении режима вывода: {str(e)}")
    
    def on_timed_record_changed(self, state):
        """Обработчик изменения состояния флажка записи по времени"""
        try:
            # Если флажок установлен, разблокируем элементы выбора времени
            is_checked = state == QtCore.Qt.Checked
            
            # Обрабатываем элементы выбора продолжительности записи
            if hasattr(self.ui, 'recordLength'):
                self.ui.recordLength.setEnabled(is_checked)
            if hasattr(self.ui, 'recordLengthTimeUnits'):
                self.ui.recordLengthTimeUnits.setEnabled(is_checked)
            
            # Если флажок установлен, выводим сообщение о включении записи по времени
            if is_checked:
                # Получаем выбранное время и единицы измерения
                record_length = self.ui.recordLength.value()
                time_unit = self.ui.recordLengthTimeUnits.currentText()
                
                # Формируем человекочитаемую строку
                if time_unit == "секунды":
                    time_text = f"{record_length} секунд"
                elif time_unit == "минуты":
                    time_text = f"{record_length} минут"
                else:  # часы
                    time_text = f"{record_length} часов"
                
                self.ui.console.appendPlainText(f"Включена запись по времени: {time_text}")
            else:
                self.ui.console.appendPlainText("Запись по времени отключена")
            
        except Exception as e:
            self.ui.console.appendPlainText(f"Ошибка при изменении режима записи: {str(e)}")

    def show_stats(self):
        """Отображаем статистику полученных и сохраненных данных"""
        if self.recording and self.system_start_time:
            # Вычисляем прошедшее время
            elapsed_time = time.time() - self.system_start_time
            
            # Формируем строку статистики
            stats_parts = [
                f"📊 получено: {self.received_data_count}",
                f"сохранено: {self.saved_data_count}",
                f"время: {elapsed_time:.1f} с"
            ]
            
            # Добавляем оставшееся время для записи по таймеру
            if self.timed_recording and self.record_timer and self.record_timer.isActive():
                remaining_ms = self.record_timer.remainingTime()
                if remaining_ms > 0:
                    remaining_sec = remaining_ms / 1000.0
                    stats_parts.append(f"осталось: {remaining_sec:.1f} с")
            
            # Добавляем размер буфера
            buffer_size = self.data_buffer.size()
            stats_parts.append(f"буфер: {buffer_size} точек")
            
            self.ui.console.appendPlainText(" | ".join(stats_parts))
            self.processEvents()

    def on_data_received(self, counter: int, voltage: float):
        """Обработка полученных данных из Serial потока"""
        self.received_data_count += 1
        
        # Вычисляем время в секундах
        if self.start_counter is None:
            self.start_counter = counter
            self.system_start_time = time.time()
        
        time_sec = (counter - self.start_counter) * ARDUINO_SAMPLING_INTERVAL_MS / 1000.0
        
        # Выводим данные в консоль (не каждый раз)
        current_time = time.time()
        if current_time - self.last_console_update_time > CONSOLE_UPDATE_INTERVAL_S and self.show_current_values:
            self.ui.console.appendPlainText(f"Время: {time_sec:.2f} с, Напряжение: {voltage:.2f} мВ")
            self.last_console_update_time = current_time
        
        # Если запись активна, добавляем данные
        if self.recording:
            # Проверяем пропуск измерений
            if self.skip_measurements > 0:
                self.measurement_skip_counter += 1
                if self.measurement_skip_counter % (self.skip_measurements + 1) != 0:
                    return
            
            # Добавляем в буфер для графика
            self.data_buffer.add_data(time_sec, voltage)
            
            # Записываем в файл
            if self.file_writer and self.file_writer.is_open():
                self.file_writer.write_measurement(time_sec, voltage)
                self.saved_data_count += 1
    
    def on_serial_error(self, error_msg: str):
        """Обработка ошибок из Serial потока"""
        self.ui.console.appendPlainText(f"❌ Ошибка: {error_msg}")
        logger.error(f"Serial error: {error_msg}")
    
    def on_info_message(self, message: str):
        """Обработка информационных сообщений из Serial потока"""
        self.ui.console.appendPlainText(message)
    
    def on_connection_lost(self):
        """Обработка потери соединения"""
        self.ui.console.appendPlainText("❌ Соединение потеряно!")
        logger.error("Connection lost")
        if self.recording:
            self.stop_recording()
        self.disconnect_device()

    def update_plot_from_buffer(self):
        # Проверяем наличие данных
        if self.data_buffer.size() == 0:
            return
        
        # Получаем данные для текущего окна
        window_times, window_voltages = self.data_buffer.get_windowed_data(self.window_size)
        
        # Если данных нет в окне, выходим
        if not window_times:
            return
        
        # Обновляем график через PlotManager
        y_mode = self.ui.yAxisRange.currentIndex()
        y_min = self.ui.yAxisMin.value()
        y_max = self.ui.yAxisMax.value()
        
        self.plot_manager.update_plot(
            window_times, window_voltages,
            self.window_size, y_mode, y_min, y_max
        )
        
        # Обрабатываем события для отзывчивости интерфейса
        # (pyqtgraph намного быстрее, поэтому не тормозит UI)
        self.processEvents()

    def show_com_selector(self):
        """Показывает диалог выбора COM порта"""
        if self.recording:
            QtWidgets.QMessageBox.warning(
                self.ui,
                "Внимание",
                "Невозможно изменить COM порт во время записи"
            )
            return
            
        dialog = ComSelectorDialog(self.ui)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            selected_port = dialog.get_selected_port()
            if selected_port:
                # Если порт уже открыт, закрываем его
                if self.serial.isOpen():
                    self.serial.close()
                    self.ui.console.appendPlainText("Порт закрыт")
                
                # Устанавливаем новый порт
                self.serial.setPortName(selected_port)
                if self.serial.open(QIODevice.ReadOnly):
                    self.ui.console.appendPlainText(f"Подключено к {selected_port}")
                    self.ui.startButton.setEnabled(True)
                    self.ui.connectButton.setEnabled(False)
                else:
                    self.ui.console.appendPlainText(f"Ошибка при подключении к {selected_port}")
                    self.ui.startButton.setEnabled(False)
                    self.ui.connectButton.setEnabled(True)

    def connect_device(self):
        """Подключает устройство"""
        self.ui.connectButton.setEnabled(False)
        self.ui.console.appendPlainText("Подключение к устройству...")
        self.processEvents()
        
        selected_port = self.ui.comPortSelect.currentText()
        
        # Если выбран автоматический режим
        if selected_port == "Авто":
            ports = [port.device for port in serial.tools.list_ports.comports()]
            if not ports:
                self.ui.console.appendPlainText("❌ ОШИБКА: Не найдены доступные COM-порты")
                self.ui.console.appendPlainText("💡 Подключите Arduino к компьютеру")
                logger.error("No COM ports found")
                self.ui.connectButton.setEnabled(True)
                return
            
            self.ui.console.appendPlainText(f"🔍 Найдено портов: {len(ports)}, начинаю поиск Arduino...")
            self.processEvents()
            
            # Пробуем подключиться к каждому порту
            for i, port in enumerate(ports, 1):
                try:
                    self.ui.console.appendPlainText(f"   [{i}/{len(ports)}] Проверка {port}...")
                    self.processEvents()
                    
                    self.serial.setPortName(port)
                    if self.serial.open(QIODevice.ReadOnly):
                        # _on_device_connected сам проверит устройство
                        self._on_device_connected(port)
                        
                        # Если подключение успешно, выходим
                        if self.serial.isOpen():
                            return
                except Exception as e:
                    self.ui.console.appendPlainText(f"   ⚠ {port}: {str(e)}")
                    logger.error(f"Failed to connect to {port}: {e}")
                    self.processEvents()
            
            self.ui.console.appendPlainText("❌ ОШИБКА: Arduino не найдена ни на одном порту")
            self.ui.console.appendPlainText("💡 Убедитесь что:")
            self.ui.console.appendPlainText("   • Arduino подключена к USB")
            self.ui.console.appendPlainText("   • Драйверы установлены")
            self.ui.console.appendPlainText("   • Загружена правильная прошивка")
            logger.error("Failed to connect to any port")
            self.ui.connectButton.setEnabled(True)
        else:
            # Подключаемся к выбранному порту
            try:
                self.serial.setPortName(selected_port)
                if self.serial.open(QIODevice.ReadOnly):
                    self._on_device_connected(selected_port)
                    # Если подключение не удалось, кнопка уже восстановлена в _on_device_connected
                else:
                    self.ui.console.appendPlainText(f"❌ Не удалось открыть порт {selected_port}")
                    self.ui.console.appendPlainText(f"💡 Порт может быть занят другой программой")
                    logger.error(f"Failed to open port {selected_port}")
                    self.ui.connectButton.setEnabled(True)
            except Exception as e:
                self.ui.console.appendPlainText(f"❌ Ошибка при подключении к {selected_port}: {str(e)}")
                logger.error(f"Exception connecting to {selected_port}: {e}")
                self.ui.connectButton.setEnabled(True)
    
    def _on_device_connected(self, port: str):
        """Обработка успешного подключения к устройству"""
        self.ui.console.appendPlainText(f"🔌 Порт {port} открыт, проверка устройства...")
        logger.info(f"Port {port} opened, checking device...")
        self.processEvents()
        
        # Проверяем, что это действительно наш Arduino
        if not self._verify_arduino_device():
            self.ui.console.appendPlainText(f"❌ ОШИБКА: Arduino не отвечает на порту {port}")
            self.ui.console.appendPlainText(f"💡 Возможные причины:")
            self.ui.console.appendPlainText(f"   • Arduino не подключена")
            self.ui.console.appendPlainText(f"   • Неправильная прошивка")
            self.ui.console.appendPlainText(f"   • Неправильная скорость порта")
            self.ui.console.appendPlainText(f"   • Устройство перезагружается")
            logger.error(f"Arduino verification failed on port {port}")
            
            # Закрываем порт
            if self.serial.isOpen():
                self.serial.close()
            
            # Восстанавливаем кнопки
            self.ui.connectButton.setEnabled(True)
            return
        
        self.ui.console.appendPlainText(f"✓ Arduino успешно подключена к {port}")
        logger.info(f"Arduino verified on {port}")
        
        # Создаем конфигуратор Arduino
        self.arduino_config = ArduinoConfig(self.serial)
        
        # Создаем и запускаем поток для чтения данных
        self.serial_thread = SerialReaderThread(self.serial)
        self.serial_thread.data_received.connect(self.on_data_received)
        self.serial_thread.error_occurred.connect(self.on_serial_error)
        self.serial_thread.info_message.connect(self.on_info_message)
        self.serial_thread.connection_lost.connect(self.on_connection_lost)
        self.serial_thread.start()
        
        # Обновляем интерфейс
        self.ui.startButton.setEnabled(True)
        self.ui.connectButton.setEnabled(False)
        self.ui.disconnectButton.setEnabled(True)
        self.ui.comPortSelect.setEnabled(False)
        self.ui.refreshPortsButton.setEnabled(False)
        self.ui.comPortSelect.setCurrentText(port)
        
        # Включаем пункт меню настройки Arduino
        if hasattr(self.ui, 'arduinoConfigAction'):
            self.ui.arduinoConfigAction.setEnabled(True)
    
    def _verify_arduino_device(self, timeout_seconds: int = DEVICE_VERIFICATION_TIMEOUT_S) -> bool:
        """
        Проверяет, что подключенное устройство - это наш Arduino с правильной прошивкой
        
        Args:
            timeout_seconds: Максимальное время ожидания ответа
            
        Returns:
            True если устройство отвечает правильно, False иначе
        """
        if not self.serial.isOpen():
            return False
        
        logger.info(f"Verifying Arduino device, timeout={timeout_seconds}s")
        start_time = time.time()
        received_valid_data = False
        
        # Ждем данные или сообщения от Arduino
        while time.time() - start_time < timeout_seconds:
            # Проверяем наличие данных
            if self.serial.waitForReadyRead(100):  # Ждем 100 мс
                try:
                    while self.serial.canReadLine():
                        line = str(self.serial.readLine(), 'utf-8').strip()
                        
                        if not line:
                            continue
                        
                        logger.debug(f"Received during verification: {line}")
                        
                        # Проверяем информационные сообщения от Arduino
                        if line.startswith(('INFO:', 'READY:', 'WARNING:', 'ERROR:', 'CONFIG:')):
                            logger.info(f"Arduino identified by message: {line}")
                            return True
                        
                        # Проверяем формат данных измерений (counter,voltage)
                        parts = line.split(',')
                        if len(parts) == 2:
                            try:
                                counter = int(parts[0])
                                voltage = float(parts[1])
                                logger.info(f"Arduino identified by data format: counter={counter}, voltage={voltage}")
                                return True
                            except (ValueError, IndexError):
                                pass
                
                except Exception as e:
                    logger.debug(f"Error during verification: {e}")
            
            # Обрабатываем события для отзывчивости UI
            self.processEvents()
        
        logger.warning(f"Arduino verification timeout after {timeout_seconds}s")
        return False

    def disconnect_device(self):
        """Отключает устройство"""
        if self.recording:
            self.stop_recording()
        
        # Останавливаем поток чтения
        if self.serial_thread and self.serial_thread.isRunning():
            self.serial_thread.stop()
            self.serial_thread.wait(2000)  # Ждем до 2 секунд
            logger.info("Serial reader thread stopped")
        
        # Закрываем порт
        if self.serial.isOpen():
            self.serial.close()
            self.ui.console.appendPlainText("✓ Устройство отключено")
            logger.info("Device disconnected")
            
        # Обновляем интерфейс
        self.ui.startButton.setEnabled(False)
        self.ui.disconnectButton.setEnabled(False)
        self.ui.connectButton.setEnabled(True)
        self.ui.comPortSelect.setEnabled(True)
        self.ui.refreshPortsButton.setEnabled(True)

    def start_recording(self):
        if not self.recording:
            if not self.serial.isOpen():
                self.ui.console.appendPlainText("❌ ОШИБКА: Сначала подключитесь к прибору")
                logger.error("Attempted to start recording without connection")
                return
                
            self.recording = True
            self.data_buffer.clear()
            self.start_counter = None
            self.system_start_time = None
            self.received_data_count = 0
            self.saved_data_count = 0
            self.measurement_skip_counter = 0
            
            # Получаем значение пропуска измерений
            self.skip_measurements = self.ui.skipMeasurements.value()
            logger.info(f"Starting recording with skip={self.skip_measurements}")
            
            # Блокируем элементы настройки времени записи
            if hasattr(self.ui, 'recordLength'):
                self.ui.recordLength.setEnabled(False)
            if hasattr(self.ui, 'recordLengthTimeUnits'):
                self.ui.recordLengthTimeUnits.setEnabled(False)
            if hasattr(self.ui, 'timedRecordCheckBox'):
                self.ui.timedRecordCheckBox.setEnabled(False)
            
            # Проверяем, включена ли запись по времени
            self.timed_recording = False
            if hasattr(self.ui, 'timedRecordCheckBox') and self.ui.timedRecordCheckBox.isChecked():
                self.timed_recording = True
                
                # Получаем время записи
                record_length = self.ui.recordLength.value()
                time_unit = self.ui.recordLengthTimeUnits.currentText()
                
                # Преобразуем в миллисекунды
                multiplier = TIME_UNITS_MULTIPLIERS.get(time_unit, 1)
                duration_ms = record_length * multiplier * 1000
                
                # Создаем таймер для автоматической остановки
                if self.record_timer is None:
                    self.record_timer = QTimer()
                    self.record_timer.setSingleShot(True)
                    self.record_timer.timeout.connect(self.stop_recording)
                
                self.record_timer.start(duration_ms)
                self.ui.console.appendPlainText(f"⏱ Начата запись на {record_length} {time_unit}")
                logger.info(f"Timed recording started: {record_length} {time_unit}")
            
            # Создаем файл для записи
            self.file_writer = DataFileWriter()
            if not self.file_writer.open():
                self.ui.console.appendPlainText("❌ Ошибка при создании файла записи")
                logger.error("Failed to open data file")
                self.recording = False
                self.file_writer = None
                return
            
            self.ui.console.appendPlainText(f"📁 Файл создан: {self.file_writer.filename}")
            logger.info(f"Recording started to file: {self.file_writer.filename}")
            
            # Обновляем интерфейс
            self.ui.startButton.setEnabled(False)
            self.ui.stopButton.setEnabled(True)
            self.ui.console.appendPlainText("✓ Запись начата")
            self.processEvents()

    def stop_recording(self):
        if self.recording:
            self.recording = False
            logger.info("Stopping recording")
            
            # Разблокируем элементы настройки времени записи
            if hasattr(self.ui, 'recordLength'):
                self.ui.recordLength.setEnabled(True)
            if hasattr(self.ui, 'recordLengthTimeUnits'):
                self.ui.recordLengthTimeUnits.setEnabled(True)
            if hasattr(self.ui, 'timedRecordCheckBox'):
                self.ui.timedRecordCheckBox.setEnabled(True)
                
                # Применяем правило блокировки в зависимости от состояния чекбокса
                is_checked = self.ui.timedRecordCheckBox.isChecked()
                if hasattr(self.ui, 'recordLength'):
                    self.ui.recordLength.setEnabled(is_checked)
                if hasattr(self.ui, 'recordLengthTimeUnits'):
                    self.ui.recordLengthTimeUnits.setEnabled(is_checked)
            
            # Останавливаем таймер записи
            if self.record_timer and self.record_timer.isActive():
                self.record_timer.stop()
            
            # Выводим причину остановки
            if self.timed_recording:
                self.ui.console.appendPlainText("⏱ Запись остановлена по таймеру")
                logger.info("Recording stopped by timer")
            
            # Закрываем файл
            if self.file_writer:
                count, filename = self.file_writer.close()
                
                # Вычисляем время записи
                elapsed_time = 0
                if self.system_start_time:
                    elapsed_time = time.time() - self.system_start_time
                
                self.ui.console.appendPlainText(
                    f"💾 Сохранено {count} измерений за {elapsed_time:.1f} с в файл {filename}"
                )
                logger.info(f"Recording saved: {count} measurements in {elapsed_time:.1f}s")
                
                # Предлагаем сохранить под другим именем
                if os.path.exists(filename):
                    new_filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                        self.ui,
                        "Сохранить файл как",
                        "",
                        "CSV Files (*.csv);;All Files (*)"
                    )
                    if new_filename:
                        try:
                            shutil.copy2(filename, new_filename)
                            self.ui.console.appendPlainText(f"💾 Файл скопирован: {new_filename}")
                            logger.info(f"File copied to: {new_filename}")
                            
                            # Предлагаем открыть для просмотра
                            reply = QtWidgets.QMessageBox.question(
                                self.ui,
                                "Просмотр данных",
                                "Открыть файл для просмотра?",
                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                QtWidgets.QMessageBox.Yes
                            )
                            
                            if reply == QtWidgets.QMessageBox.Yes:
                                viewer = FileViewerWindow(self.ui)
                                if viewer.load_data(new_filename):
                                    viewer.exec_()
                        except Exception as e:
                            self.ui.console.appendPlainText(f"❌ Ошибка копирования: {str(e)}")
                            logger.error(f"Error copying file: {e}")
                
                self.file_writer = None
            
            # Обновляем интерфейс
            self.ui.startButton.setEnabled(True)
            self.ui.stopButton.setEnabled(False)
            self.ui.console.appendPlainText("✓ Запись остановлена")
            self.processEvents()

    def refresh_ports(self):
        """Обновляет список доступных COM портов"""
        current_port = self.ui.comPortSelect.currentText()
        self.ui.comPortSelect.clear()
        
        # Добавляем опцию автоматического выбора
        self.ui.comPortSelect.addItem("Авто")
        
        # Добавляем доступные порты
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.ui.comPortSelect.addItems(ports)
        
        # Восстанавливаем выбранный порт, если он все еще доступен
        if current_port in ports:
            self.ui.comPortSelect.setCurrentText(current_port)
    
    def show_arduino_config(self):
        """Показать диалог настройки Arduino"""
        if not self.arduino_config:
            QtWidgets.QMessageBox.warning(
                self.ui,
                "Ошибка",
                "Arduino не подключен"
            )
            return
        
        if self.recording:
            QtWidgets.QMessageBox.warning(
                self.ui,
                "Предупреждение",
                "Невозможно изменить настройки во время записи"
            )
            return
        
        ArduinoConfigDialog.show_config_dialog(self.ui, self.arduino_config)

    def on_window_size_changed(self, value):
        """Обработчик изменения размера окна графика"""
        self.window_size = value
        self.ui.console.appendPlainText(f"📏 Размер окна графика: {value} с")
        logger.info(f"Plot window size changed to {value}s")
        self.update_plot_from_buffer()

    def on_y_axis_range_changed(self, index):
        """Обработчик изменения режима диапазона оси Y"""
        is_dynamic = index == 0  # 0 - Динамически, 1 - Настроить
        
        # Включаем/отключаем элементы настройки диапазона
        self.ui.yAxisMin.setEnabled(not is_dynamic)
        self.ui.yAxisMax.setEnabled(not is_dynamic)
        
        if is_dynamic:
            self.ui.console.appendPlainText("Диапазон оси Y установлен на динамический")
        else:
            self.ui.console.appendPlainText("Диапазон оси Y установлен на фиксированный")
        
        self.update_plot_from_buffer()  # Обновляем график с новыми настройками

    def on_y_axis_min_changed(self, value):
        """Обработчик изменения минимального значения оси Y"""
        self.ui.console.appendPlainText(f"Минимальное значение оси Y изменено на {value} мВ")
        self.update_plot_from_buffer()  # Обновляем график с новыми настройками

    def on_y_axis_max_changed(self, value):
        """Обработчик изменения максимального значения оси Y"""
        self.ui.console.appendPlainText(f"Максимальное значение оси Y изменено на {value} мВ")
        self.update_plot_from_buffer()  # Обновляем график с новыми настройками

    def exit(self):
        """Обработчик выхода из программы через меню"""
        self.check_exit()

    def closeEvent(self, event):
        """Обработчик закрытия окна по крестику"""
        if self.check_exit():
            event.accept()
        else:
            event.ignore()

    def check_exit(self):
        """Проверяет возможность выхода и запрашивает подтверждение"""
        # Если идет запись, предупреждаем пользователя
        if self.recording:
            reply = QtWidgets.QMessageBox.question(
                self.ui,
                "Внимание",
                "Сейчас идет запись данных. Вы уверены, что хотите выйти?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return False
            # Останавливаем запись
            self.stop_recording()
        
        # Запрашиваем подтверждение выхода
        reply = QtWidgets.QMessageBox.question(
            self.ui,
            "Подтверждение",
            "Вы уверены, что хотите выйти?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            # Закрываем все ресурсы
            if self.serial.isOpen():
                self.serial.close()
            if hasattr(self, 'file') and self.file:
                self.file.close()
            # Завершаем приложение
            sys.exit(0)
            return True
        return False


def main():
    app = SerialVoltmeterApp([])
    return app.exec_()


if __name__ == "__main__":
    main()
