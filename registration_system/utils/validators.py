"""
Модуль для валидации данных пользователя
Содержит функции проверки возраста, имени, города, терапии и даты рождения
"""
import re
from datetime import datetime, date
from typing import Tuple, Optional


def validate_age(age_str: str) -> Tuple[bool, Optional[int], str]:
    """
    Проверка корректности возраста
    
    Args:
        age_str: Строка с возрастом
        
    Returns:
        (успех, возраст, сообщение об ошибке)
    """
    if not age_str or not age_str.strip():
        return False, None, "Возраст не может быть пустым"
    
    if not age_str.isdigit():
        return False, None, "Возраст должен быть числом"
    
    age = int(age_str)
    if age < 1 or age > 120:
        return False, None, "Возраст должен быть от 1 до 120 лет"
    
    return True, age, ""


def validate_name(name: str) -> Tuple[bool, Optional[str], str]:
    """
    Проверка корректности имени
    
    Args:
        name: Строка с именем
        
    Returns:
        (успех, имя, сообщение об ошибке)
    """
    if not name or not name.strip():
        return False, None, "Имя не может быть пустым"
    
    name = name.strip()
    if len(name) < 2:
        return False, None, "Имя должно содержать минимум 2 символа"
    
    if len(name) > 50:
        return False, None, "Имя слишком длинное (максимум 50 символов)"
    
    # Проверка на допустимые символы (буквы, пробелы, дефисы)
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s\-]+$', name):
        return False, None, "Имя может содержать только буквы, пробелы и дефисы"
    
    return True, name, ""


def validate_city(city: str) -> Tuple[bool, Optional[str], str]:
    """
    Проверка корректности названия города
    
    Args:
        city: Строка с названием города
        
    Returns:
        (успех, город, сообщение об ошибке)
    """
    if not city or not city.strip():
        return False, None, "Город не может быть пустым"
    
    city = city.strip()
    if len(city) < 2:
        return False, None, "Название города должно содержать минимум 2 символа"
    
    if len(city) > 100:
        return False, None, "Название города слишком длинное (максимум 100 символов)"
    
    # Проверка на допустимые символы
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s\-\.]+$', city):
        return False, None, "Название города может содержать только буквы, пробелы, дефисы и точки"
    
    return True, city, ""


def validate_therapy(therapy: str) -> Tuple[bool, Optional[str], str]:
    """
    Проверка корректности названия терапии
    
    Args:
        therapy: Строка с названием терапии
        
    Returns:
        (успех, терапия, сообщение об ошибке)
    """
    if not therapy or not therapy.strip():
        return False, None, "Название терапии не может быть пустым"
    
    therapy = therapy.strip()
    if len(therapy) < 2:
        return False, None, "Название терапии должно содержать минимум 2 символа"
    
    if len(therapy) > 200:
        return False, None, "Название терапии слишком длинное (максимум 200 символов)"
    
    return True, therapy, ""


def validate_birth_date(date_str: str) -> Tuple[bool, Optional[str], str, Optional[int]]:
    """
    Проверка корректности даты рождения и расчет возраста
    
    Args:
        date_str: Строка с датой в формате ДД.ММ.ГГГГ
        
    Returns:
        (успех, дата, сообщение об ошибке, возраст)
    """
    if not date_str or not date_str.strip():
        return False, None, "Дата рождения не может быть пустой", None
    
    date_str = date_str.strip()
    
    # Проверка формата
    if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_str):
        return False, None, "Дата должна быть в формате ДД.ММ.ГГГГ (например, 15.05.2010)", None
    
    try:
        # Парсим дату
        day, month, year = map(int, date_str.split('.'))
        birth_date = date(year, month, day)
        today = date.today()
        
        # Проверка на будущую дату
        if birth_date > today:
            return False, None, "Дата рождения не может быть в будущем", None
        
        # Проверка на слишком старую дату (более 120 лет)
        max_date = date(today.year - 120, today.month, today.day)
        if birth_date < max_date:
            return False, None, "Возраст не может быть более 120 лет", None
        
        # Расчет возраста
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        return True, date_str, "", age
        
    except ValueError:
        return False, None, "Некорректная дата. Проверьте правильность введенных чисел", None
    except Exception as e:
        return False, None, f"Ошибка при обработке даты: {str(e)}", None


def validate_ref_code(ref_code: str) -> Tuple[bool, Optional[str], str]:
    """
    Проверка корректности реферального кода (необязательное поле)
    
    Args:
        ref_code: Строка с реферальным кодом
        
    Returns:
        (успех, код, сообщение об ошибке)
    """
    if not ref_code or not ref_code.strip():
        return True, None, ""  # Пустой код допустим
    
    ref_code = ref_code.strip()
    if len(ref_code) > 50:
        return False, None, "Реферальный код слишком длинный (максимум 50 символов)"
    
    # Реферальный код может содержать буквы, цифры и некоторые символы
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', ref_code):
        return False, None, "Реферальный код может содержать только буквы, цифры, дефисы, подчеркивания и точки"
    
    return True, ref_code, ""


def validate_username(username: str) -> Tuple[bool, Optional[str], str]:
    """
    Проверка корректности username Telegram
    
    Args:
        username: Строка с username (без @)
        
    Returns:
        (успех, username, сообщение об ошибке)
    """
    if not username or not username.strip():
        return True, None, ""  # Пустой username допустим
    
    username = username.strip().lstrip('@')
    
    if len(username) < 3:
        return False, None, "Username должен содержать минимум 3 символа"
    
    if len(username) > 32:
        return False, None, "Username слишком длинный (максимум 32 символа)"
    
    # Username может содержать только буквы, цифры и подчеркивания
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, None, "Username может содержать только буквы, цифры и подчеркивания"
    
    return True, username, ""