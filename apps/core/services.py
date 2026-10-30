from .middleware import get_client_ip, get_current_request
from .models import AuditLog


def log_action(user, action, entity_type, entity_id='', old_value=None, new_value=None, request=None):
    """Pul/boshqaruv amalini audit_log'ga yozadi. Faqat qo'shish, hech qachon o'zgartirilmaydi."""

    request = request or get_current_request()
    ip = get_client_ip(request) if request else None
    return AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        old_value=old_value,
        new_value=new_value,
        ip=ip,
    )
