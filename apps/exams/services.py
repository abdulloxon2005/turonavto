from apps.core.services import log_action
from apps.students.models import Student
from apps.students.services import student_enriched_info

from .models import ExamAttempt


def record_exam_attempt(actor, *, student, exam_type, exam_date, passed, note=''):
    attempt = ExamAttempt.objects.create(
        student=student,
        exam_type=exam_type,
        exam_date=exam_date,
        passed=passed,
        recorded_by=actor,
        note=note,
    )
    log_action(
        actor, action='exam.record', entity_type='ExamAttempt', entity_id=attempt.pk,
        new_value={'student_id': student.pk, 'exam_type': exam_type, 'exam_date': exam_date.isoformat(), 'passed': passed},
    )
    return attempt


def delete_exam_attempt(actor, attempt):
    entity_id = attempt.pk
    log_action(
        actor, action='exam.delete', entity_type='ExamAttempt', entity_id=entity_id,
        old_value={'student_id': attempt.student_id, 'exam_type': attempt.exam_type, 'passed': attempt.passed},
    )
    attempt.delete()


def exam_summary_for_student(student):
    """Bir o'quvchining nazariy/amaliy imtihonlar bo'yicha urinishlari xulosasi."""
    attempts = list(student.exam_attempts.order_by('exam_date'))
    summary = {}
    for exam_type, label in ExamAttempt.ExamType.choices:
        type_attempts = [a for a in attempts if a.exam_type == exam_type]
        passed_attempt = next((a for a in type_attempts if a.passed), None)
        summary[exam_type] = {
            'label': label,
            'attempts': type_attempts,
            'attempts_count': len(type_attempts),
            'passed': passed_attempt is not None,
            'passed_on_attempt': (type_attempts.index(passed_attempt) + 1) if passed_attempt else None,
        }
    return summary


def graduated_students_with_exam_summary():
    """Kurs muddati tugagan (bitirgan) o'quvchilar va ularning imtihon urinishlari xulosasi."""
    students = Student.objects.exclude(status=Student.Status.EXPELLED).select_related('brought_by_user_id')
    rows = []
    for student in students:
        info = student_enriched_info(student)
        if info['learning_status'] != 'finished':
            continue
        rows.append({
            'student': student,
            'group': info['group'],
            'exam_summary': exam_summary_for_student(student),
        })
    return rows
