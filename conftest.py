import datetime

import pytest

from apps.accounts.models import User
from apps.groups.models import Group
from apps.students.models import Student


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(phone='+998900000001', password='pass12345', full_name='Admin')


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        phone='+998900000002', password='pass12345', full_name='Teacher One',
        role=User.Role.TEACHER, must_change_password=False,
    )


@pytest.fixture
def other_teacher_user(db):
    return User.objects.create_user(
        phone='+998900000003', password='pass12345', full_name='Teacher Two',
        role=User.Role.TEACHER, must_change_password=False,
    )


@pytest.fixture
def instructor_user(db):
    return User.objects.create_user(
        phone='+998900000004', password='pass12345', full_name='Instructor One',
        role=User.Role.INSTRUCTOR, must_change_password=False,
    )


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def teacher_client(client, teacher_user):
    client.force_login(teacher_user)
    return client


@pytest.fixture
def other_teacher_client(client, other_teacher_user):
    client.force_login(other_teacher_user)
    return client


@pytest.fixture
def instructor_client(client, instructor_user):
    client.force_login(instructor_user)
    return client


@pytest.fixture
def group(db):
    return Group.objects.create(
        name='Test Group', category='B', start_date=datetime.date(2026, 1, 1),
        price=3_000_000, max_students=25,
    )


@pytest.fixture
def student(db, teacher_user, group):
    from apps.groups.models import GroupStudent, GroupTeacher

    GroupTeacher.objects.get_or_create(group=group, user=teacher_user)
    s = Student.objects.create(full_name='Test Student', phone='+998900000010', brought_by_user_id=teacher_user)
    GroupStudent.objects.create(group=group, student=s)
    return s


@pytest.fixture
def enrollment(db, student, group, admin_user):
    from apps.payments.models import Enrollment

    return Enrollment.objects.create(
        student=student, group=group, price=3_000_000, discount=0, total_due=3_000_000,
        created_by=admin_user,
    )
