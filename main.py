import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QTableWidget,
                             QTableWidgetItem, QTextEdit,
                             QMessageBox, QDateEdit, QComboBox, QProgressDialog,
                             QHeaderView)
from PyQt6.QtCore import QDate, Qt, QThread, pyqtSignal
from travel_functions import get_schedule, get_weather, save_to_pdf_and_upload


class LoadDataThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, from_city, to_city, date):
        super().__init__()
        self.from_city = from_city
        self.to_city = to_city
        self.date = date

    def run(self):
        try:
            schedule = get_schedule(self.from_city, self.to_city, self.date)
            weather = get_weather(self.to_city, self.date)
            result = {
                'schedule': schedule,
                'weather': weather,
                'from_city': self.from_city,
                'to_city': self.to_city,
                'date': self.date
            }
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class SaveToDiskThread(QThread):
    finished = pyqtSignal(bool, str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, from_city, to_city, date, schedule, weather, filename):
        super().__init__()
        self.from_city = from_city
        self.to_city = to_city
        self.date = date
        self.schedule = schedule
        self.weather = weather
        self.filename = filename
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            self.progress.emit("Создание PDF файла...")

            if self._is_cancelled:
                self.finished.emit(False, self.filename)
                return

            success = save_to_pdf_and_upload(
                self.from_city,
                self.to_city,
                self.date,
                self.schedule,
                self.weather,
                self.filename
            )

            if self._is_cancelled:
                self.finished.emit(False, self.filename)
                return

            self.progress.emit("Загрузка завершена!")
            self.finished.emit(success, self.filename)

        except Exception as e:
            self.error.emit(str(e))


class TravelApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Помощник путешественника")
        self.setGeometry(100, 100, 1200, 700)

        self.cities = [
            "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
            "Казань", "Нижний Новгород", "Челябинск", "Самара",
            "Омск", "Ростов-на-Дону", "Уфа", "Красноярск"
        ]

        self.current_data = None
        self.save_thread = None
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Откуда:"))
        self.from_combo = QComboBox()
        self.from_combo.addItems(self.cities)
        self.from_combo.setEditable(True)
        input_layout.addWidget(self.from_combo)

        input_layout.addWidget(QLabel("Куда:"))
        self.to_combo = QComboBox()
        self.to_combo.addItems(self.cities)
        self.to_combo.setEditable(True)
        input_layout.addWidget(self.to_combo)

        input_layout.addWidget(QLabel("Дата:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate().addDays(7))
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        input_layout.addWidget(self.date_edit)

        layout.addLayout(input_layout)

        button_layout = QHBoxLayout()
        self.show_btn = QPushButton("Показать")
        self.show_btn.clicked.connect(self.show_info)
        button_layout.addWidget(self.show_btn)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_info)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)

        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.clicked.connect(self.clear_info)
        button_layout.addWidget(self.clear_btn)

        layout.addLayout(button_layout)

        layout.addWidget(QLabel("Расписание:"))
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Вид транспорта", "Номер рейса", "Отправление", "Прибытие", "Время в пути"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        layout.addWidget(QLabel("Прогноз погоды:"))
        self.weather_text = QTextEdit()
        self.weather_text.setReadOnly(True)
        self.weather_text.setMaximumHeight(150)
        layout.addWidget(self.weather_text)

        self.statusBar().showMessage("Готов")

    def show_info(self):
        from_city = self.from_combo.currentText().strip()
        to_city = self.to_combo.currentText().strip()
        date = self.date_edit.date().toString("yyyy-MM-dd")

        if not from_city or not to_city:
            QMessageBox.warning(self, "Ошибка", "Выберите города")
            return

        if from_city == to_city:
            QMessageBox.warning(self, "Ошибка", "Города должны различаться")
            return

        self.show_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

        self.progress = QProgressDialog("Загрузка данных...", None, 0, 0, self)
        self.progress.setWindowTitle("Пожалуйста, подождите")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.show()

        QApplication.processEvents()

        self.load_thread = LoadDataThread(from_city, to_city, date)
        self.load_thread.finished.connect(self.on_data_loaded)
        self.load_thread.error.connect(self.on_load_error)
        self.load_thread.start()

    def on_data_loaded(self, data):
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()

        self.current_data = data

        if data['schedule']:
            self.table.setRowCount(len(data['schedule']))
            for i, trip in enumerate(data['schedule']):
                self.table.setItem(i, 0, QTableWidgetItem(trip.get('transport_type', '')))
                self.table.setItem(i, 1, QTableWidgetItem(trip.get('number', '')))
                self.table.setItem(i, 2, QTableWidgetItem(trip.get('departure_time', '')))
                self.table.setItem(i, 3, QTableWidgetItem(trip.get('arrival_time', '')))
                self.table.setItem(i, 4, QTableWidgetItem(trip.get('duration', '')))

        self.weather_text.setText(data['weather'])
        self.save_btn.setEnabled(True)
        self.show_btn.setEnabled(True)
        self.statusBar().showMessage(f"Загружено: {len(data['schedule']) if data['schedule'] else 0} рейсов")

    def on_load_error(self, error_msg):
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()
        self.show_btn.setEnabled(True)
        QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные:\n{error_msg}")

    def save_info(self):
        if not self.current_data:
            QMessageBox.warning(self, "Ошибка", "Нет данных для сохранения")
            return

        from_clean = self.current_data['from_city'].replace(' ', '_').replace('-', '_')
        to_clean = self.current_data['to_city'].replace(' ', '_').replace('-', '_')
        filename = f"travel_{from_clean}_{to_clean}_{self.current_data['date']}.pdf"

        reply = QMessageBox.question(
            self,
            "Сохранение на Яндекс.Диск",
            f"Файл будет сохранен на Яндекс.Диск:\n\n"
            f"Папка: /travel_app/\n"
            f"Имя: {filename}\n\n"
            f"Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.save_btn.setEnabled(False)
        self.show_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

        self.progress = QProgressDialog("Подготовка к сохранению...", "Отмена", 0, 0, self)
        self.progress.setWindowTitle("Сохранение на Яндекс.Диск")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.setValue(0)
        self.progress.show()

        QApplication.processEvents()

        self.save_thread = SaveToDiskThread(
            self.current_data['from_city'],
            self.current_data['to_city'],
            self.current_data['date'],
            self.current_data['schedule'],
            self.current_data['weather'],
            filename
        )

        self.save_thread.progress.connect(self.on_save_progress)
        self.save_thread.finished.connect(self.on_save_finished)
        self.save_thread.error.connect(self.on_save_error)

        self.progress.canceled.connect(self.cancel_save)

        self.save_thread.start()

    def on_save_progress(self, message):
        if hasattr(self, 'progress') and self.progress:
            self.progress.setLabelText(message)
            QApplication.processEvents()

    def on_save_finished(self, success, filename):
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()

        self.save_btn.setEnabled(True)
        self.show_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

        self.save_thread = None

        if success:
            QMessageBox.information(
                self,
                "Успех",
                f"Информация успешно сохранена на Яндекс.Диск!\n\n"
                f"Имя файла: {filename}\n"
                f"Путь на диске: /travel_app/{filename}\n\n"
                f"Вы можете найти файл в приложении Яндекс.Диск"
            )
            self.statusBar().showMessage(f"Файл загружен на Яндекс.Диск: {filename}")
        else:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не удалось сохранить файл на Яндекс.Диск.\n"
                "Проверьте подключение к интернету и настройки токена."
            )

    def on_save_error(self, error_msg):
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()

        self.save_btn.setEnabled(True)
        self.show_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

        self.save_thread = None

        QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении: {error_msg}")

    def cancel_save(self):
        if self.save_thread and self.save_thread.isRunning():
            self.save_thread.cancel()
            self.save_thread.wait(1000)
            self.progress.setLabelText("Отмена операции...")
            QMessageBox.information(self, "Отмена", "Сохранение отменено пользователем")
            self.save_btn.setEnabled(True)
            self.show_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)

    def clear_info(self):
        self.table.setRowCount(0)
        self.weather_text.clear()
        self.current_data = None
        self.save_btn.setEnabled(False)
        self.statusBar().showMessage("Очищено")


def main():
    app = QApplication(sys.argv)
    window = TravelApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
