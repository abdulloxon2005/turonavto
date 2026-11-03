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


@pytest.mark.django_db
def test_teacher_cannot_access_kassa(teacher_client):
    response = teacher_client.get(reverse('payments:cash_list'))
    assert response.status_code == 403


@pytest.mark.django_db
def test_teacher_dashboard_shows_students_brought_and_collected(teacher_client, teacher_user, student, enrollment):
    from apps.payments.services import create_payment

    create_payment(teacher_user, student=student, enrollment=enrollment, amount=1_200_000, method='cash')
    response = teacher_client.get(reverse('core:dashboard'))
    assert response.status_code == 200
    stats = response.context['stats']
    assert stats['students_count'] == 1
    assert stats['brought_students_count'] == 1
    assert stats['total_collected'] == 1_200_000


@pytest.mark.django_db
def test_teacher_can_add_student_to_group_but_cannot_remove(teacher_client, teacher_user, admin_user, group, student):
    from apps.groups.models import GroupTeacher

    GroupTeacher.objects.get_or_create(group=group, user=teacher_user)
    new_s = Student.objects.create(full_name='Guruhga qoshiluvchi', phone='+998901112233', brought_by_user_id=admin_user)

    add_resp = teacher_client.post(reverse('groups:student_add', args=[group.pk]), {'student_id': new_s.pk})
    assert add_resp.status_code == 302
    assert group.group_students.filter(student=new_s, left_at__isnull=True).exists()

    remove_resp = teacher_client.post(reverse('groups:student_remove', args=[group.pk, new_s.pk]))
    assert remove_resp.status_code == 403


@pytest.mark.django_db
def test_bulk_excel_import_adds_multiple_students(teacher_user, group):
    import io
    from openpyxl import Workbook
    from apps.groups.models import GroupTeacher
    from apps.students.services import bulk_import_students_from_excel

    GroupTeacher.objects.get_or_create(group=group, user=teacher_user)
    wb = Workbook()
    ws = wb.active
    ws.append(['F.I.Sh', 'Telefon', 'Qo\'shimcha telefon', 'Pasport', 'Tug\'ilgan sana', 'Manzil'])
    ws.append(['Olimov Sardor', '901234567', '', 'AD1112233', '2003-04-10', 'Toshkent'])
    ws.append(['Rasulova Dilnoza', '+998937654321', '', 'AC9998877', '2005-08-22', 'Samarqand'])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    created, errors = bulk_import_students_from_excel(teacher_user, buf, group)
    assert len(created) == 2
    assert errors == []
    assert all(s.brought_by_user_id == teacher_user for s in created)
    assert group.active_student_count == 2


@pytest.mark.django_db
def test_my_brought_students_view_learning_and_payment_statuses(teacher_client, teacher_user, group, student, enrollment):
    response = teacher_client.get(reverse('students:my_brought'))
    assert response.status_code == 200
    assert response.context['stats']['total'] == 1
    assert len(response.context['items']) == 1
    item = response.context['items'][0]
    assert item['student'] == student
    assert item['payment_status'] == 'unpaid'


@pytest.mark.django_db
def test_instructor_cannot_access_kassa_debtors_lessons_notifications(instructor_client):
    assert instructor_client.get(reverse('payments:cash_list')).status_code == 403
    assert instructor_client.get(reverse('payments:debtors')).status_code == 403
    assert instructor_client.get(reverse('lessons:list')).status_code == 403
    assert instructor_client.get(reverse('notifications:list')).status_code == 403


@pytest.mark.django_db
def test_instructor_dashboard_and_students_list_show_student_info(
    instructor_client, instructor_user, group
):
    from apps.groups.models import GroupInstructor

    GroupInstructor.objects.get_or_create(group=group, user=instructor_user)
    own_student = create_student(
        instructor_user, full_name='Instruktor Oquvchisi', phone='+998944445566', group=group
    )
    dash_resp = instructor_client.get(reverse('core:dashboard'))
    assert dash_resp.status_code == 200
    assert dash_resp.context['stats']['students_count'] == 1
    assert dash_resp.context['stats']['brought_students_count'] == 1
    assert dash_resp.context['stats']['groups_count'] == 1

    list_resp = instructor_client.get(reverse('students:list'))
    assert list_resp.status_code == 200
    assert own_student in list_resp.context['students']
    assert list_resp.context['stats']['total'] == 1
    assert list_resp.context['stats']['debtors_count'] == 1


