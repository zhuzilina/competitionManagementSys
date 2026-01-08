from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TeamViewSet  # 确保导入路径正确

# 1. 初始化路由器
router = DefaultRouter()

# 2. 注册视图集
# base_name 会作为 URL 名称的前缀，默认取 queryset 模型的名称
router.register(r'info', TeamViewSet, basename='team')

# 3. 包含路由器生成的 URL
urlpatterns = [
    path('', include(router.urls)),
]