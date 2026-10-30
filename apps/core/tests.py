import pytest
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.core.models import AuditLog
from apps.core.services import log_action


@pytest.mark.django_db
def test_audit_log_cannot_be_updated(admin_user):
    entry = log_action(admin_user, action='test.action', entity_type='Test', entity_id=1)
    entry.action = 'changed'
    with pytest.raises(PermissionDenied):
        with transaction.atomic():
            entry.save()


@pytest.mark.django_db
def test_audit_log_cannot_be_deleted(admin_user):
    entry = log_action(admin_user, action='test.action', entity_type='Test', entity_id=1)
    with pytest.raises(PermissionDenied):
        with transaction.atomic():
            entry.delete()
    assert AuditLog.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_audit_log_records_old_and_new_values(admin_user):
    entry = log_action(
        admin_user, action='test.update', entity_type='Test', entity_id=1,
        old_value={'a': 1}, new_value={'a': 2},
    )
    assert entry.old_value == {'a': 1}
    assert entry.new_value == {'a': 2}
