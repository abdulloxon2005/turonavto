import datetime

import pytest
from django.core.exceptions import ValidationError

from apps.groups.models import Group
from apps.groups.services import add_student_to_group, delete_group
from apps.students.models import Student


@pytest.mark.django_db
def test_group_capacity_enforced(admin_user, group):
    group.max_students = 1
    group.save()
    s1 = Student.objects.create(full_name='A', phone='+998911111111', brought_by_user_id=admin_user)
    s2 = Student.objects.create(full_name='B', phone='+998922222222', brought_by_user_id=admin_user)

    add_student_to_group(admin_user, group, s1)
    with pytest.raises(ValidationError):
        add_student_to_group(admin_user, group, s2)


@pytest.mark.django_db
def test_closed_group_rejects_new_student(admin_user, group):
    group.status = Group.Status.CLOSED
    group.save()
    s1 = Student.objects.create(full_name='A', phone='+998911111111', brought_by_user_id=admin_user)
    with pytest.raises(ValidationError):
        add_student_to_group(admin_user, group, s1)


@pytest.mark.django_db
def test_cannot_delete_group_with_members(admin_user, group, student):
    with pytest.raises(ValidationError):
        delete_group(admin_user, group)


@pytest.mark.django_db
def test_can_delete_empty_group(admin_user):
    empty_group = Group.objects.create(
        name='Bo\'sh guruh', category='B', start_date=datetime.date(2026, 1, 1), price=1_000_000,
    )
    delete_group(admin_user, empty_group)
    assert not Group.objects.filter(pk=empty_group.pk).exists()
