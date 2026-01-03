from django.urls import path, include
from rest_framework import routers
from .views import CompetitionViewSet, CompetitionLevelViewSet, CompetitionCategoryViewSet

router = routers.DefaultRouter()
router.register('info', CompetitionViewSet)
router.register(r'levels', CompetitionLevelViewSet)
router.register(r'categories', CompetitionCategoryViewSet)

urlpatterns = [
    path('', include(router.urls)),
]