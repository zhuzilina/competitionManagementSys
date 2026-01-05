# Create your views here.
from rest_framework import viewsets, filters, status
from rest_framework.response import Response

from .models import Competition, CompetitionLevel, CompetitionCategory
from .serializers import CompetitionSerializer, CompetitionLevelSerializer, CompetitionCategorySerializer
from userManage.permissions import IsCompAdminOrReadOnly

class CompetitionViewSet(viewsets.ModelViewSet):
    queryset = Competition.objects.all()
    serializer_class = CompetitionSerializer

    # 1. 指定过滤器后端
    filter_backends = [filters.SearchFilter]
    # 2. 指定搜索字段，'title' 前面可以加修饰符
    search_fields = ['title']

    # 设置权限
    permission_classes = [IsCompAdminOrReadOnly]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # 逻辑检查：通过 related_name="awards" 检查是否存在关联记录
        # instance.awards.exists() 会执行一个高效的 EXISTS SQL 查询
        if instance.awards.exists():
            return Response(
                {
                    "detail": f"无法删除竞赛“{instance.title}”：该竞赛下已录入 {instance.awards.count()} 条获奖记录。请先处理或删除这些获奖记录后再试。"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 如果没有关联记录，则调用父类的逻辑执行删除
        return super().destroy(request, *args, **kwargs)

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