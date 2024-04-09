from enum import Enum


class VoltageRange:
    BITS_COUNT = 16
    RANGES = [
        6144,
        4096,
        2048,
        1024,
        512,
        256
    ]
    RANGES_STR = [
        "6144",
        "4096",
        "2048",
        "1024",
        "512",
        "256"
    ]

    def __init__(self, range_value):
        self.range_value = range_value
        self.sampling = round(2 * range_value / (2**self.BITS_COUNT), 4)  # mV


class TimeUnits(Enum):
    MILLIS = 1,
    SECONDS = 1000,
    MINUTES = 60 * 1000,
    HOURS = 60 * 60 * 1000
    MAPPING = {
        "MILLIS": "мс",
        "SECONDS": "с",
        "MINUTES": "мин",
        "HOURS": "ч"
    }

    def __str__(self):
        return self.MAPPING.value[self.name]
