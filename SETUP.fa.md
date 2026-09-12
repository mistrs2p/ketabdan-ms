# Ketabdaneh — راه‌اندازی کامل پروژه به‌صورت لوکال

[English](SETUP.md) | فارسی

راهنمای قدم‌به‌قدم برای بالا آوردن کل سیستم روی سیستم لوکال (ویندوز / PowerShell؛ در macOS/Linux همین مراحل با `source .venv/bin/activate` به‌جای فعال‌سازی ویندوزی اعمال می‌شود).

---

## ۰) معماری پروژه در یک نگاه

```text
Next.js + TypeScript (فرانت‌اند, apps/web, پورت 3000)
        ↓ (HTTP / JSON + Bearer token)
FastAPI (بک‌اند, apps/api, پورت 8000)
        ↓
PostgreSQL (دیتابیس, پورت 5433 — داخل Docker)
Redis (صف نوتیفیکیشن‌ها, پورت 6390 — داخل Docker)
```

سه سرویس اصلی باید اجرا بشن: **Docker (دیتابیس و Redis)**، **API**، **Web**.
Worker نوتیفیکیشن اختیاریه (فقط برای ارسال واقعی پیام به Bale/Telegram).

---

## ۱) پیش‌نیازها

| ابزار | نسخه | برای |
| --- | --- | --- |
| [Node.js](https://nodejs.org) + npm | ≥ 20 | فرانت‌اند |
| [Python](https://www.python.org) | ≥ 3.12 | بک‌اند |
| Docker + Docker Compose | — | PostgreSQL و Redis |
| Git | — | مدیریت نسخه |

چک کردن نصب بودن:

```powershell
node --version
python --version
docker --version
```

---

## ۲) دانلود و فایل‌های Environment

```powershell
git clone <repo-url>
cd ketabdaneh
```

سه فایل env لازمه — از روی فایل‌های example کپی کن:

```powershell
# 1) ریشه پروژه (مقدارهای Docker Compose)
Copy-Item .env.example .env

# 2) بک‌اند
Copy-Item apps\api\.env.example apps\api\.env

# 3) فرانت‌اند
Copy-Item apps\web\.env.example apps\web\.env
```

مقدارهای پیش‌فرض برای توسعه‌ی لوکال کافی هستن و به هم می‌خورن. مهم‌ترین‌ها:

| فایل | متغیر | مقدار پیش‌فرض | توضیح |
| --- | --- | --- | --- |
| ریشه `.env` | `POSTGRES_PORT` | `5433` | پورت دیتابیس روی سیستم تو |
| `apps/api/.env` | `DATABASE_URL` | `postgresql+psycopg://ketabdaneh:ketabdaneh_dev@localhost:5433/ketabdaneh` | باید با بالا هم‌خوان باشه |
| `apps/api/.env` | `REDIS_URL` | `redis://localhost:6390/0` | برای worker نوتیفیکیشن |
| `apps/api/.env` | `AUTH_SECRET_KEY` | placeholder | فقط برای dev؛ در production حتماً عوض بشه |
| `apps/api/.env` | `CORS_ALLOW_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | originهای مجاز مرورگر |
| `apps/web/.env` | `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | آدرس بک‌اند |

> ⚠️ **چرا پورت 5433 و نه 5432؟** ممکنه PostgreSQL ویندوزی از قبل روی 5432 باشه
> و اتصال‌ها رو قاپ بزنه. همین‌طور Redis روی 6390 و نه 6379.
>
> ⚠️ فایل‌های `.env` واقعی هرگز commit نمی‌شن (فقط `*.example` ها تحت tracked هستن).

---

## ۳) دیتابیس و Redis (Docker)

از **ریشه‌ی پروژه**:

```powershell
docker compose up -d
```

این دو سرویس رو با healthcheck بالا میاره:

- PostgreSQL → `localhost:5433` (یوزر/پسورد/دیتابیس از `.env` ریشه)
- Redis → `localhost:6390`

بررسی سالم بودن:

```powershell
docker ps          # هر دو باید "healthy" باشند
docker compose ps
```

دستورات مدیریتی:

```powershell
docker compose down              # خاموش کردن (دیتا در volume می‌ماند)
docker compose down -v           # خاموش + پاک کردن کل داده‌ها (!خطرناک)
docker compose logs -f postgres  # لاگ دیتابیس
```

> داده‌های PostgreSQL در volume با نام `postgres_data` می‌مونن و با ری‌استارت
> ویندوز یا Docker از بین نمی‌رن.

---

## ۴) بک‌اند (FastAPI)

### ۴-۱) نصب (فقط بار اول)

```powershell
cd apps\api
python -m venv .venv
.venv\Scripts\Activate.ps1        # فعال‌سازی venv
pip install -e .
pip install "pytest>=8.0" "httpx>=0.27"   # وابستگی‌های dev/test
```

> اگه PowerShell اجازه‌ی اجرای اسکریپت رو نداد:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### ۴-۲) مایگریشن‌های دیتابیس (بار اول + بعد از هر pull)

```powershell
# داخل apps\api با venv فعال و Docker بالا
alembic upgrade head
```

این دستور همه‌ی جدول‌ها (persons، events، roles، users، …) و داده‌های seed
(۶ نقش سازمانی، ۶ مسئولیت رویداد، نقش‌ها/مجوزهای RBAC) رو می‌سازه.

```powershell
alembic check      # بررسی هم‌خوانی دیتابیس با مدل‌ها (نباید اختلافی گزارش کند)
```

> ⚠️ **اگه این مرحله رو انجام ندی، جدول‌ها اصلاً ساخته نمی‌شن** و همه‌ی
> endpointهای دیتابیس‌دار (حتی لاگین) خطای 500 می‌دن. بعد از هر `git pull`
> هم عادت کن `alembic upgrade head` بزنی.

### ۴-۳) ساخت اولین کاربر (بار اول)

ثبت‌نام عمومی وجود نداره؛ کاربر فقط با این CLI ساخته می‌شه:

```powershell
python -m app.create_user admin --role admin
```

رمز رو **تعاملی** دو بار ازت می‌پرسه (پس باید توی ترمینال خودت اجرا بشه، نه
با پایپ یا در حالت non-interactive).

نقش‌های ممکن: `admin` (همه‌ی مجوزها)، `manager`، `operator` (بدون `people:create`).
کاربر بدون نقش می‌تونه لاگین کنه ولی همه‌ی مسیرهای کاری براش 403 می‌ده.

دستور مرتبط:

```powershell
python -m app.assign_role <username> <role_code>   # دادن نقش به کاربر موجود
```

### ۴-۴) اجرای سرور API

```powershell
uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
```

از این به بعد:

| آدرس | چی هست |
| --- | --- |
| <http://localhost:8000/api/health> | لایونس — `{"status": "ok"}` |
| <http://localhost:8000/api/health/ready> | ردینس — وضعیت دیتابیس/Redis/worker |
| <http://localhost:8000/docs> | **Swagger UI** — تست تعاملی API |
| <http://localhost:8000/redoc> | مستندات ReDoc |
| <http://localhost:8000/metrics> | متریک‌های Prometheus (داخلی) |

**استفاده از Swagger UI:** اول `POST /api/auth/login` رو با یوزر/پسوردت اجرا کن،
`access_token` رو کپی کن، بالای صفحه **Authorize** رو بزن و توکن رو پیست کن —
حالا همه‌ی endpointهای محافظت‌شده با `Authorization: Bearer <token>` اجرا می‌شن.

> نکته: `--host 0.0.0.0` تضمین می‌کنه اگه مرورگر `localhost` رو به IPv6 حل کنه هم
> API در دسترس باشه. اگه سرور رو فقط روی 127.0.0.1 بایند کنی و در فرانت پیام
> «service is unreachable» دیدی، با همین فلگ ری‌استارت کن.

---

## ۵) فرانت‌اند (Next.js)

در یک **ترمینال جدا**:

```powershell
cd apps\web
npm install        # فقط بار اول
npm run dev
```

سایت: <http://localhost:3000> — صفحه‌ی لاگین در `/fa/login` (فارسی) یا `/en/login`.

ورود با همان کاربری که در مرحله‌ی ۴-۳ ساختی.

---

## ۶) Worker نوتیفیکیشن‌ها (اختیاری)

فقط وقتی لازمه که ارسال پیام واقعی به Bale/Telegram تست بشه:

```powershell
# داخل apps\api با venv فعال
python -m app.worker
```

پیش‌نیاز: Redis بالا (مرحله‌ی ۳) + توکن بات در `apps/api/.env`:

```text
TELEGRAM_BOT_TOKEN=...
BALE_BOT_TOKEN=...
```

بدون این سرویس، بقیه‌ی سیستم کامل کار می‌کنه (وضعیت worker در
`/api/health/ready` فقط informational هست).

---

## ۷) اجرای تست‌ها

```powershell
# بک‌اند — از apps\api (نیازی به PostgreSQL نیست؛ SQLite در حافظه)
python -m pytest

# فرانت‌اند — از apps\web
npm test

# لینت فرانت‌اند
npm run lint
```

---

## ۸) روتین روزانه (وقتی همه‌چیز یک‌بار نصب شده)

سه ترمینال باز کن:

```powershell
# ترمینال ۱ — زیرساخت (فقط اگر ری‌استارت شده باشه لازم است)
docker compose up -d

# ترمینال ۲ — API
cd apps\api
.venv\Scripts\Activate.ps1
# اگر pull جدیدی آمده: alembic upgrade head
uvicorn app.main:app --reload --port 8000 --host 0.0.0.0

# ترمینال ۳ — وب
cd apps\web
npm run dev
```

بعد از هر `git pull`:

```powershell
cd apps\api ; .venv\Scripts\Activate.ps1 ; alembic upgrade head
```

---

## ۹) عیب‌یابی سریع

| نشانه | علت احتمالی | راه‌حل |
| --- | --- | --- |
| جدول‌ها خالی‌ان / لاگین خطای 500 می‌دهد | مایگریشن اجرا نشده | `alembic upgrade head` (§۴-۲) |
| «The service is unreachable» در فرم لاگین | مرورگر به API نرسیده | API روشنه؟ پورت 8000؟ در `.env` وب درسته؟ با `--host 0.0.0.0` ری‌استارت کن |
| «Invalid username or password» | کاربر نیست یا رمز غلطه | §۴-۳ کاربر بساز (پیام برای هر سه حالت عمداً یکسانه) |
| بعد از لاگین همه‌چیز 403 | کاربر نقش ندارد | `python -m app.assign_role <user> admin` |
| اتصال دیتابیس رد می‌شه | PostgreSQL ویندوزی روی 5432 نشسته / کانتینر خاموش | `docker compose ps`؛ از پورت 5433 استفاده کن |
| خطای AUTH_SECRET_KEY در اجرا | placeholder بدون اجازه‌ی dev | در dev مقدار `AUTH_ALLOW_INSECURE_DEV_SECRET=1` بذار |
| `alembic` شناخته نمی‌شه | venv فعال نیست | `.venv\Scripts\Activate.ps1` |

---

## ۱۰) اشاره: اجرای استک کامل Production (شبیه‌سازی لوکال)

برای شبیه‌سازی کامل تولید (Caddy + تمام سرویس‌ها با credentialهای فیک) —
مستندات کامل: [docs/12-DEPLOYMENT.md](docs/12-DEPLOYMENT.md)

```powershell
# از ریشه پروژه
Copy-Item .env.prod.example .env.prod    # مقادیر پیش‌فرض = حالت شبیه‌سازی
scripts\deploy.sh --skip-pull
```

برای توسعه‌ی روزانه این بخش لازم نیست.
