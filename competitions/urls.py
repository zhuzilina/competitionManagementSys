from django.urls import path, include
from rest_framework import routers
from .views import CompetitionViewSet, CompetitionLevelViewSet, CompetitionCategoryViewSet, CompetitionEventViewSet

router = routers.DefaultRouter()
router.register('info', CompetitionViewSet)
router.register(r'levels', CompetitionLevelViewSet)
router.register(r'categories', CompetitionCategoryViewSet)
router.register(r'events', CompetitionEventViewSet, basename='competition-event')

urlpatterns = [
    path('', include(router.urls)),
]