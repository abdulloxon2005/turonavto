import pytest
from django.urls import reverse

from apps.students.models import Student
from apps.students.services import can_edit_student, create_student, visible_students_queryset


@pytest.mark.django_db
def test_owner_auto_set_on_create(teacher_user, group):
    student = create_student(teacher_user, full_name='Yangi Talaba', phone='+998911111111', group=group)
    assert student.brought_by_user_id == teacher_user


@pytest.mark.django_db
def test_teacher_sees_only_own_group_students(teacher_user, other_teacher_user, student):
    assert student in visible_students_queryset(teacher_user)
    assert student not in visible_students_queryset(other_teacher_user)


@pytest.mark.django_db
def test_can_edit_student_owner_or_admin_only(admin_user, teacher_user, other_teacher_user, student):
    assert can_edit_student(teacher_user, student) is True
    assert can_edit_student(admin_user, student) is True
    assert can_edit_student(other_teacher_user, student) is False


# --- HTTP darajasida: 403/404 qoidasi ---

@pytest.mark.django_db
def test_unrelated_teacher_gets_404_on_student_detail(other_teacher_client, student):
    response = other_teacher_client.get(reverse('students:detail', args=[student.pk]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_owner_teacher_can_view_student_detail(teacher_client, student):
    response = teacher_client.get(reverse('students:detail', args=[student.pk]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_non_owner_cannot_edit_student_403(teacher_client, teacher_user, other_teacher_user, group):
    foreign_student = Student.objects.create(
        full_name='Boshqa Talaba', phone='+998922222222', brought_by_user_id=other_teacher_user,
    )
    from apps.groups.models import GroupStudent, GroupTeacher

    GroupTeacher.objects.get_or_create(group=group, user=teacher_user)
    GroupStudent.objects.create(group=group, student=foreign_student)
    # teacher_client teacher_user bilan ishlaydi — guruhda a'zo bo'lgani uchun ko'ra oladi,
    # lekin egasi emasligi uchun tahrirlay olmaydi.
    response = teacher_client.get(reverse('students:update', args=[foreign_student.pk]))
    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_only_pages_403_for_teacher(teacher_client):
    response = teacher_client.get(reverse('accounts:staff_list'))
    assert response.status_code == 403


@pytest.mark.django_db
def test_unauthenticated_redirected_to_login(client, student):
    response = client.get(reverse('students:detail', args=[student.pk]))
    assert response.status_code == 302
    assert reverse('accounts:login') in response.url


# --- Instruktor: biriktirilgan (view-only) vs o'zi olib kelgan ---

@pytest.mark.django_db
def test_instructor_sees_assigned_student_but_cannot_edit(admin_user, instructor_user, student):
    from apps.students.services import assign_instructor

    assign_instructor(admin_user, student, instructor_user)
    assert student in visible_students_queryset(instructor_user)
    assert can_edit_student(instructor_user, student) is False


@pytest.mark.django_db
def test_instructor_sees_own_brought_student_without_assignment(instructor_user, group):
    from apps.groups.models import GroupInstructor, GroupStudent

    GroupInstructor.objects.get_or_create(group=group, user=instructor_user)
    own_student = create_student(instructor_user, full_name='Instruktor talabasi', phone='+998933333333', group=group)
    assert own_student in visible_students_queryset(instructor_user)
    assert can_edit_student(instructor_user, own_student) is True


@pytest.mark.django_db
def test_admin_sees_all_students(admin_user, student):
    assert student in visible_students_queryset(admin_user)


# --- Dublikat tekshiruvi ---

@pytest.mark.django_db
def test_find_duplicates_by_phone(student):
    from apps.students.services import find_duplicates

    duplicates = find_duplicates(student.phone)
    assert student in duplicates

    duplicates_excluded = find_duplicates(student.phone, exclude_pk=student.pk)
    assert student not in duplicates_excluded


# --- Egani o'zgartirish va o'chirish so'rovi oqimi ---

@pytest.mark.django_db
def test_change_owner(admin_user, other_teacher_user, student):
    from apps.students.services import change_owner

    change_owner(admin_user, student, other_teacher_user)
    student.refresh_from_db()
    assert student.brought_by_user_id == other_teacher_user


@pytest.mark.django_db
def test_delete_request_flow_removes_student_without_payments(admin_user, teacher_user, student):
    from apps.students.services import create_delete_request, decide_delete_request

    dr = create_delete_request(teacher_user, student, 'Xato kiritilgan')
    decide_delete_request(admin_user, dr, approve=True)

    dr.refresh_from_db()
    assert dr.status == 'approved'
    assert not Student.objects.filter(pk=student.pk).exists()


@pytest.mark.django_db
def test_delete_request_rejected_keeps_student(admin_user, teacher_user, student):
    from apps.students.services import create_delete_request, decide_delete_request

    dr = create_delete_request(teacher_user, student, 'Xato')
    decide_delete_request(admin_user, dr, approve=False, note='Asossiz')

    assert Student.objects.filter(pk=student.pk).exists()
    dr.refresh_from_db()
    assert dr.status == 'rejected'


@pytest.mark.django_db
def test_delete_request_with_payment_history_archives_instead_of_deletes(admin_user, teacher_user, student, enrollment):
    from apps.students.services import create_delete_request, decide_delete_request

    dr = create_delete_request(teacher_user, student, 'Xato')
    decide_delete_request(admin_user, dr, approve=True)

    student.refresh_from_db()
    assert student.status == Student.Status.ARCHIVED
    assert Student.objects.filter(pk=student.pk).exists()
