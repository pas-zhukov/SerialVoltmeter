import os
import subprocess
import sys


def build_exe():
    """Сборка исполняемого файла с помощью PyInstaller"""
    print("Начинаем сборку исполняемого файла...")
    
    # Проверяем наличие необходимых файлов
    required_files = ["app.py", "mainForm.ui", "comSelector.ui", "models.py"]
    for file in required_files:
        if not os.path.exists(file):
            print(f"ОШИБКА: Файл {file} не найден!")
            return False
    
    # Создаем директорию для сборки, если она не существует
    if not os.path.exists("build"):
        os.makedirs("build")
    
    # Формируем команду для PyInstaller
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name", "SerialVoltmeter",
        "--add-data", f"mainForm.ui{os.pathsep}.",
        "--add-data", f"comSelector.ui{os.pathsep}.",
        "--add-data", f"models.py{os.pathsep}.",
        "app.py"
    ]
    
    # Запускаем PyInstaller
    try:
        subprocess.run(cmd, check=True)
        print("Сборка успешно завершена!")
        print(f"Исполняемый файл находится в директории: {os.path.abspath('dist')}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ОШИБКА при сборке: {e}")
        return False
    except Exception as e:
        print(f"Неизвестная ошибка: {e}")
        return False


if __name__ == "__main__":
    build_exe()
