"""GET filtr parametrlarini xavfsiz o'qish.

Real-time filtrda foydalanuvchi yozayotgan paytda yarim-yorti yoki noto'g'ri qiymatlar
(harf, bo'sh joy, juda katta son, noto'g'ri sana) yuboriladi. Ular hech qachon 500 xatoga
olib kelmasligi kerak: noto'g'ri qiymat shunchaki "filtr yo'q" deb hisoblanadi.
"""
import datetime

_MAX_DB_INT = 2 ** 63 - 1


def int_param(request, name, minimum=None, maximum=_MAX_DB_INT):
    """GET[name] ni int ga o'giradi; yaroqsiz bo'lsa None qaytaradi."""
    raw = (request.GET.get(name) or '').strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    return value


def date_param(request, name):
    """GET[name] ni (YYYY-MM-DD) date ga o'giradi; yaroqsiz bo'lsa None."""
    try:
        return datetime.date.fromisoformat((request.GET.get(name) or '').strip())
    except ValueError:
        return None
