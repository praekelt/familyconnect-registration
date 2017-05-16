FROM praekeltfoundation/django-bootstrap:py2

COPY . /app
RUN pip install -e .

ENV DJANGO_SETTINGS_MODULE "familyconnect_registration.settings"
RUN ./manage.py collectstatic --noinput
CMD ["familyconnect_registration.wsgi:application"]
