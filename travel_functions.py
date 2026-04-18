import requests
from datetime import datetime
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


WEATHER_API_KEY = "..."
RASP_API_KEY = "..."
YANDEX_TOKEN = "..."


def get_city_code(city_name):
    cities_db = {
        "москва": "c213",
        "санкт-петербург": "c2",
        "новосибирск": "c54",
        "екатеринбург": "c48",
        "казань": "c38",
        "нижний новгород": "c47",
        "челябинск": "c56",
        "самара": "c51",
        "омск": "c52",
        "ростов-на-дону": "c39",
        "уфа": "c172",
        "красноярск": "c62",
        "пермь": "c50",
        "воронеж": "c44",
        "волгоград": "c55"
    }
    city_lower = city_name.lower().strip()
    return cities_db.get(city_lower)


def get_city_coordinates(city_name):
    coordinates_db = {
        "москва": (55.7558, 37.6173),
        "санкт-петербург": (59.9343, 30.3351),
        "новосибирск": (55.0084, 82.9357),
        "екатеринбург": (56.8389, 60.6057),
        "казань": (55.7887, 49.1221),
        "нижний новгород": (56.2965, 43.9361),
        "челябинск": (55.1644, 61.4368),
        "самара": (53.1959, 50.1002),
        "омск": (54.9885, 73.3242),
        "ростов-на-дону": (47.2357, 39.7015)
    }
    city_lower = city_name.lower().strip()
    return coordinates_db.get(city_lower)


def calculate_duration(departure_time, arrival_time):
    try:
        dep_h, dep_m = map(int, departure_time.split(':'))
        arr_h, arr_m = map(int, arrival_time.split(':'))
        dep_minutes = dep_h * 60 + dep_m
        arr_minutes = arr_h * 60 + arr_m
        if arr_minutes < dep_minutes:
            arr_minutes += 24 * 60
        duration_minutes = arr_minutes - dep_minutes
        hours = duration_minutes // 60
        minutes = duration_minutes % 60
        return f"{hours}ч {minutes}мин"
    except:
        return "Неизвестно"


def format_time(time_str):
    try:
        return time_str.split('T')[1].split('+')[0][:5]
    except:
        return "Неизвестно"


