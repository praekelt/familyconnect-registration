from django.conf.urls import url
from rest_framework import routers
from . import views

router = routers.DefaultRouter()

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browseable API.
urlpatterns = [
    url(r'^api/v1/change/', views.ChangePost.as_view()),
]
