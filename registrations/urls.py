from django.conf.urls import url
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r'user', views.UserViewSet)
router.register(r'group', views.GroupViewSet)
router.register(r'source', views.SourceViewSet)
router.register(r'webhook', views.HookViewSet)
router.register(r'registrations', views.RegistrationGetViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browseable API.
urlpatterns = [
    url(r'^api/v1/registration/', views.RegistrationPost.as_view()),
]
