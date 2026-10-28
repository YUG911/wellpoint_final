from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-gdwe02(a%o6-vhztg5zjwx&@r0nf&2ybd8sj^68)$(eusr=%8u',
)

# Vercel sets VERCEL=1 in the build and runtime environment. On Vercel we must
# default to DEBUG=False; locally (no Vercel, no MySQL) we keep DEBUG=True.
_ON_VERCEL = bool(os.environ.get('VERCEL'))
DEBUG = os.environ.get(
    'DJANGO_DEBUG',
    'False' if _ON_VERCEL else 'True',
).lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = [
    h for h in os.environ.get(
        'DJANGO_ALLOWED_HOSTS',
        'localhost,127.0.0.1,testserver,.vercel.app',
    ).split(',') if h
]

CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get(
        'DJANGO_CSRF_TRUSTED_ORIGINS',
        'https://wellpoint-tau.vercel.app,https://*.vercel.app,http://localhost:8000,http://127.0.0.1:8000',
    ).split(',') if o
]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'doctors',
    'appointments',
    'records',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'clinic_booking.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.current_user_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'clinic_booking.wsgi.application'

_DATABASE_URL = os.environ.get('DATABASE_URL')

# Aiven requires TLS, and PyMySQL only switches TLS on when the "ssl" dict is
# non-empty. An empty dict means plaintext, which Aiven refuses, so the
# certificate is what makes the connection work.
AIVEN_CA_CERT = BASE_DIR / 'certs' / 'aiven-ca.pem'


def _aiven_ssl_options():
    if AIVEN_CA_CERT.is_file():
        return {'ca': str(AIVEN_CA_CERT)}
    # Fallback: encrypt the traffic but skip certificate verification.
    return {'check_hostname': False, 'verify_mode': 0}


if os.environ.get('MYSQL_HOST'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_DATABASE', 'defaultdb'),
            'USER': os.environ.get('MYSQL_USER', 'avnadmin'),
            'PASSWORD': os.environ.get('MYSQL_PASSWORD', ''),
            'HOST': os.environ.get('MYSQL_HOST', ''),
            'PORT': os.environ.get('MYSQL_PORT', '3306'),
            'CONN_MAX_AGE': 0,
            'OPTIONS': {
                'charset': 'utf8mb4',
                'ssl': _aiven_ssl_options(),
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Authentication settings
LOGIN_URL = 'login'

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

# Production-only hardening (Vercel). Inactive while DEBUG is on, so local
# development over plain http keeps working.
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get('DJANGO_SECURE_SSL_REDIRECT', 'True').lower() in ('1', 'true', 'yes')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', '0'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = bool(SECURE_HSTS_SECONDS)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    X_FRAME_OPTIONS = 'DENY'
