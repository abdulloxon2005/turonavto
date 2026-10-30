import os
import sys

from django.apps import AppConfig


def _should_start_scheduler():
    """APScheduler faqat bitta worker/jarayonda ishga tushishi kerak.

    - `manage.py runserver` autoreload bilan ikki marta import bo'ladi, shuning
      uchun faqat RUN_MAIN='true' bo'lgan asosiy jarayonda ishga tushamiz.
    - Boshqa manage.py buyruqlarida (migrate, makemigrations, test, shell, ...)
      umuman ishga tushmasligi kerak.
    - gunicorn/wsgi orqali ishga tushganda (manage.py umuman chaqirilmaydi)
      bitta marta ishga tushadi; production'da gunicorn --workers 1 bilan
      ishlatilishi shart.
    """

    argv = sys.argv
    is_manage_py = len(argv) > 0 and 'manage.py' in argv[0]
    if is_manage_py:
        if len(argv) < 2 or argv[1] != 'runserver':
            return False
        return os.environ.get('RUN_MAIN') == 'true'
    return True


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core'

    def ready(self):
        from . import signals  # noqa: F401

        from django.conf import settings

        if settings.RUN_SCHEDULER and _should_start_scheduler():
            from . import scheduler
            scheduler.start()
