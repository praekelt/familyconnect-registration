import os
from django.conf.urls import include, url
from django.contrib import admin
import rest_framework.authtoken.views
from rest_framework.routers import DefaultRouter
from registrations import urls as registration_urls
from changes import urls as changes_urls
from uniqueids import urls as uniqueids_urls
from locations import urls as locations_urls
from registrations import views

admin.site.site_header = os.environ.get('REGISTRATIONS_TITLE',
                                        'FamilyConnect Registration Admin')


class ContainerRouter(DefaultRouter):
    def register_router(self, router):
        self.registry.extend(router.registry)

router = ContainerRouter()
router.register_router(registration_urls.router)
router.register_router(changes_urls.router)
router.register_router(uniqueids_urls.router)
router.register_router(locations_urls.router)

urlpatterns = [
    url(r'^admin/',  include(admin.site.urls)),
    url(r'^api/auth/',
        include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api/token-auth/', rest_framework.authtoken.views.obtain_auth_token),
    url(r'^api/metrics/', views.MetricsView.as_view()),
    url(r'^', include('registrations.urls')),
    url(r'^', include('changes.urls')),
    url(r'^', include('uniqueids.urls')),
    url(r'^', include('locations.urls')),
    url(r'^api/v1/', include(router.urls)),
]
