from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.services import log_action
from apps.notifications.services import notify

from .models import DeleteRequest, InstructorStudent, Student


def visible_students_queryset(user):
    """Rolga qarab ko'rinadigan o'quvchilar ro'yxati (RBAC Guard)."""
    from django.db.models import Q

    if user.is_admin():
        return Student.objects.all()
    if user.is_teacher():
        return Student.objects.filter(
            Q(group_memberships__group__group_teachers__user=user) | Q(brought_by_user_id=user)
        ).distinct()
    if user.is_instructor():
        return Student.objects.filter(
            _instructor_visibility_q(user)
        ).distinct()
    return Student.objects.none()


def _instructor_visibility_q(user):
    from django.db.models import Q

    return (
        Q(instructor_links__instructor=user)
        | Q(brought_by_user_id=user)
        | Q(group_memberships__group__group_instructors__user=user)
    )


def can_edit_student(user, student):
    if user.is_admin():
        return True
    return student.brought_by_user_id_id == user.id


def find_duplicates(phone, passport_no=None, exclude_pk=None):
    qs = Student.objects.filter(phone=phone)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs


@transaction.atomic
def create_student(actor, *, full_name, phone, phone2='', passport_no=None, birth_date=None,
                    address='', photo=None, note='', group=None):
    if group is not None:
        if group.status != group.Status.OPEN:
            raise ValidationError("Yopilgan yoki arxivlangan guruhga o'quvchi qo'shib bo'lmaydi")
        if group.is_full:
            raise ValidationError("Guruh to'lgan (max_students chegarasiga yetgan)")

    student = Student.objects.create(
        full_name=full_name,
        phone=phone,
        phone2=phone2,
        passport_no=passport_no or None,
        birth_date=birth_date,
        address=address,
        photo=photo,
        note=note,
        brought_by_user_id=actor,
    )

    if group is not None:
        from apps.groups.models import GroupStudent
        from apps.payments.models import Enrollment

        GroupStudent.objects.create(group=group, student=student)
        Enrollment.objects.get_or_create(
            student=student,
            group=group,
            defaults={
                'price': group.price,
                'discount': 0,
                'total_due': group.price,
                'created_by': actor,
            },
        )

    log_action(
        actor,
        action='student.create',
        entity_type='Student',
        entity_id=student.pk,
        new_value={'full_name': full_name, 'phone': phone, 'group_id': group.pk if group else None},
    )
    return student


@transaction.atomic
def update_student(actor, student, *, full_name, phone, phone2='', passport_no=None,
                    birth_date=None, address='', photo=None, note=''):
    old_value = {
        'full_name': student.full_name,
        'phone': student.phone,
        'phone2': student.phone2,
        'passport_no': student.passport_no,
        'address': student.address,
    }
    student.full_name = full_name
    student.phone = phone
    student.phone2 = phone2
    student.passport_no = passport_no or None
    student.birth_date = birth_date
    student.address = address
    student.note = note
    if photo:
        student.photo = photo
    student.save()

    log_action(
        actor,
        action='student.update',
        entity_type='Student',
        entity_id=student.pk,
        old_value=old_value,
        new_value={'full_name': full_name, 'phone': phone, 'phone2': phone2, 'passport_no': passport_no, 'address': address},
    )
    return student


@transaction.atomic
def change_owner(actor, student, new_owner):
    old_owner_id = student.brought_by_user_id_id
    student.brought_by_user_id = new_owner
    student.save(update_fields=['brought_by_user_id'])
    log_action(
        actor,
        action='student.change_owner',
        entity_type='Student',
        entity_id=student.pk,
        old_value={'brought_by_user_id': old_owner_id},
        new_value={'brought_by_user_id': new_owner.id},
    )
    return student


