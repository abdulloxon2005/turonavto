# Avtomaktab to'lov tizimi — Django backend + frontend

Asl texnik topshiriq FastAPI uchun yozilgan edi (`Avtomaktab to'lov tizimi backend uchun texnik
topshiriq.docx`). Loyiha **Django**da, bitta kod bazasida backend (business-logika, Guard/rol
tekshiruvi, audit) va frontend (server-rendered shablonlar + Bootstrap + HTMX) sifatida qurilmoqda.

## Texnologiyalar (FastAPI -> Django moslashtirish)

| Asl (FastAPI) | Django'da |
|---|---|
| FastAPI + Pydantic | Django 5 + Django Forms/Views |
| SQLAlchemy + Alembic | Django ORM + Django migratsiyalari |
| SQLite (WAL) | SQLite (WAL), keyin PostgreSQL'ga o'tishga tayyor |
| JWT (access+refresh) | Django session autentifikatsiyasi (telefon raqami orqali, custom `PhoneBackend`) |
| Parol: argon2/bcrypt | Argon2 (`PASSWORD_HASHERS`) |
| APScheduler | APScheduler (o'zgarishsiz, `apps/core/scheduler.py`) |
| OpenAPI/Swagger | Django shablonlari (API hozircha yo'q — pastga qarang) |
| WeasyPrint/ReportLab | ReportLab (Windows'da GTK talab qilmaydi) |
| Router -> Guard -> Service -> Repository | View (+ `core.mixins` Guard) -> `services.py` -> Django ORM (Repository) |

**Frontend**: foydalanuvchi bilan kelishilgan holda Django shablonlari + Bootstrap 5 + HTMX
tanlandi (alohida React/Vue emas). Sabab: bitta kod bazasi, Node.js/build jarayonisiz tezroq
yetkazish, kichik-o'rta avtomaktab uchun yetarli.

**REST API**: texnik topshiriqda keltirilgan `/api/v1/...` endpointlar ro'yxati (10-bo'lim)
Telegram bot va Click/Payme integratsiyasi uchun mo'ljallangan, ikkalasi ham "keyingi bosqich"
deb belgilangan. Shuning uchun hozircha alohida REST API qurilmayapti; `djangorestframework`
o'rnatilgan va modellar/service qatlami shu maqsadda qayta ishlatishga tayyor qilib yozilgan —
kerak bo'lganda ustiga DRF serializer/view qo'shish oson bo'ladi.

## Ishga tushirish (lokal, development)

```bash
cd D:\BMI\avtomaktab
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

`.env` fayli (`.env.example`dan nusxa) orqali `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `TIME_ZONE`,
`CENTER_NAME` sozlanadi. `DEBUG=True` bo'lsa statik fayllar manifestsiz, to'g'ridan-to'g'ri
xizmat qiladi (collectstatic shart emas); `DEBUG=False` da WhiteNoise'ning siqilgan/xeshlangan
storage'i ishlatiladi — avval `python manage.py collectstatic` bajarilishi kerak.

Birinchi admin allaqachon yaratilgan (1-bosqichda sinov uchun):
- Telefon: `+998900000000`
- Parol: `Admin12345`

Production uchun bu hisobni o'chirib, yangisini `python manage.py createsuperuser` bilan yarating.

## Testlar

```bash
pip install -r requirements-dev.txt
pytest                                   # barcha testlar
pytest --cov=apps --cov-report=term-missing   # qamrov hisoboti
```

Testlar `apps/*/tests.py` fayllarida, pytest-django + fixture'lar (`conftest.py`) asosida.
Asosiy e'tibor texnik topshiriqning 13-bo'lim qabul mezonlariga qaratilgan:

- **RBAC**: rol mos kelmasa 403, begona yozuvga murojaat 404 (`apps/students/tests.py`,
  `apps/core/tests.py`)
- **Qarz formulasi**: 10+ turli narx/chegirma/to'lov kombinatsiyasi parametrlangan testda
  (`test_debt_formula_scenarios`), bekor qilingan va qaytarilgan to'lovlar hisobga olinishi
- **Idempotentlik**: bir xil kalit bilan takroriy so'rov ikkinchi to'lov yaratmasligi
- **To'lov o'chirilmasligi**: faqat `cancelled` holatiga o'tishi, audit_log immutability
- **Kassa yopish**: farq bo'lsa izohsiz tasdiqlab bo'lmasligi, yopilgan kunda yangi to'lov
  kiritib bo'lmasligi
- **Fon vazifasi**: muddati o'tgan grafik qismlarini avtomatik belgilash

`apps/payments/services.py` (qarz/to'lov hisob-kitobi) va `apps/core/mixins.py` (RBAC Guard)
uchun qamrov **~83%** (talab: ≥80%, `pytest --cov=apps.payments.services --cov=apps.students.services --cov=apps.core.mixins --cov=apps.accounts.backends`).

## Bosqichlar (ish rejasi)

1. **Asos** ✅ — loyiha skeleti, `apps.accounts` (User, rollar, telefon orqali login, rate-limit,
   majburiy parol almashtirish), RBAC Guard (`apps.core.mixins`), audit_log (append-only),
   `apps.notifications` va `apps.site_settings` modellari, asosiy shablon (navbar, xabarlar),
   403/404/500 sahifalari, APScheduler skeleti.
2. **Guruh va o'quvchilar** ✅ — `apps.groups`, `apps.students`: guruhlar (CRUD, yopish/arxivlash),
   hodim/o'quvchi biriktirish (group_teachers/instructors/students, instructor_students),
   egalik qoidalari (`brought_by_user_id`, faqat egasi yoki admin tahrirlaydi — 403),
   ko'rinish RBAC bo'yicha cheklangan (admin: hammasi, o'qituvchi: o'z guruhlari, instruktor:
   biriktirilgan+olib kelgan — 404 begona yozuvga), dublikat telefon ogohlantirishi,
   o'chirish so'rovlari (`delete_requests`, to'lovi yo'q bo'lsa o'chiriladi, bo'lsa arxivlanadi).
3. **To'lovlar** ✅ — `apps.payments`: enrollments (kursga yozish, narx/chegirma),
   payment_schedule (bo'lib to'lash grafigi, eng eski muddatdan taqsimlash), to'lov kiritish
   (idempotency_key orqali takroriy bosishdan himoya, ortiqcha to'lov rad etiladi), chegirma
   (faqat admin, sabab majburiy), bekor qilish (to'lov o'chirilmaydi, faqat cancelled) va
   qaytarish (alohida manfiy summali yozuv), qarz avtomatik hisoblanadi
   (unpaid/partial/paid/overdue), PDF chek (ReportLab), qarzdorlar ro'yxati, fon vazifalari
   (`apps/payments/jobs.py`: muddati o'tganlarni belgilash, oldindan eslatma).
4. **Instruktor va kassa** ✅ — amaliyot darslari (`apps.lessons`: dars qo'shish, qatnashdi/
   qatnashmadi belgisi, jami soat), kassa yopish (`CashClosing`: tizim hisobi avtomatik
   hisoblanadi, farq bo'lsa admin izoh bilan tasdiqlaydi, yopilgan kunda yangi to'lov
   kiritilmaydi), T-4/I-4 shaxsiy statistika dashboardda (olib kelgan o'quvchilar, undirgan
   summa, qarz, o'tkazilgan soat).
5. **Hisobotlar va fon vazifalari** ✅ — `apps.reports`: tushum, guruhlar, hodimlar,
   qarzdorlar, kutilayotgan tushum, kassa hisobotlari (har biri filtrlanadi, Excel/PDF
   eksport qilinadi). Admin uchun "Tizim" bo'limi: faoliyat jurnali (filtrlanadigan),
   tizim sozlamalari (markaz nomi, to'lov usullari, eslatma kunlari), qo'lda zaxira nusxa
   olish/yuklab olish. Fon vazifalari (APScheduler) 1/3-bosqichda qo'shilgan edi — shu
   bosqichda ishga tushirilishi va bog'liqliklari tasdiqlandi.
6. **Sinov, xavfsizlik, joylashtirish** ✅ — pytest-django testlar (64 ta, qamrov ≥80%
   muhim qismlarda), `manage.py check --deploy` orqali xavfsizlik tekshiruvi, rasm yuklashda
   hajm cheklovi qo'shildi, Dockerfile + docker-compose + Nginx, to'liq hujjatlar.

Har bosqich tugagach loyiha ishga tushirilib, brauzerda sinovdan o'tkazildi.

## Docker bilan joylashtirish (production)

Loyiha papkasida `.env.production` fayli tayyorlab qo'yilgan (kuchli tasodifiy
`SECRET_KEY` bilan). Serverga ko'chirishdan oldin faqat `ALLOWED_HOSTS`ni server
IP (yoki domen)ingizga almashtiring:

```bash
# server ustida, loyiha papkasida:
nano .env.production   # ALLOWED_HOSTS=SIZNING_SERVER_IP_MANZILINGIZ ni to'g'rilang
cp .env.production .env

docker compose build
docker compose up -d

# Birinchi admin yaratish:
docker compose exec web python manage.py createsuperuser
```

Sayt `http://<server-ip>/` manzilida ishga tushadi (hozircha oddiy HTTP —
domen va TLS sertifikat hali yo'q). Keyinchalik domen va Let's Encrypt
sertifikat qo'shilganda:

1. `nginx.conf`ga 443-port va sertifikat (masalan `certbot`) qo'shiladi.
2. `.env`da `ALLOWED_HOSTS`ga domen qo'shiladi, `ENABLE_SSL=True` qilinadi
   (shundan keyin `SECURE_SSL_REDIRECT`, xavfsiz cookie'lar va HSTS yoqiladi —
   bu bayroq `DEBUG=False`dan ajratilgan, chunki TLS sozlanmagan holda uni
   yoqish cheksiz redirectga olib keladi).
3. `docker compose up -d --build` bilan qayta ishga tushiriladi.

- `web` — Gunicorn, **faqat 1 ta worker** (`--workers 1`): APScheduler fon vazifalari va
  SQLite'ning yagona yozuvchi cheklovi shuni talab qiladi. Ko'p worker/server kerak bo'lsa,
  avval PostgreSQL'ga o'tish va fon vazifalarini alohida jarayonga chiqarish kerak
  (12-bo'limdagi nofunksional talab: "100 dan oshsa PostgreSQL'ga o'tish tavsiya etiladi").
- `nginx` — 80-portda statik/media fayllarni va `/`ni `web`ga proksi qiladi.
- Ma'lumotlar (`db.sqlite3`, `media`, `backups`, `logs`, `staticfiles`) nomli Docker
  volume'larida saqlanadi — konteyner qayta qurilganda yo'qolmaydi.
- Kunlik zaxira nusxa fon vazifasi orqali avtomatik olinadi (`02:00`, oxirgi 30 nusxa);
  qo'lda ham olish/yuklab olish mumkin (admin panel → Zaxira).

## Xavfsizlik (12-bo'lim) — holat

| Talab | Holat |
|---|---|
| Parollar argon2 bilan xeshlanadi, kamida 8 belgi | ✅ |
| 5 xato urinishdan keyin 15 daqiqa blok | ✅ (`apps/accounts/backends.py`) |
| Faqat HTTPS (production) | ⚠️ Tayyor, lekin o'chirilgan — domen+TLS sertifikat sozlanmaguncha `ENABLE_SSL=False`; sozlangach `.env`da `ENABLE_SSL=True` qiling, shunda `SECURE_SSL_REDIRECT`/xavfsiz cookie/HSTS yoqiladi |
| Rol (Guard) va egalik tekshiruvi har bir view'da | ✅ (`apps/core/mixins.py` + har app'ning `services.py`) |
| Ruxsatsiz yozuvga 404 | ✅ |
| SQL injection himoyasi | ✅ — loyihada xom SQL yo'q, faqat Django ORM |
| Rasm: turi (jpg/png) va hajmi (≤5MB) tekshiriladi | ✅ (`apps/core/validators.py`, 6-bosqichda qo'shildi) |
| Shaxsiy ma'lumotlar (pasport/telefon) loglarga yozilmaydi | ✅ — strukturalangan logda faqat xabar matni, so'rov tanasi yozilmaydi |
| audit_log faqat qo'shiladi | ✅ (signal orqali bloklangan, test bilan tasdiqlangan) |
| Bloklangan hodim tokeni darhol bekor qilinadi | ✅ (`BlockedUserMiddleware`) |
| Zaxira nusxa shifrlangan va serverdan tashqarida | ⚠️ **Qisman** — kunlik avtomatik zaxira mavjud, lekin shifrlash va serverdan tashqariga nusxalash (masalan S3/boshqa server) hozircha amalga oshirilmagan; buning uchun production muhitida `backup_database()` natijasini tashqi saqlashga yuklash (masalan `rclone`/S3 SDK) qo'shish tavsiya etiladi. |
| `manage.py check --deploy` | ✅ toza (faqat `SECRET_KEY`ni production qiymatiga almashtirish va ixtiyoriy HSTS preload haqida eslatma qoladi) |

Deploy qilishdan oldin `.env`da albatta: `DEBUG=False`, uzun tasodifiy `SECRET_KEY`,
to'g'ri `ALLOWED_HOSTS` o'rnating.
