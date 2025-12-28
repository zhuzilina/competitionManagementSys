from rest_framework import generics, permissions, filters
from .models import Profile
from .serializers import ProfileSerializer
from userManage.permissions import IsCompAdmin

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
    """
    通过姓名模糊查找用户 Profile
    """
    serializer_class = ProfileSerializer
    permission_classes = [IsCompAdmin]

    # 获取所有 Profile 记录，并预加载 user 以提高性能
    queryset = Profile.objects.all().select_related('user')

    # 配置搜索后端
    filter_backends = [filters.SearchFilter]
    # 指定搜索的字段，'real_name' 对应 Profile 里的字段
    search_fields = ['real_name']