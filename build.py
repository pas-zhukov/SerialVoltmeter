import os
import subprocess
import sys
import platform
import re


def get_version():
    """Получает версию из pyproject.toml"""
    try:
        with open("pyproject.toml", "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r'version\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"ОШИБКА при чтении версии: {e}")
    return "0.0.0"


def get_platform_suffix():
    """Возвращает суффикс для текущей платформы"""
    system = platform.system().lower()
    if system == "windows":
        return ".exe"
    elif system == "darwin":  # macOS
        return ".app"
    else:  # Linux и другие
        return ""


def build_exe():
    """Сборка исполняемого файла с помощью PyInstaller"""
    print("Начинаем сборку исполняемого файла...")
    
    # Получаем версию и суффикс платформы
    version = get_version()
    platform_suffix = get_platform_suffix()
    
    # Проверяем наличие необходимых файлов
    required_files = ["app.py", "mainForm.ui", "comSelector.ui", "models.py"]
    for file in required_files:
        if not os.path.exists(file):
            print(f"ОШИБКА: Файл {file} не найден!")
            return False
    
    # Создаем директорию для сборки, если она не существует
    if not os.path.exists("build"):
        os.makedirs("build")
    
    # Формируем имя выходного файла с версией
    output_name = f"SerialVoltmeter-v{version}{platform_suffix}"
    
    # Формируем команду для PyInstaller
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name", output_name,
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
