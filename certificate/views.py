from rest_framework import viewsets, permissions
import os
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

    def perform_destroy(self, instance):
        """
        重要：删除数据库记录时，同步删除磁盘上的物理文件
        """
        if instance.image_uri:
            if os.path.isfile(instance.image_uri.path):
                os.remove(instance.image_uri.path)
        instance.delete()