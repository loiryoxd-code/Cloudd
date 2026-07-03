import os
from pathlib import Path
import dotenv

# Initialize environment variables
BASE_DIR = Path(__file__).resolve().parent.parent

# Read .env file if it exists
dotenv.load_dotenv(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')

allowed_hosts_env = os.getenv('ALLOWED_HOSTS')
if allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]
else:
    ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'storages',
    'axes',
    
    # Local Apps
    'core.apps.CoreConfig',
    'documents.apps.DocumentsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Rate limiter / Authentication failures (OWASP A07:2021)
    'axes.middleware.AxesMiddleware',
    # Custom Security Headers Middleware (OWASP Top 10 Control Panel)
    'core.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'securedocs.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.global_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'securedocs.wsgi.application'

# Database Configuration (OCI Autonomous Database / SQLite Fallback)
# If OCI environment variables are present, connect to Oracle, else fall back to local SQLite.
oci_db_name = os.getenv('OCI_DB_NAME') or os.getenv('OCI_DSN')
oci_db_user = os.getenv('OCI_DB_USER') or os.getenv('OCI_USER')
oci_db_password = os.getenv('OCI_DB_PASSWORD') or os.getenv('OCI_PASSWORD')
oci_wallet_dir = os.getenv('OCI_WALLET_DIR') or os.getenv('TNS_ADMIN') or os.getenv('WALLET_LOCATION')
oci_wallet_password = os.getenv('OCI_WALLET_PASSWORD') or os.getenv('WALLET_PASSWORD')

if oci_db_name and oci_db_user and oci_db_password:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.oracle',
            'NAME': oci_db_name,
            'USER': oci_db_user,
            'PASSWORD': oci_db_password,
            'OPTIONS': {
                'config_dir': oci_wallet_dir,
                'wallet_location': oci_wallet_dir,
                'wallet_password': oci_wallet_password,
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }

# Password validation (OWASP A07:2021 mitigation)
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 10,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    # AxesBackend should be first to capture login attempts
    'axes.backends.AxesBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Internationalization
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

# Static files directories
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Storage Configuration (Azure Blob Storage with local fallback)
# Enables seamless hybrid deployments with Django 4.2+ STORAGES setting
AZURE_ACCOUNT_NAME = os.getenv('AZURE_ACCOUNT_NAME')
AZURE_ACCOUNT_KEY = os.getenv('AZURE_ACCOUNT_KEY')
AZURE_CONTAINER_MEDIA = os.getenv('AZURE_CONTAINER_MEDIA')
AZURE_CONTAINER_STATIC = os.getenv('AZURE_CONTAINER_STATIC')

if AZURE_ACCOUNT_NAME and AZURE_ACCOUNT_KEY and AZURE_CONTAINER_MEDIA and AZURE_CONTAINER_STATIC:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.azure_storage.AzureStorage",
            "OPTIONS": {
                "account_name": AZURE_ACCOUNT_NAME,
                "account_key": AZURE_ACCOUNT_KEY,
                "azure_container": AZURE_CONTAINER_MEDIA,
            },
        },
        "staticfiles": {
            "BACKEND": "storages.backends.azure_storage.AzureStorage",
            "OPTIONS": {
                "account_name": AZURE_ACCOUNT_NAME,
                "account_key": AZURE_ACCOUNT_KEY,
                "azure_container": AZURE_CONTAINER_STATIC,
            },
        },
    }
    AZURE_SSL = True
    AZURE_OVERWRITE_FILES = False
    STATIC_URL = f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_STATIC}/"
    MEDIA_URL = f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_MEDIA}/"
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    STATIC_URL = 'static/'
    MEDIA_URL = '/media/'

# Define roots for fallback and local file handling
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Authentication urls configuration
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'landing'

# OWASP Security Toggles and environment details (configured for HTTP first)
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1', 't')
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 't')
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'False').lower() in ('true', '1', 't')
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_REFERRER_POLICY = "same-origin"

# CSRF Settings
csrf_origins_env = os.getenv('CSRF_TRUSTED_ORIGINS')
if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins_env.split(',') if origin.strip()]
else:
    CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:8000', 'http://localhost:8000']

# Rate Limiting (Axes) (OWASP A07:2021)
AXES_ENABLED = os.getenv('AXES_ENABLED', 'True').lower() in ('true', '1', 't')
AXES_FAILURE_LIMIT = 5  # Lock out user after 5 failed attempts
AXES_COOLOFF_TIME = 10  # Wait 10 minutes before cooldown
AXES_LOCKOUT_TEMPLATE = 'lockout.html'
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']
AXES_RESET_ON_SUCCESS = True

# Cryptographic Keys (OWASP A02:2021)
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '3r0vPzI9G2hK5-aXmR8oD7fC9uV1wY4zL2xJ7hG4bQ0=')

# Django Default Auto Field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging & Monitoring (OWASP A09:2021)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'security_warnings.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'securedocs.security': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
