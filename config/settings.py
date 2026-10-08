from pathlib import Path
import os
import dj_database_url

try:
    from . import credentials
except ImportError:
    credentials = None

BASE_DIR = Path(__file__).resolve().parent.parent

def load_local_env(path):
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_local_env(BASE_DIR / '.env')
SECRET_KEY = os.environ.get('SECRET_KEY', os.environ.get('DJANGO_SECRET_KEY', 'phonecase254-dev-key-change-me'))
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost,.onrender.com').split(',')

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'shop',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'shop' / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages', 'shop.context_processors.store_context',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'

if os.environ.get('DATABASE_URL'):
    DATABASES = {'default': dj_database_url.config(conn_max_age=600, conn_health_checks=True)}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'shop' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'
REQUIRE_EMAIL_CONFIRMATION = os.environ.get('REQUIRE_EMAIL_CONFIRMATION', 'False') == 'True'

EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST else 'django.core.mail.backends.console.EmailBackend',
)
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'phonecase254.shop@gmail.com')
ORDER_NOTIFICATION_EMAIL = os.environ.get('ORDER_NOTIFICATION_EMAIL', 'phonecase254.shop@gmail.com')
OWNER_PHONE_NUMBER = os.environ.get('OWNER_PHONE_NUMBER', '0727729400')

# Add your Daraja credentials and phone number when you are ready to connect payments.
MPESA_PAYBILL_NUMBER = os.environ.get('MPESA_PAYBILL_NUMBER', '174379')
MPESA_ENVIRONMENT = os.environ.get('MPESA_ENVIRONMENT', 'sandbox')
MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY', getattr(credentials, 'CONSUMER_KEY', ''))
MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET', getattr(credentials, 'CONSUMER_SECRET', ''))
MPESA_PASSKEY = os.environ.get('MPESA_PASSKEY', getattr(credentials, 'PASSKEY', ''))
MPESA_SHORT_CODE = os.environ.get('MPESA_SHORT_CODE', '174379')
MPESA_CALLBACK_URL = os.environ.get('MPESA_CALLBACK_URL') or getattr(credentials, 'CALLBACK_URL', '') or 'https://your-public-domain.example.com/mpesa/callback/'
MPESA_ACCOUNT_REFERENCE = os.environ.get('MPESA_ACCOUNT_REFERENCE', 'PHONECASE254')
MPESA_TRANSACTION_DESCRIPTION = os.environ.get('MPESA_TRANSACTION_DESCRIPTION', 'phoneCase254 order')

if not DEBUG:
    CSRF_TRUSTED_ORIGINS = [origin for origin in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if origin]
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
