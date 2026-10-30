"""Core uchun umumiy fon vazifalari: zaxira nusxa va eski xabarlarni tozalash."""

import datetime
import logging
import shutil
import sqlite3
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def backup_database():
    """SQLite ma'lumotlar bazasidan kunlik zaxira nusxa oladi (sqlite3 .backup).

    Oxirgi BACKUP_KEEP_COUNT nusxa saqlanadi, qolganlari o'chiriladi.
    """

    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    dest_path = settings.BACKUP_DIR / f'backup_{timestamp}.sqlite3'

    src = sqlite3.connect(settings.DATABASES['default']['NAME'])
    dest = sqlite3.connect(str(dest_path))
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()

    _rotate_backups()
    logger.info('Zaxira nusxa olindi: %s', dest_path)
    return dest_path


def _rotate_backups():
    backups = sorted(
        Path(settings.BACKUP_DIR).glob('backup_*.sqlite3'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[settings.BACKUP_KEEP_COUNT:]:
        old.unlink(missing_ok=True)


def cleanup_old_notifications():
    """90 kundan eski, o'qilgan xabarnomalarni o'chiradi."""

    from apps.notifications.models import Notification

    threshold = timezone.now() - datetime.timedelta(days=90)
    deleted, _ = Notification.objects.filter(created_at__lt=threshold, is_read=True).delete()
    logger.info('Eski xabarnomalar tozalandi: %s ta', deleted)
    return deleted
