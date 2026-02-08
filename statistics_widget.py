"""
Виджет для отображения статистики в реальном времени
"""
from PyQt5 import QtWidgets, QtCore
from typing import Dict


class StatisticsWidget(QtWidgets.QWidget):
    """
    Виджет для отображения статистики измерений
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Настройка интерфейса виджета"""
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        
        # Заголовок
        title = QtWidgets.QLabel("📊 Статистика в реальном времени")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title, 0, 0, 1, 2)
        
        # Метки для статистики
        self.labels = {}
        stats_items = [
            ('count', 'Измерений:', '0'),
            ('min', 'Минимум:', '0.00 мВ'),
            ('max', 'Максимум:', '0.00 мВ'),
            ('mean', 'Среднее:', '0.00 мВ'),
            ('std', 'Ст. отклонение:', '0.00 мВ'),
            ('rms', 'RMS:', '0.00 мВ'),
        ]
        
        row = 1
        for key, label_text, default_value in stats_items:
            label = QtWidgets.QLabel(label_text)
            value_label = QtWidgets.QLabel(default_value)
            value_label.setStyleSheet("font-weight: bold;")
            value_label.setAlignment(QtCore.Qt.AlignRight)
            
            layout.addWidget(label, row, 0)
            layout.addWidget(value_label, row, 1)
            
            self.labels[key] = value_label
            row += 1
        
        # Добавляем разделитель
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line, row, 0, 1, 2)
        row += 1
        
        # Метки для событий
        peaks_label = QtWidgets.QLabel("🔺 Пики обнаружено:")
        self.peaks_value = QtWidgets.QLabel("0")
        self.peaks_value.setStyleSheet("font-weight: bold; color: #FF6B6B;")
        self.peaks_value.setAlignment(QtCore.Qt.AlignRight)
        
        triggers_label = QtWidgets.QLabel("⚡ Триггеры сработали:")
        self.triggers_value = QtWidgets.QLabel("0")
        self.triggers_value.setStyleSheet("font-weight: bold; color: #4ECDC4;")
        self.triggers_value.setAlignment(QtCore.Qt.AlignRight)
        
        layout.addWidget(peaks_label, row, 0)
        layout.addWidget(self.peaks_value, row, 1)
        row += 1
        
        layout.addWidget(triggers_label, row, 0)
        layout.addWidget(self.triggers_value, row, 1)
        row += 1
        
        # Кнопка сброса статистики
        self.reset_button = QtWidgets.QPushButton("Сбросить статистику")
        layout.addWidget(self.reset_button, row, 0, 1, 2)
        
        # Растягиваем последнюю строку
        layout.setRowStretch(row + 1, 1)
    
    def update_statistics(self, stats: Dict[str, float]):
        """
        Обновить отображаемую статистику
        
        Args:
            stats: Словарь со статистическими показателями
        """
        if 'count' in stats:
            self.labels['count'].setText(str(int(stats['count'])))
        
        if 'min' in stats:
            self.labels['min'].setText(f"{stats['min']:.2f} мВ")
        
        if 'max' in stats:
            self.labels['max'].setText(f"{stats['max']:.2f} мВ")
        
        if 'mean' in stats:
            self.labels['mean'].setText(f"{stats['mean']:.2f} мВ")
        
        if 'std' in stats:
            self.labels['std'].setText(f"{stats['std']:.2f} мВ")
        
        if 'rms' in stats:
            self.labels['rms'].setText(f"{stats['rms']:.2f} мВ")
    
    def update_events(self, peaks_count: int, triggers_count: int):
        """
        Обновить счетчики событий
        
        Args:
            peaks_count: Количество обнаруженных пиков
            triggers_count: Количество сработавших триггеров
        """
        self.peaks_value.setText(str(peaks_count))
        self.triggers_value.setText(str(triggers_count))
    
    def reset(self):
        """Сбросить все значения"""
        self.labels['count'].setText('0')
        self.labels['min'].setText('0.00 мВ')
        self.labels['max'].setText('0.00 мВ')
        self.labels['mean'].setText('0.00 мВ')
        self.labels['std'].setText('0.00 мВ')
        self.labels['rms'].setText('0.00 мВ')
        self.peaks_value.setText('0')
        self.triggers_value.setText('0')
