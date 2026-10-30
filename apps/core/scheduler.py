"""APScheduler orqali fon vazifalari (11-bo'lim).

Vazifalarning o'zi tegishli app'larda (masalan apps/payments/jobs.py) yoziladi;
bu modul faqat scheduler'ni ishga tushiradi va vazifalarni registratsiya qiladi.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings

logger = logging.getLogger(__name__)

_scheduler = None


def start():
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    _register_jobs(scheduler)
    scheduler.start()
    _scheduler = scheduler
    logger.info('APScheduler ishga tushdi')
    return scheduler


def _register_jobs(scheduler):
    try:
        from apps.payments.jobs import mark_overdue_schedules, remind_upcoming_due
        from apps.core.jobs import backup_database, cleanup_old_notifications

        scheduler.add_job(
            mark_overdue_schedules,
            CronTrigger(hour=0, minute=5),
            id='mark_overdue_schedules',
            replace_existing=True,
        )
        scheduler.add_job(
            remind_upcoming_due,
            CronTrigger(hour=9, minute=0),
            id='remind_upcoming_due',
            replace_existing=True,
        )
        scheduler.add_job(
            backup_database,
            CronTrigger(hour=2, minute=0),
            id='backup_database',
            replace_existing=True,
        )
        scheduler.add_job(
            cleanup_old_notifications,
            CronTrigger(day_of_week='mon', hour=3, minute=0),
            id='cleanup_old_notifications',
            replace_existing=True,
        )
    except ImportError:
        # Hali tegishli modullar yozilmagan bosqichda jim o'tkazib yuboramiz.
        logger.warning('Fon vazifalari hali to\'liq ro\'yxatga olinmadi (ImportError)')
