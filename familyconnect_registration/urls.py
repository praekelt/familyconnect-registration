import os
from django.conf.urls import patterns, include, url
from django.contrib import admin

admin.site.site_header = os.environ.get('REGISTRATIONS_TITLE',
                                        'FamilyConnect Registration Admin')


urlpatterns = patterns(
    '',
    url(r'^admin/',  include(admin.site.urls)),
    url(r'^api/auth/',
        include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api/token-auth/',
        'rest_framework.authtoken.views.obtain_auth_token'),
    url(r'^', include('registrations.urls')),
    url(r'^', include('changes.urls')),
)
