import typing

from PyQt5 import QtWidgets, uic
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
from PyQt5.QtCore import QIODevice

from models import VoltageRange, TimeUnits


class SerialVoltmeterApp(QtWidgets.QApplication):
    def __init__(self, argv: typing.List[str]):
        super().__init__(argv)
        self.ui = uic.loadUi("mainForm.ui")
        self.ui.setWindowTitle("Serial Voltmeter")
        self.serial = QSerialPort()
        self.serial.setBaudRate(115200)

        self.init_gui()
        self.serial.readyRead.connect(self.parse_serial)

        self.ui.show()
        self.exec()

        self.connect_device()

    def init_gui(self):
        self.ui.recordRange.addItems(VoltageRange.RANGES_STR)
        self.ui.samplingTimeUnits.addItems(TimeUnits.MAPPING.value.values())
        self.ui.recordLengthTimeUnits.addItems(TimeUnits.MAPPING.value.values())
        self.ui.recordSampling.addItem(str(VoltageRange(6144).sampling))

    def parse_serial(self):
        if not self.serial.canReadLine():
            return
        data = str(self.serial.readLine())[2:-5].strip().split(",")
        if data[0] == 5:
            with open("temp_data.txt", "a+") as file:
                file.write(f"{data[1]},{data[2]},{data[3]}\n")
        if data[0] == 1:
            if data[1] == 1 and data[2] == 1:
                dlg = QtWidgets.QDialog()
                dlg.setWindowTitle("Прибор успешно подключен!")
                dlg.exec()

    def connect_device(self):
        # автопоиск порта здесь будет
        self.serial.setPortName("COM3")
        self.serial.open(QIODevice.ReadWrite)
        self.send_package([0, 1, 1])

    def send_package(self, data: list[int]):
        txs = ','.join(map(str, data)) + '\n'
        self.serial.write(txs.encode())

    def start_recording(self):
        self.send_package([4, 6144, 10, 60*1000])


if __name__ == "__main__":
    app = SerialVoltmeterApp([])
