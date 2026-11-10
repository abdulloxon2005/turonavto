from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.core.services import log_action
from apps.students.services import visible_students_queryset

from .models import Lesson, TheoryLesson, TheoryLessonAttendance


def visible_lessons_queryset(user):
    if user.is_admin():
        return Lesson.objects.all()
    if user.is_instructor():
        return Lesson.objects.filter(instructor=user)
    return Lesson.objects.none()


@transaction.atomic
def create_lesson(actor, *, student, lesson_date, start_time, hours):
    if not actor.is_admin() and student not in visible_students_queryset(actor):
        raise PermissionDenied("Bu o'quvchi uchun dars qo'sha olmaysiz")
    if hours <= 0:
        raise ValidationError("Soat noldan katta bo'lishi kerak")

    instructor = actor if actor.is_instructor() else student.instructor_links.first() and student.instructor_links.first().instructor
    if instructor is None:
        raise ValidationError(
            "Bu o'quvchiga hali instruktor biriktirilmagan. Avval o'quvchi sahifasida "
            "\"Instruktorlar\" bo'limidan instruktor biriktiring (guruhga biriktirilgan "
            "instruktor buni avtomatik hal qilmaydi)."
        )

    lesson = Lesson.objects.create(
        instructor=instructor, student=student, lesson_date=lesson_date,
        start_time=start_time, hours=hours,
    )
    log_action(
        actor, action='lesson.create', entity_type='Lesson', entity_id=lesson.pk,
        new_value={'student_id': student.pk, 'date': lesson_date.isoformat(), 'hours': str(hours)},
    )
    return lesson


@transaction.atomic
def mark_attendance(actor, lesson, attended):
    old_value = {'attended': lesson.attended}
    lesson.attended = attended
    lesson.save(update_fields=['attended'])
    log_action(
        actor, action='lesson.mark_attendance', entity_type='Lesson', entity_id=lesson.pk,
        old_value=old_value, new_value={'attended': attended},
    )
    return lesson


def total_hours_for_student(student):
    total = student.lessons.filter(attended=True).aggregate(s=Sum('hours'))['s']
    return total or 0


def total_hours_for_instructor(instructor, since=None, until=None):
    qs = Lesson.objects.filter(instructor=instructor, attended=True)
    if since:
        qs = qs.filter(lesson_date__gte=since)
    if until:
        qs = qs.filter(lesson_date__lte=until)
    return qs.aggregate(s=Sum('hours'))['s'] or 0


def visible_theory_lessons_queryset(user):
    if user.is_admin():
        return TheoryLesson.objects.all()
    if user.is_teacher():
        return TheoryLesson.objects.filter(teacher=user)
    return TheoryLesson.objects.none()


@transaction.atomic
def create_theory_lesson(actor, *, group, teacher, topic, lesson_date, start_time, hours):
    if hours <= 0:
        raise ValidationError("Soat noldan katta bo'lishi kerak")

    lesson = TheoryLesson.objects.create(
        group=group, teacher=teacher, topic=topic,
        lesson_date=lesson_date, start_time=start_time, hours=hours,
    )

    students = [
        m.student for m in group.group_students.filter(left_at__isnull=True).select_related('student')
    ]
    TheoryLessonAttendance.objects.bulk_create([
        TheoryLessonAttendance(theory_lesson=lesson, student=student) for student in students
    ])

    log_action(
        actor, action='theory_lesson.create', entity_type='TheoryLesson', entity_id=lesson.pk,
        new_value={'group_id': group.pk, 'teacher_id': teacher.pk, 'date': lesson_date.isoformat(), 'hours': str(hours)},
    )
    return lesson


@transaction.atomic
def mark_theory_attendance(actor, attendance, attended):
    old_value = {'attended': attendance.attended}
    attendance.attended = attended
    attendance.save(update_fields=['attended'])
    log_action(
        actor, action='theory_lesson.mark_attendance', entity_type='TheoryLessonAttendance', entity_id=attendance.pk,
        old_value=old_value, new_value={'attended': attended},
    )
    return attendance
