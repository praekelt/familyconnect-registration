FROM praekeltfoundation/django-bootstrap
ENV DJANGO_SETTINGS_MODULE "familyconnect_registration.settings"
RUN ./manage.py collectstatic --noinput
ENV APP_MODULE "familyconnect_registration.wsgi:application"
