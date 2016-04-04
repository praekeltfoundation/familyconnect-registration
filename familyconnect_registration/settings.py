"""
Django settings for familyconnect_registration project.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.9/ref/settings/
"""

from kombu import Exchange, Queue

import os
import djcelery
import dj_database_url

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.9/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'REPLACEME')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', False)

TEMPLATE_DEBUG = DEBUG

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = (
    # admin
    'django.contrib.admin',
    # core
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 3rd party
    'djcelery',
    'raven.contrib.django.raven_compat',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'rest_hooks',
    # us
    'registrations',
    'changes'

)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'familyconnect_registration.urls'

WSGI_APPLICATION = 'familyconnect_registration.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get(
            'REGISTRATIONS_DATABASE',
            'postgres://postgres:@localhost/familyconnect_registration')),
}


# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'en-gb'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
)

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# TEMPLATE_CONTEXT_PROCESSORS = (
#     "django.core.context_processors.request",
# )

# Sentry configuration
RAVEN_CONFIG = {
    # DevOps will supply you with this.
    'dsn': os.environ.get('REGISTRATIONS_SENTRY_DSN', None),
}

# REST Framework conf defaults
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAdminUser',),
    'PAGE_SIZE': 1000,
    'DEFAULT_PAGINATION_CLASS':
        'rest_framework.pagination.LimitOffsetPagination',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': ('rest_framework.filters.DjangoFilterBackend',)
}

# Webhook event definition
HOOK_EVENTS = {
    # 'any.event.name': 'App.Model.Action' (created/updated/deleted)
    'subscriptionrequest.added': 'registrations.SubscriptionRequest.created+'
}

HOOK_DELIVERER = 'registrations.tasks.deliver_hook_wrapper'

HOOK_AUTH_TOKEN = os.environ.get('HOOK_AUTH_TOKEN', 'REPLACEME')

# Celery configuration options
CELERY_RESULT_BACKEND = 'djcelery.backends.database:DatabaseBackend'
CELERYBEAT_SCHEDULER = 'djcelery.schedulers.DatabaseScheduler'

BROKER_URL = os.environ.get('RABBITMQ_URL', 'redis://localhost:6379/0')

CELERY_DEFAULT_QUEUE = 'familyconnect_registration'
CELERY_QUEUES = (
    Queue('familyconnect_registration',
          Exchange('familyconnect_registration'),
          routing_key='familyconnect_registration'),
)

CELERY_ALWAYS_EAGER = False

# Tell Celery where to find the tasks
CELERY_IMPORTS = (
    'registrations.tasks',
    'changes.tasks'
)

CELERY_CREATE_MISSING_QUEUES = True
CELERY_ROUTES = {
    'celery.backend_cleanup': {
        'queue': 'mediumpriority',
    },
    'registrations.tasks.validate_registration': {
        'queue': 'priority',
    },
    'changes.tasks.implement_action': {
        'queue': 'priority',
    },
    'registrations.tasks.deliver_hook_wrapper': {
        'queue': 'priority',
    },
}

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']

djcelery.setup_loader()

PREBIRTH_MIN_WEEKS = int(os.environ.get('PREBIRTH_MIN_WEEKS', '4'))

STAGE_BASED_MESSAGING_URL = os.environ.get('STAGE_BASED_MESSAGING_URL',
                                           'http://localhost:8005/api/v1')
STAGE_BASED_MESSAGING_TOKEN = os.environ.get('STAGE_BASED_MESSAGING_TOKEN',
                                             'REPLACEME')
IDENTITY_STORE_URL = os.environ.get('IDENTITY_STORE_URL',
                                    'http://localhost:8001/api/v1')
IDENTITY_STORE_TOKEN = os.environ.get('IDENTITY_STORE_TOKEN',
                                      'REPLACEME')
MESSAGE_SENDER_URL = os.environ.get('MESSAGE_SENDER_URL',
                                    'http://localhost:8006/api/v1')
MESSAGE_SENDER_TOKEN = os.environ.get('MESSAGE_SENDER_TOKEN',
                                      'REPLACEME')
MOTHER_HW_WELCOME_TEXT_UG_ENG = os.environ.get(
    'MOTHER_HW_WELCOME_TEXT_UG_ENG', "Welcome to FamilyConnect, [mother_first_name]. Your FamilyConnect ID is [health_id]. Write it down and give it to the Nurse at your next clinic visit.")  # noqa
MOTHER_PUBLIC_WELCOME_TEXT_UG_ENG = os.environ.get(
    'MOTHER_PUBLIC_WELCOME_TEXT_UG_ENG', "Welcome to FamilyConnect, [mother_first_name]. Your FamilyConnect ID is [health_id]. Write it down and give it to the Nurse at your next clinic visit.")  # noqa
HOUSEHOLD_HW_WELCOME_TEXT_UG_ENG = os.environ.get(
    'HOUSEHOLD_HW_WELCOME_TEXT_UG_ENG', "Welcome to FamilyConnect. Your FamilyConnect ID is [health_id]. Write it down and give it to the Nurse at your next clinic visit.")  # noqa
HOUSEHOLD_PUBLIC_WELCOME_TEXT_UG_ENG = os.environ.get(
    'HOUSEHOLD_PUBLIC_WELCOME_TEXT_UG_ENG', "Welcome to FamilyConnect. The FamilyConnect ID for this woman is [health_id]. Write it down and give it to the Nurse at the next clinic visit.")  # noqa