def get_schedule(from_city, to_city, date):
    from_code = get_city_code(from_city)
    to_code = get_city_code(to_city)

    if RASP_API_KEY == "..." or not from_code or not to_code:
        print("Не хватает данных")
        return None

    base_url = "https://api.rasp.yandex.net/v3.0/search/"
    schedule = []
    transport_types = ['plane', 'train', 'bus', 'suburban']

    for transport in transport_types:
        params = {
            "apikey": RASP_API_KEY,
            "format": "json",
            "from": from_code,
            "to": to_code,
            "lang": "ru_RU",
            "date": date,
            "transport_types": transport,
            "limit": 20
        }

        try:
            response = requests.get(base_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'segments' in data and data['segments']:
                    for segment in data['segments']:
                        departure = segment.get('departure', '')
                        arrival = segment.get('arrival', '')
                        departure_time = format_time(departure)
                        arrival_time = format_time(arrival)
                        thread = segment.get('thread', {})
                        number = thread.get('number', 'Неизвестно')
                        duration = calculate_duration(departure_time, arrival_time)
                        transport_type_name = {
                            'plane': 'Самолет',
                            'train': 'Поезд',
                            'bus': 'Автобус',
                            'suburban': 'Электричка'
                        }.get(transport, transport)
                        schedule.append({
                            'transport_type': transport_type_name,
                            'number': number,
                            'departure_time': departure_time,
                            'arrival_time': arrival_time,
                            'duration': duration
                        })
        except Exception as e:
            print(f"Ошибка при запросе {transport}: {e}")
            continue

    if not schedule:
        return None

    print("API RASP", "OK")
    return schedule


def get_weather(city, date):
    coordinates = get_city_coordinates(city)

    if WEATHER_API_KEY == "..." or not coordinates:
        print("Не хватает данных")
        return "DATA ERROR"

    lat, lon = coordinates
    headers = {"X-Yandex-Weather-Key": WEATHER_API_KEY}

    url = "https://api.weather.yandex.ru/v2/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "limit": 10,
        "hours": False,
        "extra": False
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            target_date = datetime.strptime(date, "%Y-%m-%d").date()

            for forecast in data.get('forecasts', []):
                forecast_date = datetime.strptime(forecast['date'], "%Y-%m-%d").date()

                if forecast_date == target_date:
                    day_part = forecast.get('parts', {}).get('day', {})

                    if day_part:
                        temp = day_part.get('temp_avg', day_part.get('temp', 'Нет данных'))
                        condition = day_part.get('condition', '')
                        wind_speed = day_part.get('wind_speed', 0)
                        humidity = day_part.get('humidity', 0)
                        pressure = day_part.get('pressure_mm', 0)
                    else:
                        temp = forecast.get('fact', {}).get('temp', 'Нет данных')
                        condition = forecast.get('fact', {}).get('condition', '')
                        wind_speed = forecast.get('fact', {}).get('wind_speed', 0)
                        humidity = forecast.get('fact', {}).get('humidity', 0)
                        pressure = forecast.get('fact', {}).get('pressure_mm', 0)

                    conditions_ru = {
                        'clear': 'Ясно',
                        'partly-cloudy': 'Переменная облачность',
                        'cloudy': 'Облачно',
                        'overcast': 'Пасмурно',
                        'light-rain': 'Небольшой дождь',
                        'rain': 'Дождь',
                        'heavy-rain': 'Сильный дождь',
                        'showers': 'Ливень',
                        'wet-snow': 'Дождь со снегом',
                        'light-snow': 'Небольшой снег',
                        'snow': 'Снег',
                        'heavy-snow': 'Сильный снег',
                        'thunderstorm': 'Гроза',
                        'hail': 'Град'
                    }

                    precip_ru = conditions_ru.get(condition, condition)

                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%d.%m.%Y")

                    weather_info = f"""
Город: {city}
Дата: {formatted_date}
                    
Температура: {temp}°C
{precip_ru}
Ветер: {wind_speed} м/с
Влажность: {humidity}%
Давление: {pressure} мм рт. ст.
"""
                    print("API WEATHER", "OK")
                    return weather_info.strip()

            return "NOT FOUND ERROR"

        else:
            print(f"Ошибка HTTP: {response.status_code}")
            return "ERROR HTTP"

    except Exception as e:
        print(f"Ошибка при получении погоды: {e}")
        return "ERROR"


def save_to_pdf_and_upload(from_city, to_city, date, schedule, weather_info, yandex_filename=None):
    import tempfile
    import os

    if yandex_filename is None:
        from_clean = from_city.replace(' ', '_').replace('-', '_')
        to_clean = to_city.replace(' ', '_').replace('-', '_')
        yandex_filename = f"travel_{from_clean}_{to_clean}_{date}.pdf"

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    temp_filename = temp_file.name
    temp_file.close()

    try:
        try:
            pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))
            font_name = 'DejaVu'
        except:
            font_name = 'Helvetica'

        doc = SimpleDocTemplate(temp_filename, pagesize=A4,
                                rightMargin=15 * mm, leftMargin=15 * mm,
                                topMargin=20 * mm, bottomMargin=15 * mm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=font_name,
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.HexColor('#2E4053')
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=font_name,
            fontSize=14,
            alignment=TA_LEFT,
            spaceAfter=10,
            spaceBefore=15,
            textColor=colors.HexColor('#2874A6')
        )

        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            alignment=TA_LEFT,
            spaceAfter=6
        )

        elements = []

        elements.append(Paragraph("Информация для путешественника", title_style))
        elements.append(Spacer(1, 10))

        route_info = f"""
        <b>Маршрут:</b> {from_city} → {to_city}<br/>
        <b>Дата прибытия:</b> {date}
        """
        elements.append(Paragraph(route_info, normal_style))
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("Расписание рейсов:", heading_style))
        elements.append(Spacer(1, 5))

        table_data = [
            ['Вид транспорта', 'Номер рейса', 'Отправление', 'Прибытие', 'Время в пути']
        ]

        for trip in schedule:
            table_data.append([
                trip.get('transport_type', ''),
                trip.get('number', ''),
                trip.get('departure_time', ''),
                trip.get('arrival_time', ''),
                trip.get('duration', '')
            ])

        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2874A6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("Прогноз погоды:", heading_style))
        elements.append(Spacer(1, 5))

        weather_paragraphs = weather_info.split('\n')
        for line in weather_paragraphs:
            if line.strip():
                elements.append(Paragraph(line.strip(), normal_style))

        doc.build(elements)
        print(f"Временный PDF файл создан: {temp_filename}")

        upload_success = upload_to_yandex_disk(temp_filename, yandex_filename)

        if os.path.exists(temp_filename):
            os.unlink(temp_filename)
            print(f"Временный файл удален: {temp_filename}")

        return upload_success

    except Exception as e:
        print(f"Ошибка при создании PDF: {e}")
        if os.path.exists(temp_filename):
            try:
                os.unlink(temp_filename)
            except:
                pass
        return False


def upload_to_yandex_disk(file_path, yandex_filename=None):
    if YANDEX_TOKEN == "...":
        print("Токен Яндекс.Диска не настроен")
        return False

    headers = {'Authorization': f'OAuth {YANDEX_TOKEN}'}

    if yandex_filename is None:
        filename = os.path.basename(file_path)
    else:
        filename = yandex_filename

    folder_path = "/travel_app"
    full_path = f"{folder_path}/{filename}"

    create_folder_url = "https://cloud-api.yandex.net/v1/disk/resources"
    create_params = {"path": folder_path}

    try:
        create_response = requests.put(create_folder_url, headers=headers, params=create_params)

        if create_response.status_code == 201:
            print(f"Папка {folder_path} успешно создана")
        elif create_response.status_code == 409:
            print(f"Папка {folder_path} уже существует")

        upload_url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
        upload_params = {
            "path": full_path,
            "overwrite": "true"
        }

        print(f"Загрузка файла как: {full_path}")

        response = requests.get(upload_url, headers=headers, params=upload_params)

        if response.status_code == 200:
            upload_link = response.json()['href']

            with open(file_path, 'rb') as f:
                upload_response = requests.put(upload_link, data=f)

            if upload_response.status_code == 201:
                print(f"Файл {filename} успешно загружен на Яндекс.Диск")
                return True
            else:
                print(f"Ошибка загрузки: {upload_response.status_code}")
                return False
        else:
            print(f"Ошибка получения ссылки: {response.status_code}")
            print(f"Ответ: {response.text}")
            return False

    except Exception as e:
        print(f"Ошибка при загрузке на Яндекс.Диск: {e}")
        return False
