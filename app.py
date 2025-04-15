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
from scipy.signal import savgol_filter

matplotlib.use('Qt5Agg')

from models import TimeUnits


def resource_path(relative_path):
    """Получает абсолютный путь к ресурсу, работает для dev и для PyInstaller"""
    try:
        # PyInstaller создает временную папку и хранит путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class SmoothSettingsDialog(QtWidgets.QDialog):
    """Диалог настройки параметров сглаживания"""
    def __init__(self, window_size, poly_order, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки сглаживания")
        self.window_size = window_size
        self.poly_order = poly_order
        
        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)
        
        # Создаем спинбоксы для параметров
        self.window_size_spin = QtWidgets.QSpinBox()
        self.window_size_spin.setRange(3, 101)
        self.window_size_spin.setSingleStep(2)
        self.window_size_spin.setValue(window_size)
        layout.addRow("Размер окна (нечетное число):", self.window_size_spin)
        
        self.poly_order_spin = QtWidgets.QSpinBox()
        self.poly_order_spin.setRange(1, 10)
        self.poly_order_spin.setValue(poly_order)
        layout.addRow("Порядок полинома:", self.poly_order_spin)
        
        # Кнопки OK и Отмена
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        # Подключаем валидацию
        self.window_size_spin.valueChanged.connect(self.validate_settings)
    
    def validate_settings(self):
        """Проверяет корректность настроек"""
        # Размер окна должен быть нечетным
        if self.window_size_spin.value() % 2 == 0:
            self.window_size_spin.setValue(self.window_size_spin.value() + 1)
        
        # Порядок полинома должен быть меньше размера окна
        if self.poly_order_spin.value() >= self.window_size_spin.value():
            self.poly_order_spin.setValue(self.window_size_spin.value() - 1)
    
    def get_settings(self):
        """Возвращает выбранные настройки"""
        return self.window_size_spin.value(), self.poly_order_spin.value()


