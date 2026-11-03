from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.services import log_action

from .models import Group, GroupInstructor, GroupStudent, GroupTeacher


def visible_groups_queryset(user):
    if user.is_admin():
        return Group.objects.all()
    if user.is_teacher():
        return Group.objects.filter(group_teachers__user=user).distinct()
    if user.is_instructor():
        return Group.objects.filter(group_instructors__user=user).distinct()
    return Group.objects.none()


@transaction.atomic
def create_group(actor, **fields):
    group = Group.objects.create(**fields)
    log_action(actor, action='group.create', entity_type='Group', entity_id=group.pk, new_value=_jsonable(fields))
    return group


@transaction.atomic
def update_group(actor, group, **fields):
    old_value = {k: getattr(group, k) for k in fields}
    for key, value in fields.items():
        setattr(group, key, value)
    group.save()
    log_action(
        actor, action='group.update', entity_type='Group', entity_id=group.pk,
        old_value=_jsonable(old_value), new_value=_jsonable(fields),
    )
    return group


def _jsonable(d):
    return {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in d.items()}


@transaction.atomic
def close_group(actor, group):
    group.status = Group.Status.CLOSED
    group.save(update_fields=['status'])
    log_action(actor, action='group.close', entity_type='Group', entity_id=group.pk)
    return group


@transaction.atomic
def archive_group(actor, group):
    group.status = Group.Status.ARCHIVED
    group.save(update_fields=['status'])
    log_action(actor, action='group.archive', entity_type='Group', entity_id=group.pk)
    return group


@transaction.atomic
def reopen_group(actor, group):
    group.status = Group.Status.OPEN
    group.save(update_fields=['status'])
    log_action(actor, action='group.reopen', entity_type='Group', entity_id=group.pk)
    return group


@transaction.atomic
def delete_group(actor, group):
    if group.group_students.exists():
        raise ValidationError("A'zolari bor guruhni o'chirib bo'lmaydi, avval a'zolarini chiqaring yoki arxivlang")
    entity_id = group.pk
    log_action(actor, action='group.delete', entity_type='Group', entity_id=entity_id,
               old_value={'name': group.name})
    group.delete()


@transaction.atomic
def assign_teacher(actor, group, user):
    link, created = GroupTeacher.objects.get_or_create(group=group, user=user)
    if created:
        log_action(actor, action='group.assign_teacher', entity_type='Group', entity_id=group.pk,
                   new_value={'user_id': user.id})
    return link


@transaction.atomic
def remove_teacher(actor, group, user):
    deleted, _ = GroupTeacher.objects.filter(group=group, user=user).delete()
    if deleted:
        log_action(actor, action='group.remove_teacher', entity_type='Group', entity_id=group.pk,
                   old_value={'user_id': user.id})
    return deleted


@transaction.atomic
def assign_instructor(actor, group, user):
    link, created = GroupInstructor.objects.get_or_create(group=group, user=user)
    if created:
        log_action(actor, action='group.assign_instructor', entity_type='Group', entity_id=group.pk,
                   new_value={'user_id': user.id})
    return link


@transaction.atomic
def remove_instructor(actor, group, user):
    deleted, _ = GroupInstructor.objects.filter(group=group, user=user).delete()
    if deleted:
        log_action(actor, action='group.remove_instructor', entity_type='Group', entity_id=group.pk,
                   old_value={'user_id': user.id})
    return deleted


@transaction.atomic
def add_student_to_group(actor, group, student):
    if group.status != Group.Status.OPEN:
        raise ValidationError("Yopilgan yoki arxivlangan guruhga o'quvchi qo'shib bo'lmaydi")
    if group.is_full:
        raise ValidationError("Guruh to'lgan (max_students chegarasiga yetgan)")
    if GroupStudent.objects.filter(group=group, student=student, left_at__isnull=True).exists():
        raise ValidationError("O'quvchi allaqachon shu guruhda")

    membership = GroupStudent.objects.create(group=group, student=student)
    from apps.payments.models import Enrollment

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
    log_action(actor, action='group.add_student', entity_type='Group', entity_id=group.pk,
               new_value={'student_id': student.pk})
    return membership


@transaction.atomic
def remove_student_from_group(actor, group, student):
    membership = GroupStudent.objects.filter(group=group, student=student, left_at__isnull=True).first()
    if not membership:
        raise ValidationError("O'quvchi bu guruhda emas")
    membership.left_at = timezone.now()
    membership.save(update_fields=['left_at'])
    log_action(actor, action='group.remove_student', entity_type='Group', entity_id=group.pk,
               old_value={'student_id': student.pk})
    return membership


@transaction.atomic
def move_student(actor, student, from_group, to_group):
    remove_student_from_group(actor, from_group, student)
    membership = add_student_to_group(actor, to_group, student)
    log_action(
        actor, action='student.move', entity_type='Student', entity_id=student.pk,
        old_value={'group_id': from_group.pk}, new_value={'group_id': to_group.pk},
    )
    return membership
