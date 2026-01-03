from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, filters
from .models import Profile
from .serializers import ProfileSerializer
from userManage.permissions import IsAdmin, IsCompAdmin


class MyProfileView(generics.RetrieveUpdateAPIView):
    """
    仅允许查看和修改“当前登录用户”自己的档案
    """
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # 核心逻辑：不从 URL 获取 ID，而是直接从 request 中获取当前用户
        # 如果 Profile 不存在则自动创建
        profile, created = Profile.objects.get_or_create(user=self.request.user)
        return profile


class ProfileSearchByFieldNameView(generics.ListAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsCompAdmin | IsAdmin]
    queryset = Profile.objects.all().select_related('user')

    # 1. 切换后端为 DjangoFilterBackend
    filter_backends = [DjangoFilterBackend]

    # 2. 使用 filterset_fields 明确指定过滤字段
    # 默认就是精确查询
    filterset_fields = ['real_name']