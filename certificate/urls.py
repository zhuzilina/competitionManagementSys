from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CertificateViewSet

router = DefaultRouter()
router.register(r'infos', CertificateViewSet) # 接口路径：/api/certificate/infos/

urlpatterns = [
    path('', include(router.urls)),
]