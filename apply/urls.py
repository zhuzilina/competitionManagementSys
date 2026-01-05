from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AwardApplyViewSet, AwardApproveViewSet

router = DefaultRouter()

# 普通用户申请接口: /api/award-apply/
router.register(r'award-apply', AwardApplyViewSet, basename='award-apply')

# 管理员审批接口: /api/award-approve/
router.register(r'award-approve', AwardApproveViewSet, basename='award-approve')

urlpatterns = [
    path('', include(router.urls)),
]