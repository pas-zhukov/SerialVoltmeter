"""
Модуль для виджетов графиков
Поддерживает как matplotlib (медленный, но красивый), 
так и pyqtgraph (быстрый, для real-time)
"""
import logging
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from typing import List, Tuple

from constants import *


logger = logging.getLogger(__name__)


class PyQtGraphWidget:
    """
    Быстрый виджет графика на основе pyqtgraph
    Идеально подходит для real-time визуализации
    """
    
    def __init__(self, parent_widget: QtWidgets.QWidget):
        """
        Args:
            parent_widget: Родительский виджет Qt для размещения графика
        """
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')  # Белый фон
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'Напряжение', units='мВ')
        self.plot_widget.setLabel('bottom', 'Время', units='с')
        
        # Настройка осей
        self.plot_widget.setAxisItems({
            'bottom': pg.AxisItem(orientation='bottom'),
            'left': pg.AxisItem(orientation='left')
        })
        
        # Кривая для данных
        pen = pg.mkPen(color=(0, 0, 255), width=1)
        self.curve = self.plot_widget.plot([], [], pen=pen)
        
        # Создаем layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.plot_widget)
        parent_widget.setLayout(layout)
        
        logger.info("PyQtGraph widget initialized")
    
    def update_plot(self, times: List[float], voltages: List[float],
                   window_size: float, y_mode: int, y_min: float = 0, y_max: float = 1000):
        """
        Обновить график новыми данными
        
        Args:
            times: Массив времен (секунды)
            voltages: Массив напряжений (милливольты)
            window_size: Размер окна по времени (секунды)
            y_mode: Режим оси Y (0=динамический, 1=фиксированный)
            y_min: Минимум оси Y (для фиксированного режима)
            y_max: Максимум оси Y (для фиксированного режима)
        """
        if not times or not voltages:
            return
        
        # Обновляем данные кривой (очень быстро!)
        self.curve.setData(times, voltages)
        
        # Устанавливаем пределы по X
        current_time = times[-1]
        min_time = max(0, current_time - window_size)
        self.plot_widget.setXRange(min_time, current_time, padding=0)
        
        # Настраиваем диапазон Y
        if y_mode == Y_AXIS_MODE_DYNAMIC:
            if len(voltages) > 1:
                min_v = min(voltages)
                max_v = max(voltages)
                padding = (max_v - min_v) * DEFAULT_Y_AXIS_PADDING
                if padding < MIN_Y_AXIS_PADDING_MV:
                    padding = MIN_Y_AXIS_PADDING_MV
                self.plot_widget.setYRange(min_v - padding, max_v + padding, padding=0)
        else:
            self.plot_widget.setYRange(y_min, y_max, padding=0)
        
        # Обновляем заголовок
        title = f'Последние {window_size} с ({len(times)} точек)'
        self.plot_widget.setTitle(title)
    
    def clear(self):
        """Очистить график"""
        self.curve.setData([], [])


class MatplotlibWidget:
    """
    Виджет графика на основе matplotlib
    Медленнее, но с более красивым рендерингом
    """
    
    def __init__(self, parent_widget: QtWidgets.QWidget):
        """
        Args:
            parent_widget: Родительский виджет Qt для размещения графика
        """
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel('Время, с')
        self.ax.set_ylabel('Напряжение, мВ')
        self.ax.grid(True, alpha=0.3)
        
        # Создаем layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.canvas)
        parent_widget.setLayout(layout)
        
        logger.info("Matplotlib widget initialized")
    
    def update_plot(self, times: List[float], voltages: List[float],
                   window_size: float, y_mode: int, y_min: float = 0, y_max: float = 1000):
        """
        Обновить график новыми данными
        
        Args:
            times: Массив времен (секунды)
            voltages: Массив напряжений (милливольты)
            window_size: Размер окна по времени (секунды)
            y_mode: Режим оси Y (0=динамический, 1=фиксированный)
            y_min: Минимум оси Y (для фиксированного режима)
            y_max: Максимум оси Y (для фиксированного режима)
        """
        if not times or not voltages:
            return
        
        # Очищаем и перерисовываем (медленно!)
        self.ax.clear()
        self.ax.plot(times, voltages, 'b-', linewidth=1)
        
        # Устанавливаем пределы по X
        current_time = times[-1]
        min_time = max(0, current_time - window_size)
        self.ax.set_xlim(min_time, current_time)
        
        # Настраиваем диапазон Y
        if y_mode == Y_AXIS_MODE_DYNAMIC:
            if len(voltages) > 1:
                min_v = min(voltages)
                max_v = max(voltages)
                padding = (max_v - min_v) * DEFAULT_Y_AXIS_PADDING
                if padding < MIN_Y_AXIS_PADDING_MV:
                    padding = MIN_Y_AXIS_PADDING_MV
                self.ax.set_ylim(min_v - padding, max_v + padding)
        else:
            self.ax.set_ylim(y_min, y_max)
        
        # Настройка осей и сетки
        self.ax.set_xlabel('Время, с')
        self.ax.set_ylabel('Напряжение, мВ')
        self.ax.grid(True, alpha=0.3)
        
        # Заголовок
        self.ax.set_title(f'Последние {window_size} с ({len(times)} точек)')
        
        # Обновляем canvas
        self.canvas.draw()
    
    def clear(self):
        """Очистить график"""
        self.ax.clear()
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()


class PlotManager:
    """
    Менеджер графиков, позволяющий переключаться между 
    matplotlib и pyqtgraph
    """
    
    def __init__(self, parent_widget: QtWidgets.QWidget, use_pyqtgraph: bool = True):
        """
        Args:
            parent_widget: Родительский виджет
            use_pyqtgraph: Использовать pyqtgraph (True) или matplotlib (False)
        """
        self.use_pyqtgraph = use_pyqtgraph
        
        if use_pyqtgraph:
            self.plot = PyQtGraphWidget(parent_widget)
            logger.info("Using pyqtgraph for plotting (fast mode)")
        else:
            self.plot = MatplotlibWidget(parent_widget)
            logger.info("Using matplotlib for plotting (quality mode)")
    
    def update_plot(self, times: List[float], voltages: List[float],
                   window_size: float, y_mode: int, y_min: float = 0, y_max: float = 1000):
        """Обновить график"""
        self.plot.update_plot(times, voltages, window_size, y_mode, y_min, y_max)
    
    def clear(self):
        """Очистить график"""
        self.plot.clear()
