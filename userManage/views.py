from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .serializers import RegisterSerializer,UserSerializer
from . import permissions

User = get_user_model()
# Create your views here.
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    # 允许所有人访问
    permission_classes = [AllowAny]

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
    queryset = User.objects.all()
    serializer_class = UserSerializer

    # 设置认证方式和权限类
    authentication_classes = [JWTAuthentication]
    permission_classes = [
        permissions.IsCommonManager
    ]


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
