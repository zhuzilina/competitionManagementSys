from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet  # 确保导入正确

# 1. 初始化 Router
router = DefaultRouter()

# 2. 注册 ViewSet
# 这里的 'notifications' 决定了 URL 的前缀
router.register(r'info', NotificationViewSet, basename='notification')

# 3. 将 router.urls 加入到 urlpatterns
urlpatterns = [
    path('', include(router.urls)),
]