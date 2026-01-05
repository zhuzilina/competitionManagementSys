from rest_framework import viewsets, permissions, status
import os

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Certificate
from .serializers import CertificateSerializer
from userManage.permissions import IsCompAdminOrReadOnly
# Create your views here.
class CertificateViewSet(viewsets.ModelViewSet):
    queryset = Certificate.objects.all()
    serializer_class = CertificateSerializer

    def get_permissions(self):
        """
        权限拆分：
        - 查询 (list, retrieve): 登录用户即可
        - 增删改 (create, update, destroy): 需管理员角色
        """
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsCompAdminOrReadOnly()]

    def destroy(self, request, *args, **kwargs):
        # 1. 获取要删除的实例
        instance = self.get_object()

        # 2. 友好校验：检查关联关系
        # hasattr(instance, 'award') 检查 OneToOneField 反向关联
        if hasattr(instance, 'award'):
            return Response(
                {
                    "success": False,
                    "message": "删除失败：证书已被引用",
                    "detail": f"该证书目前关联着获奖记录“{instance.award}”，无法单独删除。请先删除对应的获奖记录。"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. 执行真正的删除
        self.perform_destroy(instance)

        return Response(
            {"success": True, "message": "证书记录及其物理文件已成功删除"},
            status=status.HTTP_200_OK  # 默认是 204 No Content，建议改用 200 以携带友好提示
        )
