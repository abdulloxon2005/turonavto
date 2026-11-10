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


@transaction.atomic
def expel_student(actor, student):
    student.status = Student.Status.EXPELLED
    student.save(update_fields=['status'])
    log_action(actor, action='student.expel', entity_type='Student', entity_id=student.pk)
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
    """O'quvchining guruhi, o'qish holati (studying/finished) va to'lov holatini qaytaradi.

    To'lov holati 4 ta qiymatdan biri bo'ladi: paid, partial, unpaid, debtor.
    O'qish davomida (hali tugamagan) qarz bo'lishi normal holat - 'debtor' deb hisoblanmaydi.
    Faqat o'qishni tugatib, to'lovi 100% bo'lmagan o'quvchi 'debtor' (qarzdor) hisoblanadi.
    """
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
        learning_status = 'finished' if group.learning_status == 'finished' else 'studying'
    else:
        learning_status = 'no_group'

    debt_info = student_debt_summary(student)
    if debt_info['enrollments']:
        total_due = sum(e['total_due'] for e in debt_info['enrollments'])
        paid = sum(e['paid'] for e in debt_info['enrollments'])
        debt = debt_info['total_debt']
    elif group is not None:
        total_due = group.price
        paid = 0
        debt = group.price
    else:
        total_due = 0
        paid = 0
        debt = 0

    if debt <= 0 and total_due > 0:
        payment_status = 'paid'
    elif learning_status == 'finished':
        payment_status = 'debtor'
    elif paid > 0:
        payment_status = 'partial'
    else:
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


def payment_breakdown(enriched_list):
    """To'lov holati bo'yicha (paid/partial/unpaid/debtor) o'quvchilar soni va summalarini hisoblaydi.

    Har bir indikator shu yerdagi son/summa ustidan ?payment_status=<key> filtriga mos keladi.
    """
    buckets = {'paid': [], 'partial': [], 'unpaid': [], 'debtor': []}
    for item in enriched_list:
        buckets.setdefault(item['payment_status'], []).append(item)

    return {
        'paid_count': len(buckets['paid']),
        'paid_sum': sum(i['paid'] for i in buckets['paid']),
        'partial_count': len(buckets['partial']),
        'partial_sum': sum(i['paid'] for i in buckets['partial']),
        'unpaid_count': len(buckets['unpaid']),
        'unpaid_sum': sum(i['debt'] for i in buckets['unpaid']),
        'debtor_count': len(buckets['debtor']),
        'debtor_sum': sum(i['debt'] for i in buckets['debtor']),
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


def _parse_date_cell(val):
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


def bulk_import_students_from_word(actor, file_obj, group):
    """Word (.docx) fayldagi jadvaldan o'quvchilarni ommaviy o'qib, guruhga qo'shadi."""
    import re

    from docx import Document

    if group.status != group.Status.OPEN:
        raise ValidationError("Yopilgan yoki arxivlangan guruhga o'quvchi qo'shib bo'lmaydi")

    try:
        doc = Document(file_obj)
    except Exception as exc:
        raise ValidationError("Word faylni o'qib bo'lmadi. Iltimos, .docx formatdagi fayl yuklang.") from exc

    if not doc.tables:
        raise ValidationError("Word fayl ichida jadval topilmadi. Namuna faylni yuklab, shu shablon asosida to'ldiring.")

    table = doc.tables[0]
    rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        raise ValidationError("Word fayldagi jadval bo'sh")

    # Sarlavha qatorini aniqlash
    first_row = [c.lower() for c in rows[0]]
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

        birth_date = _parse_date_cell(_cell(row, 'birth_date'))
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


def generate_student_import_sample_docx():
    """O'quvchilarni Word orqali yuklash uchun namuna .docx fayl."""
    import io

    from docx import Document

    headers = [
        "F.I.Sh (To'liq ism)",
        'Telefon',
        "Qo'shimcha telefon",
        'Pasport raqami',
        "Tug'ilgan sana (YYYY-MM-DD)",
        'Manzil',
        'Izoh',
    ]
    sample_rows = [
        ['Aliyev Vali G\'ani o\'g\'li', '+998901234567', '+998911234567', 'AD1234567', '2004-05-15', 'Toshkent sh., Chilonzor', ''],
        ['Karimova Malika Rustam qizi', '+998931112233', '', 'AC7654321', '2005-10-20', 'Toshkent sh., Yunusobod', ''],
    ]

    doc = Document()
    doc.add_heading("O'quvchilar ro'yxati — namuna", level=2)

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Light Grid Accent 1'
    header_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        header_cells[i].text = h
        for paragraph in header_cells[i].paragraphs:
            for run in paragraph.runs:
                run.bold = True

    for r in sample_rows:
        row_cells = table.add_row().cells
        for i, value in enumerate(r):
            row_cells[i].text = value

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()