@transaction.atomic
def assign_instructor(actor, student, instructor):
    link, created = InstructorStudent.objects.get_or_create(
        student=student, instructor=instructor, defaults={'assigned_by': actor}
    )
    if created:
        log_action(
            actor,
            action='student.assign_instructor',
            entity_type='Student',
            entity_id=student.pk,
            new_value={'instructor_id': instructor.id},
        )
        notify(
            instructor,
            type='instructor_assigned',
            title="Sizga o'quvchi biriktirildi",
            body=student.full_name,
            link=f'/oquvchilar/{student.pk}/',
        )
    return link


@transaction.atomic
def unassign_instructor(actor, student, instructor):
    deleted, _ = InstructorStudent.objects.filter(student=student, instructor=instructor).delete()
    if deleted:
        log_action(
            actor,
            action='student.unassign_instructor',
            entity_type='Student',
            entity_id=student.pk,
            old_value={'instructor_id': instructor.id},
        )
    return deleted


@transaction.atomic
def archive_student(actor, student):
    student.status = Student.Status.ARCHIVED
    student.save(update_fields=['status'])
    log_action(actor, action='student.archive', entity_type='Student', entity_id=student.pk)
    return student


@transaction.atomic
def unarchive_student(actor, student):
    student.status = Student.Status.ACTIVE
    student.save(update_fields=['status'])
    log_action(actor, action='student.unarchive', entity_type='Student', entity_id=student.pk)
    return student


def has_payment_history(student):
    """3-bosqichda `payments` app qo'shilgach, enrollment/payment mavjudligini tekshiradi.

    Hozircha to'lov moduli yo'q, shuning uchun har doim False qaytaradi.
    """

    try:
        return student.enrollments.exists()
    except AttributeError:
        return False


@transaction.atomic
def delete_student(actor, student):
    if has_payment_history(student):
        raise ValidationError("To'lovi bor o'quvchi o'chirilmaydi, faqat arxivlanadi")
    entity_id = student.pk
    log_action(actor, action='student.delete', entity_type='Student', entity_id=entity_id,
               old_value={'full_name': student.full_name})
    student.delete()


@transaction.atomic
def create_delete_request(actor, student, reason):
    delete_request = DeleteRequest.objects.create(
        requested_by=actor,
        entity_type=DeleteRequest.EntityType.STUDENT,
        entity_id=student.pk,
        reason=reason,
    )
    log_action(
        actor,
        action='delete_request.create',
        entity_type='Student',
        entity_id=student.pk,
        new_value={'reason': reason},
    )
    from apps.accounts.models import User

    for admin in User.objects.filter(role=User.Role.ADMIN, is_active=True):
        notify(
            admin,
            type='delete_request',
            title="Yangi o'chirish so'rovi",
            body=f'{actor.full_name}: {student.full_name} — {reason}',
            link='/oquvchilar/ochirish-sorovlari/',
        )
    return delete_request


@transaction.atomic
def decide_delete_request(actor, delete_request, approve, note=''):
    if delete_request.status != DeleteRequest.Status.PENDING:
        raise ValidationError("So'rov allaqachon ko'rib chiqilgan")

    delete_request.status = DeleteRequest.Status.APPROVED if approve else DeleteRequest.Status.REJECTED
    delete_request.decided_by = actor
    delete_request.decision_note = note
    delete_request.decided_at = timezone.now()
    delete_request.save()

    student = delete_request.student
    if approve and student is not None:
        if has_payment_history(student):
            archive_student(actor, student)
        else:
            delete_student(actor, student)

    log_action(
        actor,
        action='delete_request.decide',
        entity_type='DeleteRequest',
        entity_id=delete_request.pk,
        new_value={'status': delete_request.status, 'note': note},
    )

    notify(
        delete_request.requested_by,
        type='delete_decided',
        title="O'chirish so'rovingiz ko'rib chiqildi",
        body=delete_request.get_status_display(),
    )
    return delete_request


