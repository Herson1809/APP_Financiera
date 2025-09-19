from .base import *
INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # <-- AGREGA ESTA:
    'django.contrib.humanize',

    # Terceros
    'rest_framework',

    # Apps del proyecto
    'apps.core',
    'apps.policy',
]

