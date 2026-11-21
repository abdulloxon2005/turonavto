from django.contrib.auth.backends import ModelBackend

from .models import User


class PhoneBackend(ModelBackend):
    """Telefon + parol orqali autentifikatsiya (xato urinishlar uchun blok yo'q)."""

    def authenticate(self, request, phone=None, password=None, username=None, **kwargs):
        # Django admin va boshqa standart joylar `username=` nomi bilan yuboradi
        # (USERNAME_FIELD='phone' bo'lsa ham); shu sababli ikkalasini ham qabul qilamiz.
        phone = phone or username
        if phone is None or password is None:
            return None

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            User().set_password(password)  # timing-attack oldini olish
            return None

        if user.check_password(password):
            # is_active tekshiruvi shu yerda emas, LoginView'da amalga oshiriladi —
            # shunda bloklangan hodim aniq xabar oladi va urinish muvaffaqiyatsiz hisoblanmaydi.
            return user

        return None