def student_enriched_info(student):
    """O'quvchining guruhi, o'qish holati (studying/ending_soon/finished) va to'lov holatini qaytaradi."""
    from apps.payments.services import student_debt_summary

    membership = (
        student.group_memberships.filter(left_at__isnull=True)
        .select_related('group')
        .order_by('-joined_at')
        .first()
    )
    if membership is None:
        membership = (
            student.group_memberships.select_related('group')
            .order_by('-joined_at')
            .first()
        )
    group = membership.group if membership else None

    if student.status == Student.Status.ARCHIVED:
        learning_status = 'finished'
    elif group is not None:
        learning_status = group.learning_status
    else:
        learning_status = 'no_group'

    debt_info = student_debt_summary(student)
    if debt_info['enrollments']:
        total_due = sum(e['total_due'] for e in debt_info['enrollments'])
        paid = sum(e['paid'] for e in debt_info['enrollments'])
        debt = debt_info['total_debt']
        payment_status = debt_info['status'] or 'unpaid'
    elif group is not None:
        total_due = group.price
        paid = 0
        debt = group.price
        payment_status = 'unpaid'
    else:
        total_due = 0
        paid = 0
        debt = 0
        payment_status = 'unpaid'

    return {
        'student': student,
        'group': group,
        'learning_status': learning_status,
        'days_remaining': group.days_remaining if group else None,
        'total_due': total_due,
        'paid': paid,
        'debt': debt,
        'payment_status': payment_status,
    }


def normalize_phone(raw_phone):
    """Turli formatdagi telefon raqamlarini +998901234567 ko'rinishiga keltiradi."""
    import re

    if raw_phone is None:
        return ''
    text = str(raw_phone).strip()
    if text.endswith('.0'):
        text = text[:-2]
    digits = re.sub(r'\D', '', text)
    if not digits:
        return ''
    if len(digits) == 9:
        return f'+998{digits}'
    if len(digits) == 12 and digits.startswith('998'):
        return f'+{digits}'
    if text.startswith('+'):
        return f'+{digits}'
    return f'+{digits}' if len(digits) >= 10 else digits


