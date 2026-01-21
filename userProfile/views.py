from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, filters
from rest_framework.pagination import PageNumberPagination

from .models import Profile
from .serializers import ProfileSerializer
from userManage.permissions import IsAdminOrReadOnly


class MyProfileView(generics.RetrieveUpdateAPIView):
    """
    仅允许查看和修改“当前登录用户”自己的档案
    GET /user-profile/view/
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
    通过姓名搜索用户
    GET /user-profile/search/?real_name=张三
    """
    serializer_class = ProfileSerializer
    permission_classes = [IsAdminOrReadOnly]
    queryset = Profile.objects.all().select_related('user')

    # 1. 切换后端为 DjangoFilterBackend
    filter_backends = [DjangoFilterBackend]

    # 2. 使用 filterset_fields 明确指定过滤字段
    # 默认就是精确查询
    filterset_fields = ['real_name']


class ProfileRetrieveByUserIdView(generics.RetrieveAPIView):
    """
    通过 user_id (学号/工号) 获取该用户的档案详情
    GET /user-profile/by-user-id/{user_id}/
    """
    queryset = Profile.objects.all().select_related('user')
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    # 指定查找字段为关联 User 模型的 user_id
    lookup_field = 'user__user_id'
    # URL 中的参数名，默认与 lookup_field 一致，我们可以简化它
    lookup_url_kwarg = 'user_id'


class StandardResultsSetPagination(PageNumberPagination):
    """
    自定义分页配置：可以控制每一页的大小
    """
    page_size = 10  # 默认每页显示 10 条
    page_size_query_param = 'size'  # 允许客户端通过 ?size=20 自定义每页数量
    max_page_size = 100  # 最大允许每页 100 条


class ProfileListView(generics.ListAPIView):
    """
    获取所有用户档案列表（支持分页、搜索、过滤）
    GET /user-profile/list/?page=1&size=10
    """
    queryset = Profile.objects.all().select_related('user').order_by('id')
    serializer_class = ProfileSerializer
    permission_classes = [IsAdminOrReadOnly]  # 或者 permissions.IsAuthenticated

    # 启用分页
    pagination_class = StandardResultsSetPagination

    # 可选：如果你想在这个列表里也支持搜索或排序
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['college', 'major', 'clazz']  # 按学院、专业、班级精确过滤
    search_fields = ['real_name', 'phone', 'user__user_id']  # 支持模糊搜索
    ordering_fields = ['id', 'real_name']  # 支持排序