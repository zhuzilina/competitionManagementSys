# Create your views here.
from django.db import transaction
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from award.models import Award
from .models import Competition, CompetitionLevel, CompetitionCategory, CompetitionEvent
from .serializers import CompetitionSerializer, CompetitionLevelSerializer, CompetitionCategorySerializer, \
    CompetitionEventSerializer
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


class CompetitionEventViewSet(viewsets.ModelViewSet):
    queryset = CompetitionEvent.objects.all().order_by('-start_time')
    serializer_class = CompetitionEventSerializer

    permission_classes = [IsCompAdminOrReadOnly]

    def get_queryset(self):
        """
        过滤逻辑：
        - 学生只能看到 'active' 和 'reviewing' 的比赛
        - 管理员可以看到所有（包括 archived）
        """
        user = self.request.user
        if user.is_staff or user.groups.filter(name__in=['Teacher', 'Admin']).exists():
            return CompetitionEvent.objects.all().order_by('-start_time')

        # 普通学生只能看到进行中或审核中的
        return CompetitionEvent.objects.filter(status__in=['active', 'reviewing'])

    @action(detail=True, methods=['post'], url_path='archive')
    def archive_event(self, request, pk=None):
        """
        管理员接口：关闭并归档赛事
        1. 计算并存入最终统计数据 (参赛人数、获奖人数)
        2. 将赛事状态改为 'archived'
        3. 销毁该赛事下的所有 Team 记录 (释放空间)
        """
        event = self.get_object()

        # 1. 检查状态，避免重复归档
        if event.status == 'archived':
            return Response({"detail": "该赛事已经处于归档状态。"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # --- A. 统计并持久化数据 ---
                # 统计参赛团队总数 (在删除之前统计)
                event.final_participants_count = event.teams.count()

                # 统计获奖人数 (查询已生成的正式 Award 记录数)
                # 假设 Award 模型有一个 event 外键关联到 CompetitionEvent
                event.final_winners_count = Award.objects.filter(event=event).count()

                # --- B. 更新赛事状态 ---
                event.status = 'archived'
                event.save()

                # --- C. 自动销毁关联的所有团队记录 ---
                # 这里的 delete() 会触发 django-cleanup 自动清理物理文件
                # 同时也释放了数据库空间。由于之前已经生成了 Award，获奖数据是安全的。
                event.teams.all().delete()

            return Response({
                "message": "赛事已成功归档",
                "participants": event.final_participants_count,
                "winners": event.final_winners_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": f"归档失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)