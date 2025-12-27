# Create your views here.
from rest_framework import viewsets
from .models import Competition
from .serializers import CompetitionSerializer
from userManage.permissions import IsCompAdminOrReadOnly

class CompetitionViewSet(viewsets.ModelViewSet):
    queryset = Competition.objects.all()
    serializer_class = CompetitionSerializer

    # 设置权限
    permission_classes = [IsCompAdminOrReadOnly]

    def perform_create(self, serializer):
        # 在保存数据时，注入当前登录的用户
        serializer.save(creator=self.request.user)