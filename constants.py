"""
Константы приложения
"""

# Serial порт
SERIAL_BAUD_RATE = 115200
SERIAL_TIMEOUT_MS = 100
DEVICE_VERIFICATION_TIMEOUT_S = 5  # Таймаут проверки Arduino при подключении

# Интервалы обновления (в миллисекундах)
PLOT_UPDATE_INTERVAL_MS = 100  # Обновление графика
STATS_UPDATE_INTERVAL_MS = 1000  # Обновление статистики
CONSOLE_UPDATE_INTERVAL_S = 0.5  # Обновление консоли

# График
DEFAULT_WINDOW_SIZE_S = 5.0  # Размер окна графика по умолчанию (секунды)
DEFAULT_Y_AXIS_PADDING = 0.1  # Отступ по оси Y (10%)
MIN_Y_AXIS_PADDING_MV = 10.0  # Минимальный отступ по оси Y (милливольты)

# Данные
MAX_DATA_BUFFER_SIZE = 100000  # Максимальное количество точек в буфере
FILE_FLUSH_INTERVAL = 100  # Интервал сброса буфера файла (количество измерений)

# Arduino
ARDUINO_SAMPLING_INTERVAL_MS = 1  # Интервал отправки данных с Arduino (синхронизировано с АЦП)
ARDUINO_ADC_SAMPLE_RATE = 860  # Частота дискретизации АЦП (SPS)

# Режимы оси Y
Y_AXIS_MODE_DYNAMIC = 0
Y_AXIS_MODE_FIXED = 1

# Единицы времени для записи
TIME_UNIT_SECONDS = "секунды"
TIME_UNIT_MINUTES = "минуты"
TIME_UNIT_HOURS = "часы"

TIME_UNITS_MULTIPLIERS = {
    TIME_UNIT_SECONDS: 1,
    TIME_UNIT_MINUTES: 60,
    TIME_UNIT_HOURS: 3600
}

# Диапазоны АЦП ADS1115 (в милливольтах)
ADS1115_RANGES = [256, 512, 1024, 2048, 4096, 6144]

# Частоты дискретизации АЦП ADS1115 (в SPS)
ADS1115_SAMPLE_RATES = [8, 16, 32, 64, 128, 250, 475, 860]

# Логирование
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
