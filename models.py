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

    def __init__(self, range_value):
        self.range_value = range_value
        self.sampling = round(range_value / (2**self.BITS_COUNT), 4)  # mV

