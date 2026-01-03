from django.http import JsonResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Menu
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    MenuTreeSerializer,
    ChangePasswordSerializer, GroupSerializer
)
from . import permissions
from .utils import UserFilter

User = get_user_model()
# Create your views here.
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    # 允许所有人访问
    permission_classes = [permissions.IsAdmin]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message":"用户注册成功",
                "user_id": user.user_id,
                "roles": [g.name for g in user.groups.all()]
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# 自定义登录返回数据
class LoginTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        # 添加自定义字段
        data['user_id'] = self.user.user_id
        data['roles'] = [group.name for group in self.user.groups.all()]
        return data

class LoginTokenObtainPairView(TokenObtainPairView):
    serializer_class = LoginTokenObtainPairSerializer

# 获取所有用户视图
class UserListView(generics.ListAPIView):
    # 优化查询：select_related 用于一对一(Profile)，prefetch_related 用于多对多(Groups)
    queryset = User.objects.all().select_related('profile').prefetch_related('groups')
    serializer_class = UserSerializer

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdmin]

    # 启用过滤
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserFilter


# 查询、更新、删除单个用户
class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [
        permissions.IsAdmin,
        permissions.NotChangingSelf,
        permissions.NotDeletingSelf
    ]
    lookup_field = 'user_id'


class UserMenuView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_superuser:
            menus = Menu.objects.all()
        else:
            # 获取用户所在角色拥有的所有菜单
            menus = Menu.objects.filter(roles__in=user.groups.all()).distinct()

        # 拿到所有有权访问的菜单 ID 列表
        valid_menu_ids = list(menus.values_list('id', flat=True))

        # 筛选根节点
        root_menus = menus.filter(parent__isnull=True)

        # 关键：将 valid_menu_ids 通过 context 传递给序列化器
        serializer = MenuTreeSerializer(
            root_menus,
            many=True,
            context={'valid_menu_ids': valid_menu_ids}
        )
        # return Response(serializer.data)
        return JsonResponse("[]", safe=False)


class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # 始终返回当前登录的用户对象
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # 1. 检查旧密码是否正确
            if not self.object.check_password(serializer.data.get("old_password")):
                return Response({"old_password": ["旧密码错误"]}, status=status.HTTP_400_BAD_REQUEST)

            # 2. 设置新密码（注意要用 set_password 才能进行哈希加密）
            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()

            return Response({"message": "密码修改成功"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserRoleStatisticsView(APIView):
    """
    获取不同角色的用户数量统计
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdmin]

    def get(self, request, *args, **kwargs):
        # 核心逻辑：从 Group 模型出发，统计关联的 user 数量
        # 使用 annotate 聚合查询
        stats = Group.objects.annotate(user_count=Count('user')).values('name', 'user_count')

        # 如果你想包含那些“没有分配任何角色”的用户数量：
        unassigned_count = User.objects.filter(groups__isnull=True).count()

        # 格式化数据
        data = {
            "role_stats": list(stats),
            "unassigned_stats": {
                "name": "未分配角色",
                "user_count": unassigned_count
            },
            "total_users": User.objects.count()
        }

        return Response(data)


class RoleListView(generics.ListAPIView):
    """
    获取系统中所有的角色组及其 ID
    """
    queryset = Group.objects.all().order_by('id')
    serializer_class = GroupSerializer
    # 既然只有管理员能管理用户，这里通常也建议加权限控制
    # permission_classes = [IsAdmin]