class AverageSettingsDialog(QtWidgets.QDialog):
    """Диалог настройки параметров усреднения"""
    def __init__(self, window_size, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки усреднения")
        self.window_size = window_size
        
        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)
        
        # Создаем спинбокс для размера окна
        self.window_size_spin = QtWidgets.QSpinBox()
        self.window_size_spin.setRange(2, 100)
        self.window_size_spin.setValue(window_size)
        layout.addRow("Размер окна усреднения:", self.window_size_spin)
        
        # Кнопки OK и Отмена
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def get_settings(self):
        """Возвращает выбранные настройки"""
        return self.window_size_spin.value()


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
        
        # Инициализируем данные
        self.times = []
        self.data = []
        self.smoothed_data = None
        self.averaged_data = None
        self.window_size = 5  # Размер окна для сглаживания
        self.poly_order = 2   # Порядок полинома для сглаживания
        self.avg_window = 10  # Размер окна для усреднения
        self.graph_title = ""  # Заголовок графика
        
        self.setup_ui()
    
    def setup_ui(self):
        # Создаем основной layout
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # Создаем контейнер для кнопок с фиксированной шириной
        buttons_container = QtWidgets.QWidget()
        buttons_container.setFixedWidth(600)  # Увеличиваем ширину контейнера
        
        # Создаем меню в две строки
        menu_layout = QtWidgets.QVBoxLayout()
        menu_layout.setContentsMargins(0, 0, 0, 0)  # Убираем отступы
        buttons_container.setLayout(menu_layout)
        
        # Верхняя строка - основные действия
        top_buttons = QtWidgets.QHBoxLayout()
        top_buttons.setSpacing(10)  # Отступ между кнопками
        
        # Создаем кнопки с фиксированной высотой и минимальной шириной
        button_height = 40  # Высота кнопок в пикселях
        
        # Функция для создания кнопки с правильным размером
        def create_button(text, callback):
            button = QtWidgets.QPushButton(text, self)
            button.setFixedHeight(button_height)
            button.setMinimumWidth(150)  # Минимальная ширина кнопки
            button.clicked.connect(callback)
            return button
        
        # Создаем кнопки с помощью функции
        smooth_button = create_button("Сгладить", self.smooth_data)
        top_buttons.addWidget(smooth_button)
        
        average_button = create_button("Усреднить", self.average_data)
        top_buttons.addWidget(average_button)
        
        combined_button = create_button("Сгладить и усреднить", self.combined_processing)
        top_buttons.addWidget(combined_button)
        
        restore_button = create_button("Восстановить оригинал", self.restore_original)
        top_buttons.addWidget(restore_button)
        
        # Нижняя строка - настройки и сохранение
        bottom_buttons = QtWidgets.QHBoxLayout()
        bottom_buttons.setSpacing(10)  # Отступ между кнопками
        
        smooth_settings_button = create_button("Настройки сглаживания", self.show_smooth_settings)
        bottom_buttons.addWidget(smooth_settings_button)
        
        average_settings_button = create_button("Настройки усреднения", self.show_average_settings)
        bottom_buttons.addWidget(average_settings_button)
        
        save_button = create_button("Сохранить данные", self.save_processed_data)
        bottom_buttons.addWidget(save_button)
        
        # Добавляем строки кнопок в меню
        menu_layout.addLayout(top_buttons)
        menu_layout.addLayout(bottom_buttons)
        
        # Создаем горизонтальный layout для центрирования блока кнопок
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(buttons_container)
        buttons_layout.addStretch()
        
        # Добавляем блок кнопок в основной layout
        layout.addLayout(buttons_layout)
        
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
        self.setMinimumSize(800, 400)  # Увеличиваем минимальную ширину окна
    
    def smooth_data(self):
        """Сглаживает данные с помощью фильтра Савицкого-Голея"""
        if not self.times or not self.data:
            return
            
        try:
            # Сглаживаем данные
            self.smoothed_data = savgol_filter(self.data, self.window_size, self.poly_order)
            
            # Обновляем график
            self.ax.clear()
            self.ax.plot(self.times, self.data, 'b-', alpha=0.3, label='Исходные данные')
            self.ax.plot(self.times, self.smoothed_data, 'r-', label='Сглаженные данные')
            self.ax.set_xlabel('Время, с')
            self.ax.set_ylabel('Напряжение, мВ')
            self.ax.grid(True)
            self.ax.legend()
            self.ax.set_title(self.graph_title)  # Восстанавливаем заголовок
            
            # Обновляем canvas
            self.canvas.draw()
            
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Не удалось сгладить данные: {str(e)}")
    
    def average_data(self):
        """Усредняет данные с помощью скользящего среднего"""
        if not self.times or not self.data:
            return
            
        try:
            # Усредняем данные
            self.averaged_data = np.convolve(self.data, np.ones(self.avg_window)/self.avg_window, mode='valid')
            
            # Создаем временную шкалу для усредненных данных
            # Убираем точки с краев, где усреднение неполное
            edge = self.avg_window // 2
            avg_times = self.times[edge:-edge+1]
            
            # Обновляем график
            self.ax.clear()
            self.ax.plot(self.times, self.data, 'b-', alpha=0.3, label='Исходные данные')
            self.ax.plot(avg_times, self.averaged_data, 'g-', label='Усредненные данные')
            self.ax.set_xlabel('Время, с')
            self.ax.set_ylabel('Напряжение, мВ')
            self.ax.grid(True)
            self.ax.legend()
            self.ax.set_title(self.graph_title)  # Восстанавливаем заголовок
            
            # Обновляем canvas
            self.canvas.draw()
            
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Не удалось усреднить данные: {str(e)}")
    
    def restore_original(self):
        """Восстанавливает оригинальные данные на графике"""
        if not self.times or not self.data:
            return
            
        # Очищаем обработанные данные
        self.smoothed_data = None
        self.averaged_data = None
        
        # Обновляем график
        self.ax.clear()
        self.ax.plot(self.times, self.data, 'b-')
        self.ax.set_xlabel('Время, с')
        self.ax.set_ylabel('Напряжение, мВ')
        self.ax.grid(True)
        self.ax.set_title(self.graph_title)  # Восстанавливаем заголовок
        
        # Обновляем canvas
        self.canvas.draw()
    
    def show_smooth_settings(self):
        """Показывает диалог настройки параметров сглаживания"""
        dialog = SmoothSettingsDialog(self.window_size, self.poly_order, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.window_size, self.poly_order = dialog.get_settings()
            # Если есть сглаженные данные, применяем новые настройки
            if self.smoothed_data is not None:
                self.smooth_data()
    
    def show_average_settings(self):
        """Показывает диалог настройки параметров усреднения"""
        dialog = AverageSettingsDialog(self.avg_window, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.avg_window = dialog.get_settings()
            # Если есть усредненные данные, применяем новые настройки
            if self.averaged_data is not None:
                self.average_data()
    
    def combined_processing(self):
        """Применяет сглаживание и усреднение к данным"""
        if not self.times or not self.data:
            return
            
        try:
            # Сначала сглаживаем данные
            smoothed = savgol_filter(self.data, self.window_size, self.poly_order)
            
            # Затем усредняем сглаженные данные
            edge = self.avg_window // 2
            combined_data = np.convolve(smoothed, np.ones(self.avg_window)/self.avg_window, mode='valid')
            combined_times = self.times[edge:-edge+1]
            
            # Обновляем график
            self.ax.clear()
            self.ax.plot(self.times, self.data, 'b-', alpha=0.3, label='Исходные данные')
            self.ax.plot(combined_times, combined_data, 'r-', label='Обработанные данные')
            self.ax.set_xlabel('Время, с')
            self.ax.set_ylabel('Напряжение, мВ')
            self.ax.grid(True)
            self.ax.legend()
            self.ax.set_title(self.graph_title)  # Восстанавливаем заголовок
            
            # Сохраняем обработанные данные
            self.smoothed_data = smoothed
            self.averaged_data = combined_data
            
            # Обновляем canvas
            self.canvas.draw()
            
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Не удалось обработать данные: {str(e)}")
    
    def load_data(self, filename):
        """Загружает данные из файла CSV и отображает их на графике"""
        try:
            # Загружаем данные из CSV
            self.times = []
            self.data = []
            
            with open(filename, 'r') as f:
                # Пропускаем заголовок
                header = next(f)
                
                # Читаем данные
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        try:
                            time_val = float(row[0])
                            voltage = float(row[1])
                            self.times.append(time_val)
                            self.data.append(voltage)
                        except (ValueError, IndexError):
                            pass
            
            if not self.times or not self.data:
                QtWidgets.QMessageBox.warning(self, "Ошибка", "Файл не содержит данных или имеет неверный формат")
                return False
            
            # Очищаем график
            self.ax.clear()
            
            # Строим график
            self.ax.plot(self.times, self.data, '-', linewidth=1)
            
            # Настраиваем оси
            self.ax.set_xlabel('Время, с')
            self.ax.set_ylabel('Напряжение, мВ')
            self.ax.grid(True)
            
            # Масштабируем график, чтобы видеть все данные
            self.ax.set_xlim(min(self.times), max(self.times))
            
            if len(self.data) > 1:
                min_voltage = min(self.data)
                max_voltage = max(self.data)
                padding = (max_voltage - min_voltage) * 0.1
                if padding < 10:
                    padding = 10
                self.ax.set_ylim(min_voltage - padding, max_voltage + padding)
            
            # Заголовок графика
            self.graph_title = f'Данные из файла: {os.path.basename(filename)}'
            self.ax.set_title(self.graph_title)
            
            # Обновляем информационные метки
            self.file_info_label.setText(f"Файл: {os.path.basename(filename)}")
            self.data_info_label.setText(f"Точек: {len(self.data)}")
            
            if self.times:
                duration = max(self.times)
                self.time_info_label.setText(f"Время записи: {duration:.1f} с")
            
            # Обновляем canvas
            self.canvas.draw()
            
            return True
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл: {str(e)}")
            return False

    def save_processed_data(self):
        """Сохраняет обработанные данные в файл"""
        if not self.times or not self.data:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Нет данных для сохранения")
            return
            
        # Определяем, какие данные сохранять
        data_to_save = None
        if self.smoothed_data is not None and self.averaged_data is not None:
            # Если есть и сглаженные, и усредненные данные, сохраняем комбинированные
            edge = self.avg_window // 2
            data_to_save = self.averaged_data
            times_to_save = self.times[edge:-edge+1]
        elif self.smoothed_data is not None:
            # Если есть только сглаженные данные
            data_to_save = self.smoothed_data
            times_to_save = self.times
        elif self.averaged_data is not None:
            # Если есть только усредненные данные
            data_to_save = self.averaged_data
            edge = self.avg_window // 2
            times_to_save = self.times[edge:-edge+1]
        else:
            # Если нет обработанных данных, сохраняем исходные
            data_to_save = self.data
            times_to_save = self.times
        
        try:
            # Запрашиваем имя файла для сохранения
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Сохранить обработанные данные",
                "",
                "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
            )
            
            if filename:
                # Сохраняем данные
                with open(filename, 'w') as f:
                    f.write("time,voltage\n")  # Заголовок
                    for t, v in zip(times_to_save, data_to_save):
                        f.write(f"{t},{v}\n")
                
                QtWidgets.QMessageBox.information(
                    self,
                    "Успех",
                    f"Данные успешно сохранены в файл {filename}"
                )
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось сохранить данные: {str(e)}"
            )


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
        self.file = None
        self.recording = False
        self.data = []
        self.times = []
        self.start_time = None  # время начала в миллисекундах Arduino
        self.system_start_time = None  # системное время начала записи
        self.last_update_time = 0
        self.buffered_data = []  # Буфер для данных
        self.update_interval = 100  # Интервал обновления графика в мс
        self.window_size = 5.0  # Размер окна графика в секундах
        self.backup_filename = ""
        self.received_data_count = 0  # Счетчик полученных данных
        self.saved_data_count = 0    # Счетчик сохраненных данных
        self.record_timer = None     # Таймер для автоматической остановки записи
        self.timed_recording = False # Флаг записи по времени
        self.show_current_values = True  # Флаг отображения текущих значений
        
        self.ui = uic.loadUi(resource_path("mainForm.ui"))
        self.ui.setWindowTitle("Serial Voltmeter")
        
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
        
        self.serial = QSerialPort()
        self.serial.setBaudRate(115200)

        # Настройка графика
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel('Время, с')
        self.ax.set_ylabel('Напряжение, мВ')
        self.ax.grid(True)
        
        # Добавляем график в интерфейс
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.canvas)
        self.ui.plot.setLayout(layout)

        # Таймер для обновления графика
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot_from_buffer)
        self.update_timer.start(self.update_interval)

        # Таймер для вывода статистики каждую секунду
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.show_stats)
        self.stats_timer.start(1000)  # Каждую секунду

        self.init_gui()
        self.serial.readyRead.connect(self.parse_serial)
        self.lastWindowClosed.connect(self.stop_recording)

        self.ui.show()
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
        if self.recording:
            # Вычисляем прошедшее время на основе системного времени
            elapsed_time = 0
            if self.system_start_time:
                current_time = time.time()
                elapsed_time = current_time - self.system_start_time
            
            # Если запись по времени, показываем оставшееся время
            remaining_text = ""
            if self.timed_recording and self.record_timer and self.record_timer.isActive():
                remaining_ms = self.record_timer.remainingTime()
                if remaining_ms > 0:
                    remaining_sec = remaining_ms / 1000.0
                    remaining_text = f", осталось: {remaining_sec:.1f} с"
            
            self.ui.console.appendPlainText(
                f"Статистика: получено измерений: {self.received_data_count}, "
                f"сохранено в файл: {self.saved_data_count}, "
                f"время записи: {elapsed_time:.1f} с{remaining_text}"
            )
            self.processEvents()

    def parse_serial(self):
        # Обрабатываем все доступные данные
        while self.serial.canReadLine():
            try:
                line = str(self.serial.readLine(), 'utf-8').strip()
                
                # Разбираем данные (формат: millis,voltage)
                parts = line.split(',')
                if len(parts) < 2:
                    continue
                
                try:
                    # Время в миллисекундах
                    time_ms = int(parts[0])
                    # Напряжение в милливольтах
                    voltage = float(parts[1])
                    
                    # Преобразуем время в секунды
                    time_sec = time_ms / 1000.0
                    
                    # Увеличиваем счетчик полученных данных
                    self.received_data_count += 1
                    
                    # Выводим данные в консоль (не каждый раз, чтобы не перегружать)
                    current_time = time.time()
                    if current_time - self.last_update_time > 0.5 and self.show_current_values:  
                        # Обновляем консоль каждые 0.5 секунды, если включен вывод текущих значений
                        self.ui.console.appendPlainText(f"Время: {time_sec:.2f} с, Напряжение: {voltage:.2f} мВ")
                        self.last_update_time = current_time
                        # Обрабатываем события приложения, чтобы не зависало
                        self.processEvents()
                    
                    # Если запись активна, добавляем данные
                    if self.recording:
                        # Если это первое измерение, запоминаем время начала
                        if not self.times and self.start_time is None:
                            self.start_time = time_ms
                            # Запоминаем системное время начала записи
                            if self.system_start_time is None:
                                self.system_start_time = time.time()
                        
                        # Нормализуем время (от начала записи)
                        normalized_time = (time_ms - self.start_time) / 1000.0
                        
                        # Добавляем данные в буфер (для графика)
                        self.buffered_data.append((normalized_time, voltage))
                        
                        # Записываем в файл сразу
                        if self.file:
                            self.file.write(f"{normalized_time},{voltage}\n")
                            self.file.flush()  # Сбрасываем буфер файла
                            self.saved_data_count += 1  # Увеличиваем счетчик сохраненных данных
                    
                except (ValueError, IndexError) as e:
                    self.ui.console.appendPlainText(f"Ошибка при обработке данных: {str(e)}")
                    self.processEvents()
            except Exception as e:
                self.ui.console.appendPlainText(f"Ошибка при чтении данных: {str(e)}")
                self.processEvents()

    def update_plot_from_buffer(self):
        # Если нет новых данных, не обновляем график
        if not self.buffered_data:
            return
            
        # Добавляем все буферизованные данные
        for time_val, voltage in self.buffered_data:
            self.times.append(time_val)
            self.data.append(voltage)
            
        # Очищаем буфер
        self.buffered_data = []
        
        # Обновляем график с окном заданного размера
        if self.times and self.data:
            # Находим минимальное значение времени для окна
            current_time = self.times[-1]
            min_time = max(0, current_time - self.window_size)
            
            # Фильтруем данные только для окна заданного размера
            window_times = []
            window_data = []
            
            for i in range(len(self.times)):
                if self.times[i] >= min_time:
                    window_times.append(self.times[i])
                    window_data.append(self.data[i])
            
            # Если данных нет в окне, выходим
            if not window_times:
                return
                
            # Обновляем график с фильтрованными данными
            self.ax.clear()
            self.ax.plot(window_times, window_data, 'b-')
            
            # Устанавливаем пределы графика
            self.ax.set_xlim(min_time, current_time)
            
            # Настраиваем диапазон оси Y в зависимости от выбранного режима
            if self.ui.yAxisRange.currentIndex() == 0:  # Динамически
                # Если есть хотя бы два измерения, определяем диапазон по Y
                if len(window_data) > 1:
                    min_voltage = min(window_data)
                    max_voltage = max(window_data)
                    padding = (max_voltage - min_voltage) * 0.1  # 10% отступ
                    if padding < 10:  # Минимальный отступ 10 мВ
                        padding = 10
                    self.ax.set_ylim(min_voltage - padding, max_voltage + padding)
            else:  # Фиксированный диапазон
                self.ax.set_ylim(self.ui.yAxisMin.value(), self.ui.yAxisMax.value())
            
            self.ax.set_xlabel('Время, с')
            self.ax.set_ylabel('Напряжение, мВ')
            self.ax.grid(True)
            
            # Подпись для скользящего окна с информацией о числе точек
            points_in_window = len(window_times)
            self.ax.set_title(f'Последние {self.window_size} секунд ({points_in_window} точек)')
            
            self.canvas.draw()
            
        # Обрабатываем события приложения
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
                self.ui.console.appendPlainText("ОШИБКА: Не найдены доступные COM-порты")
                self.ui.connectButton.setEnabled(True)
                return
            
            # Пробуем подключиться к каждому порту
            for port in ports:
                try:
                    self.serial.setPortName(port)
                    if self.serial.open(QIODevice.ReadOnly):
                        self.ui.console.appendPlainText(f"Подключено к {port}")
                        self.ui.startButton.setEnabled(True)
                        self.ui.connectButton.setEnabled(False)
                        self.ui.disconnectButton.setEnabled(True)
                        self.ui.comPortSelect.setEnabled(False)
                        self.ui.refreshPortsButton.setEnabled(False)
                        # Устанавливаем текущий порт в выпадающем списке
                        self.ui.comPortSelect.setCurrentText(port)
                        return
                except Exception as e:
                    self.ui.console.appendPlainText(f"Ошибка при подключении к {port}: {str(e)}")
                    self.processEvents()
            
            self.ui.console.appendPlainText("ОШИБКА: Не удалось подключиться ни к одному порту")
            self.ui.connectButton.setEnabled(True)
        else:
            # Подключаемся к выбранному порту
            try:
                self.serial.setPortName(selected_port)
                if self.serial.open(QIODevice.ReadOnly):
                    self.ui.console.appendPlainText(f"Подключено к {selected_port}")
                    self.ui.startButton.setEnabled(True)
                    self.ui.connectButton.setEnabled(False)
                    self.ui.disconnectButton.setEnabled(True)
                    self.ui.comPortSelect.setEnabled(False)
                    self.ui.refreshPortsButton.setEnabled(False)
                else:
                    self.ui.console.appendPlainText(f"Ошибка при подключении к {selected_port}")
                    self.ui.connectButton.setEnabled(True)
            except Exception as e:
                self.ui.console.appendPlainText(f"Ошибка при подключении к {selected_port}: {str(e)}")
                self.ui.connectButton.setEnabled(True)

    def disconnect_device(self):
        """Отключает устройство"""
        if self.recording:
            self.stop_recording()
        
        if self.serial.isOpen():
            self.serial.close()
            self.ui.console.appendPlainText("Устройство отключено")
            self.ui.startButton.setEnabled(False)
            self.ui.disconnectButton.setEnabled(False)
            self.ui.connectButton.setEnabled(True)
            self.ui.comPortSelect.setEnabled(True)
            self.ui.refreshPortsButton.setEnabled(True)

    def start_recording(self):
        if not self.recording:
            if not self.serial.isOpen():
                self.ui.console.appendPlainText("ОШИБКА: Сначала подключитесь к прибору")
                return
                
            self.recording = True
            self.data = []
            self.times = []
            self.buffered_data = []
            self.start_time = None
            self.system_start_time = None
            self.received_data_count = 0
            self.saved_data_count = 0
            
            # Блокируем элементы настройки времени записи, пока идет запись
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
                
                # Получаем время записи в миллисекундах
                record_length = self.ui.recordLength.value()
                time_unit = self.ui.recordLengthTimeUnits.currentText()
                
                # Преобразуем время в миллисекунды
                duration_ms = record_length * 1000  # По умолчанию в секундах
                if time_unit == "минуты":
                    duration_ms = record_length * 60 * 1000
                elif time_unit == "часы":
                    duration_ms = record_length * 60 * 60 * 1000
                
                # Создаем таймер для автоматической остановки записи
                if self.record_timer is None:
                    self.record_timer = QTimer()
                    self.record_timer.setSingleShot(True)  # Однократное срабатывание
                    self.record_timer.timeout.connect(self.stop_recording)
                
                # Запускаем таймер
                self.record_timer.start(duration_ms)
                
                # Получаем человекочитаемое время для вывода
                if time_unit == "секунды":
                    time_text = f"{record_length} секунд"
                elif time_unit == "минуты":
                    time_text = f"{record_length} минут"
                else:  # часы
                    time_text = f"{record_length} часов"
                
                self.ui.console.appendPlainText(f"Начата запись на {time_text}")
            
            # Генерируем имя файла на основе даты и времени
            now = datetime.datetime.now()
            self.backup_filename = f"measurements{now.strftime('%Y%m%d%H%M%S')}.csv"
            
            # Открываем файл для записи
            try:
                self.file = open(self.backup_filename, "w")
                self.file.write("time,voltage\n")
                self.file.flush()
                self.ui.console.appendPlainText(f"Файл создан и готов к записи: {self.backup_filename}")
            except Exception as e:
                self.ui.console.appendPlainText(f"Ошибка при создании файла: {str(e)}")
                self.recording = False
                return
            
            self.ui.startButton.setEnabled(False)
            self.ui.stopButton.setEnabled(True)
            self.ui.console.appendPlainText(f"Начало записи данных в файл {self.backup_filename}")
            self.processEvents()  # Обрабатываем события, чтобы интерфейс обновился

    def stop_recording(self):
        if self.recording:
            self.recording = False
            
            # Разблокируем элементы настройки времени записи
            if hasattr(self.ui, 'recordLength'):
                self.ui.recordLength.setEnabled(True)
            if hasattr(self.ui, 'recordLengthTimeUnits'):
                self.ui.recordLengthTimeUnits.setEnabled(True)
            if hasattr(self.ui, 'timedRecordCheckBox'):
                self.ui.timedRecordCheckBox.setEnabled(True)
                
                # После разблокировки применяем правило блокировки в зависимости от состояния чекбокса
                is_checked = self.ui.timedRecordCheckBox.isChecked()
                if hasattr(self.ui, 'recordLength'):
                    self.ui.recordLength.setEnabled(not is_checked)
                if hasattr(self.ui, 'recordLengthTimeUnits'):
                    self.ui.recordLengthTimeUnits.setEnabled(not is_checked)
            
            # Останавливаем таймер записи, если он активен
            if self.record_timer and self.record_timer.isActive():
                self.record_timer.stop()
            
            # Выводим информацию о причине остановки
            if self.timed_recording:
                self.ui.console.appendPlainText("Запись автоматически остановлена по истечении заданного времени")
            
            if self.file:
                try:
                    self.file.close()
                    
                    # Вычисляем реальное время записи
                    elapsed_time = 0
                    if self.system_start_time:
                        elapsed_time = time.time() - self.system_start_time
                    
                    self.ui.console.appendPlainText(
                        f"Данные сохранены в файл {self.backup_filename} "
                        f"(всего записано {self.saved_data_count} измерений за {elapsed_time:.1f} с)"
                    )
                    
                    # Предлагаем пользователю сохранить файл под другим именем
                    if os.path.exists(self.backup_filename):
                        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                            self.ui,
                            "Сохранить файл как",
                            "",
                            "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
                        )
                        if filename:
                            try:
                                shutil.copy2(self.backup_filename, filename)
                                self.ui.console.appendPlainText(f"Файл также сохранен как {filename}")
                                
                                # Предлагаем открыть файл для просмотра
                                reply = QtWidgets.QMessageBox.question(
                                    self.ui, 
                                    "Просмотр данных",
                                    "Открыть файл для просмотра?",
                                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                    QtWidgets.QMessageBox.Yes
                                )
                                
                                if reply == QtWidgets.QMessageBox.Yes:
                                    # Создаем окно просмотра файла
                                    viewer = FileViewerWindow(self.ui)
                                    # Загружаем данные
                                    if viewer.load_data(filename):
                                        # Показываем окно, если данные успешно загружены
                                        viewer.exec_()
                                
                            except Exception as e:
                                self.ui.console.appendPlainText(f"Ошибка при сохранении файла: {str(e)}")
                                
                except Exception as e:
                    self.ui.console.appendPlainText(f"Ошибка при закрытии файла: {str(e)}")
            
            self.ui.startButton.setEnabled(True)
            self.ui.stopButton.setEnabled(False)
            self.ui.console.appendPlainText("Запись остановлена")
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

    def on_window_size_changed(self, value):
        """Обработчик изменения размера окна графика"""
        self.window_size = value
        self.ui.console.appendPlainText(f"Размер окна графика изменен на {value} секунд")
        self.update_plot_from_buffer()  # Обновляем график с новым размером окна

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
