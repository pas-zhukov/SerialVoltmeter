import typing

import matplotlib
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QIODevice
from PyQt5.QtSerialPort import QSerialPort

matplotlib.use('Qt5Agg')

from models import VoltageRange, TimeUnits


class SerialVoltmeterApp(QtWidgets.QApplication):
    def __init__(self, argv: typing.List[str]):
        super().__init__(argv)
        self.file = open("temp_data.txt", "a+")
        self.ui = uic.loadUi("mainForm.ui")
        self.ui.setWindowTitle("Serial Voltmeter")
        self.serial = QSerialPort()
        self.serial.setBaudRate(115200)

        self.init_gui()
        self.serial.readyRead.connect(self.parse_serial)
        self.lastWindowClosed.connect(self.file.close)

        self.ui.show()
        self.exec()

    def init_gui(self):
        self.ui.connection.triggered.connect(self.connect_device)
        self.ui.exit.triggered.connect(self.exit)
        self.ui.startButton.clicked.connect(self.start_recording)
        self.ui.recordRange.addItems(VoltageRange.RANGES_STR)
        self.ui.samplingTimeUnits.addItems(TimeUnits.MAPPING.value.values())
        self.ui.recordLengthTimeUnits.addItems(TimeUnits.MAPPING.value.values())
        self.ui.recordRange.currentTextChanged.connect(self.refresh_gui)
        self.refresh_gui()

    def refresh_gui(self):
        self.ui.recordSampling.clear()
        self.ui.recordSampling.addItem(
            str(VoltageRange(VoltageRange.RANGES[self.ui.recordRange.currentIndex()]).sampling))

    def parse_serial(self):
        if not self.serial.canReadLine():
            return
        data = str(self.serial.readLine())[2:-5].strip().split(",")
        self.ui.console.appendPlainText(str(data))
        if data[0] == '5':
            self.file.write(data.__str__() + "\n")
        if data[0] == '0':
            if data[1] == '1':
                self.ui.console.appendPlainText("Прибор успешно подключен!")
            elif data[1] == '0':
                self.ui.console.appendPlainText("ОШИБКА: Не удалось инициализировать плату АЦП")

    def connect_device(self):
        # автопоиск порта здесь будет
        self.serial.setPortName("COM3")
        self.serial.open(QIODevice.ReadWrite)
        self.send_package([0, 0])

    def send_package(self, data: list[int]):
        txs = ','.join(map(str, data)) + '\n'
        self.serial.write(txs.encode())

    def start_recording(self):
        self.send_package([4, 6144, 10, 1800])


if __name__ == "__main__":
    app = SerialVoltmeterApp([])
