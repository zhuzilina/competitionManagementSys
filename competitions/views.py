# Create your views here.
from rest_framework import viewsets
from .models import Competition, CompetitionLevel, CompetitionCategory
from .serializers import CompetitionSerializer, CompetitionLevelSerializer, CompetitionCategorySerializer
from userManage.permissions import IsCompAdminOrReadOnly

class CompetitionViewSet(viewsets.ModelViewSet):
    queryset = Competition.objects.all()
    serializer_class = CompetitionSerializer

    # 设置权限
    permission_classes = [IsCompAdminOrReadOnly]

    def perform_create(self, serializer):
        # 在保存数据时，注入当前登录的用户
        serializer.save(creator=self.request.user)


class CompetitionLevelViewSet(viewsets.ModelViewSet):
    queryset = CompetitionLevel.objects.all()
    # 设置权限
    permission_classes = [IsCompAdminOrReadOnly]
    serializer_class = CompetitionLevelSerializer


class CompetitionCategoryViewSet(viewsets.ModelViewSet):
    queryset = CompetitionCategory.objects.all()
    # 设置权限
    permission_classes = [IsCompAdminOrReadOnly]
    serializer_class = CompetitionCategorySerializer