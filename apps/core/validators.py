from django.conf import settings
from django.core.exceptions import ValidationError


def validate_image_size(file):
    if file.size > settings.MAX_UPLOAD_IMAGE_SIZE:
        max_mb = settings.MAX_UPLOAD_IMAGE_SIZE / (1024 * 1024)
        raise ValidationError(f"Rasm hajmi {max_mb:.0f} MB dan oshmasligi kerak")
