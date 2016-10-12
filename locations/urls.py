from rest_framework.routers import DefaultRouter

from .views import ParishSearch

router = DefaultRouter()
router.register(r'parish', ParishSearch, 'locations')

urlpatterns = [
]
