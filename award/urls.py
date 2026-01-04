from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AwardViewSet, AwardReportView, AwardStatisticsView

router = DefaultRouter()
router.register(r'infos', AwardViewSet) # 接口路径：/api/certificate/infos/

urlpatterns = [
    path('', include(router.urls)),
    path('report/', AwardReportView.as_view(), name='report'),
    path('statistics/', AwardStatisticsView.as_view(), name='statistics'),
]