"""Demo ma'lumotlar: 3 o'qituvchi, 4 instruktor, 3 guruh (har birida 5 o'quvchi),
har bir o'quvchi uchun shartnoma (enrollment) va taxminiy to'lov.

Bir martalik ishga tushirish uchun mo'ljallangan: `python manage.py seed_demo`.
Agar "B2" nomli guruh allaqachon mavjud bo'lsa, qayta ishga tushirilmaydi (idempotent emas).
"""

import datetime
import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.accounts.services import create_staff
from apps.groups.models import Group
from apps.groups.services import assign_instructor as assign_group_instructor
from apps.groups.services import assign_teacher, create_group
from apps.payments.models import Payment
from apps.payments.services import create_enrollment, create_payment
from apps.students.services import assign_instructor, create_student

TEACHERS = [
    ('Shuhrat Yusupov', '+998901113001'),
    ('Nodira Tosheva', '+998901113002'),
    ('Jahongir Yoldashev', '+998901113003'),
]

INSTRUCTORS = [
    ('Bekzod Rashidov', '+998901113011'),
    ('Davron Mirzayev', '+998901113012'),
    ('Kamola Yusupova', '+998901113013'),
    ('Sardor Toshpulatov', '+998901113014'),
]

GROUPS = [
    {
        'name': 'B2', 'category': 'B', 'price': 3_500_000,
        'schedule': 'Dush/Chor/Juma 18:00', 'teacher_idx': 0, 'instructor_idxs': [0, 3],
        'students': [
            'Aziz Komilov', 'Dilnoza Rahimova', 'Sanjar Yusupov',
            'Madina Qodirova', 'Otabek Islomov',
        ],
    },
    {
        'name': 'B3', 'category': 'B', 'price': 3_500_000,
        'schedule': 'Sesh/Pay/Shan 10:00', 'teacher_idx': 1, 'instructor_idxs': [1],
        'students': [
            'Zarina Abdullayeva', 'Jasur Toshmatov', 'Kamila Nematova',
            'Farrux Saidov', "Gulnoza Ergasheva",
        ],
    },
    {
        'name': 'C1', 'category': 'C', 'price': 4_500_000,
        'schedule': 'Dush/Chor/Juma 15:00', 'teacher_idx': 2, 'instructor_idxs': [2],
        'students': [
            'Rustam Xoliqov', 'Shahnoza Murodova', "Ulug'bek Qosimov",
            'Nilufar Sattorova', 'Anvar Normatov',
        ],
    },
]

ADDRESSES = ['Andijon', 'Toshkent', "Farg'ona", 'Namangan', 'Samarqand']


class Command(BaseCommand):
    help = "Demo ma'lumotlar yaratadi: o'qituvchilar, instruktorlar, guruhlar, o'quvchilar va to'lovlar"

    @transaction.atomic
    def handle(self, *args, **options):
        if Group.objects.filter(name='B2').exists():
            raise CommandError('Demo ma\'lumotlar allaqachon yaratilgan ko\'rinadi ("B2" guruhi mavjud)')

        admin = User.objects.filter(role=User.Role.ADMIN, is_active=True).first()
        if admin is None:
            raise CommandError('Faol admin hisob topilmadi')

        self.stdout.write('--- Hodimlar yaratilmoqda ---')
        teacher_credentials = []
        teacher_users = []
        for full_name, phone in TEACHERS:
            user, temp_password = create_staff(admin, full_name=full_name, phone=phone, role=User.Role.TEACHER)
            teacher_users.append(user)
            teacher_credentials.append((phone, temp_password, full_name))

        instructor_credentials = []
        instructor_users = []
        for full_name, phone in INSTRUCTORS:
            user, temp_password = create_staff(admin, full_name=full_name, phone=phone, role=User.Role.INSTRUCTOR)
            instructor_users.append(user)
            instructor_credentials.append((phone, temp_password, full_name))

        self.stdout.write('--- Guruhlar yaratilmoqda ---')
        today = datetime.date.today()
        student_phone_counter = 0
        for g in GROUPS:
            group = create_group(
                admin,
                name=g['name'], category=g['category'], start_date=today,
                price=g['price'], max_students=25, schedule=g['schedule'],
            )
            teacher = teacher_users[g['teacher_idx']]
            assign_teacher(admin, group, teacher)
            group_instructors = [instructor_users[i] for i in g['instructor_idxs']]
            for instructor in group_instructors:
                assign_group_instructor(admin, group, instructor)
            primary_instructor = group_instructors[0]

            self.stdout.write(f"  {group.name}: o'qituvchi={teacher.full_name}, "
                               f"instruktor(lar)={', '.join(i.full_name for i in group_instructors)}")

            for student_name in g['students']:
                phone = f"+998901114{student_phone_counter:03d}"
                student_phone_counter += 1
                birth_year = random.randint(1998, 2007)
                birth_date = datetime.date(birth_year, random.randint(1, 12), random.randint(1, 28))
                student = create_student(
                    teacher, full_name=student_name, phone=phone,
                    birth_date=birth_date, address=random.choice(ADDRESSES),
                    group=group,
                )
                assign_instructor(admin, student, primary_instructor)

                enrollment = create_enrollment(admin, student=student, group=group, price=group.price)
                paid_ratio = random.choice([0.2, 0.3, 0.4, 0.5, 0.6, 1.0])
                paid_amount = round(group.price * paid_ratio / 50_000) * 50_000
                if paid_amount > 0:
                    create_payment(
                        admin, student=student, enrollment=enrollment, amount=paid_amount,
                        method=Payment.Method.CASH, note="Boshlang'ich to'lov (demo)",
                    )
                self.stdout.write(
                    f"    {student.full_name} ({phone}) - narx {group.price:,} so'm, "
                    f"to'langan {paid_amount:,} so'm".replace(',', ' ')
                )

        self.stdout.write(self.style.SUCCESS('\n--- Tayyor ---'))
        self.stdout.write("O'qituvchilar (telefon / vaqtinchalik parol):")
        for phone, pwd, name in teacher_credentials:
            self.stdout.write(f'  {name}: {phone} / {pwd}')
        self.stdout.write('Instruktorlar (telefon / vaqtinchalik parol):')
        for phone, pwd, name in instructor_credentials:
            self.stdout.write(f'  {name}: {phone} / {pwd}')
        self.stdout.write(
            '\nEslatma: barcha hodimlar birinchi kirishda parolni almashtirishi so\'raladi '
            '(must_change_password=True).'
        )