def _parse_excel_date(val):
    import datetime

    if not val:
        return None
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, datetime.date):
        return val
    text = str(val).strip()
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def bulk_import_students_from_excel(actor, file_obj, group):
    """Excel (.xlsx) fayldan o'quvchilarni ommaviy o'qib, guruhga qo'shadi."""
    import re
    from openpyxl import load_workbook

    if group.status != group.Status.OPEN:
        raise ValidationError("Yopilgan yoki arxivlangan guruhga o'quvchi qo'shib bo'lmaydi")

    try:
        wb = load_workbook(filename=file_obj, data_only=True)
    except Exception as exc:
        raise ValidationError("Excel faylni o'qib bo'lmadi. Iltimos, .xlsx formatdagi fayl yuklang.") from exc

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValidationError("Excel fayl bo'sh")

    # Sarlavha qatorini aniqlash
    first_row = [str(c).strip().lower() if c is not None else '' for c in rows[0]]
    header_keywords = ('ism', 'f.i', 'fio', 'full_name', 'familiya', 'telefon', 'tel', 'phone', 'pasport')
    has_header = any(any(k in cell for k in header_keywords) for cell in first_row)

    col_map = {
        'full_name': 0,
        'phone': 1,
        'phone2': 2,
        'passport_no': 3,
        'birth_date': 4,
        'address': 5,
        'note': 6,
    }

    if has_header:
        detected = {}
        for idx, h in enumerate(first_row):
            if any(k in h for k in ('ism', 'f.i', 'fio', 'full_name', 'familiya', "o'quvchi", 'oquvchi')):
                detected.setdefault('full_name', idx)
            elif any(k in h for k in ('qo\'shimcha', 'qoshimcha', 'tel2', 'telefon 2', 'phone2')):
                detected.setdefault('phone2', idx)
            elif any(k in h for k in ('telefon', 'tel', 'phone', 'raqam')):
                detected.setdefault('phone', idx)
            elif any(k in h for k in ('pasport', 'passport', 'seriya')):
                detected.setdefault('passport_no', idx)
            elif any(k in h for k in ('tug', 'birth', 'sana')):
                detected.setdefault('birth_date', idx)
            elif any(k in h for k in ('manzil', 'address', 'yashash')):
                detected.setdefault('address', idx)
            elif any(k in h for k in ('izoh', 'note', 'eslatma')):
                detected.setdefault('note', idx)
        if 'full_name' in detected and 'phone' in detected:
            col_map = detected
        data_rows = rows[1:]
        start_row_num = 2
    else:
        data_rows = rows
        start_row_num = 1

    created_students = []
    errors = []
    phone_regex = re.compile(r'^\+?\d{9,15}$')

    def _cell(row, key):
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    for offset, row in enumerate(data_rows):
        row_num = start_row_num + offset
        if not row or all(c is None or str(c).strip() == '' for c in row):
            continue

        raw_name = _cell(row, 'full_name')
        raw_phone = _cell(row, 'phone')
        full_name = str(raw_name).strip() if raw_name is not None else ''
        phone = normalize_phone(raw_phone)

        if not full_name:
            errors.append(f"{row_num}-qator: To'liq ism kiritilmagan")
            continue
        if not phone or not phone_regex.match(phone):
            errors.append(f"{row_num}-qator ({full_name}): Telefon raqami noto'g'ri ('{raw_phone}')")
            continue

        raw_phone2 = _cell(row, 'phone2')
        phone2 = normalize_phone(raw_phone2) if raw_phone2 else ''
        if phone2 and not phone_regex.match(phone2):
            phone2 = ''

        raw_passport = _cell(row, 'passport_no')
        passport_no = str(raw_passport).strip().upper().replace(' ', '') if raw_passport else ''
        if passport_no.endswith('.0'):
            passport_no = passport_no[:-2]

        birth_date = _parse_excel_date(_cell(row, 'birth_date'))
        raw_address = _cell(row, 'address')
        address = str(raw_address).strip() if raw_address else ''
        raw_note = _cell(row, 'note')
        note = str(raw_note).strip() if raw_note else ''

        if group.is_full:
            errors.append(f"{row_num}-qator ({full_name}): Guruh to'lgan ({group.max_students} ta limit)")
            break

        if passport_no and Student.objects.filter(passport_no=passport_no).exists():
            errors.append(f"{row_num}-qator ({full_name}): '{passport_no}' pasport raqami allaqachon mavjud")
            continue

        try:
            student = create_student(
                actor,
                full_name=full_name,
                phone=phone,
                phone2=phone2,
                passport_no=passport_no or None,
                birth_date=birth_date,
                address=address,
                note=note,
                group=group,
            )
            created_students.append(student)
        except Exception as exc:
            msg = getattr(exc, 'message', str(exc))
            errors.append(f"{row_num}-qator ({full_name}): {msg}")

    return created_students, errors


def generate_student_import_sample_xlsx():
    """O'quvchilarni Excel orqali yuklash uchun namuna .xlsx fayl."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "O'quvchilar ro'yxati"

    headers = [
        "F.I.Sh (To'liq ism)",
        'Telefon',
        "Qo'shimcha telefon",
        'Pasport raqami',
        "Tug'ilgan sana (YYYY-MM-DD)",
        'Manzil',
        'Izoh',
    ]
    ws.append(headers)
    header_fill = PatternFill(start_color='2563EB', end_color='2563EB', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF')
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font

    sample_rows = [
        ['Aliyev Vali G\'ani o\'g\'li', '+998901234567', '+998911234567', 'AD1234567', '2004-05-15', 'Toshkent sh., Chilonzor', ''],
        ['Karimova Malika Rustam qizi', '+998931112233', '', 'AC7654321', '2005-10-20', 'Toshkent sh., Yunusobod', ''],
    ]
    for r in sample_rows:
        ws.append(r)

    for column_cells in ws.columns:
        length = max(len(str(c.value)) if c.value is not None else 0 for c in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(max(length + 4, 14), 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()

