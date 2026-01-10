# Create your views here.
from django.db import transaction
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from notifications.signals import notify
from django.contrib.auth import get_user_model


from award.models import Award
from .models import Competition, CompetitionLevel, CompetitionCategory, CompetitionEvent
from .serializers import CompetitionSerializer, CompetitionLevelSerializer, CompetitionCategorySerializer, \
    CompetitionEventSerializer
from userManage.permissions import IsCompAdminOrReadOnly


User = get_user_model()
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

    def _notify_all_participants(self, event, message):
        """
        内部辅助方法：向所有报名该赛事的成员发送通知
        """
        # 1. 获取该赛事下所有团队的队长 ID
        leader_ids = event.teams.values_list('leader_id', flat=True)

        # 2. 获取该赛事下所有团队的队员 ID (ManyToManyField)
        member_ids = event.teams.values_list('members__id', flat=True)

        # 3.获取该赛事下所有团队的指导老师 ID

        teacher_ids = event.teams.values_list('teachers__id', flat=True)

        # 3. 合并 ID 并去重，排除 None 值
        all_user_ids = set(list(leader_ids) + list(member_ids) +list(teacher_ids))
        all_user_ids.discard(None)

        if not all_user_ids:
            return

        # 4. 获取对应的用户对象列表
        recipients = User.objects.filter(id__in=all_user_ids)

        # 5. 批量发送通知
        # verb: 动作描述, target: 关联的对象(当前赛事)
        notify.send(
            sender=self.request.user,  # 发送者通常是当前操作的管理员
            recipient=recipients,  # 接收者可以是 QuerySet 或 List
            verb=message,
            target=event
        )

    def get_queryset(self):
        user = self.request.user
        # 管理员可以看到所有
        if user.is_staff or user.groups.filter(name__in=['CompetitionAdministrator']).exists():
            return CompetitionEvent.objects.all().order_by('-start_time')

        # 学生和教师只能看到归档以前的所有阶段
        # 包含：registration, screening, ongoing, awarding
        return CompetitionEvent.objects.exclude(status='archived').order_by('-start_time')

    def perform_create(self, serializer):
        serializer.save(status='registration')

    @action(detail=True, methods=['post'], url_path='next-stage')
    def advance_stage(self, request, pk=None):
        """
        管理员接口：将赛事推进到下一个阶段，并重置入围团队状态
        """
        event = self.get_object()

        status_messages = {
            'screening': '报名已截止，赛事进入初筛阶段，请关注审核结果。',
            'ongoing': '恭喜！初筛已结束，入围团队请重新提交参赛作品/资料。',  # 修改了话术
            'awarding': '比赛已结束，正在进行最后的成果审核与奖项录入。',
        }

        stage_flow = ['registration', 'screening', 'ongoing', 'awarding']

        if event.status not in stage_flow:
            return Response({"detail": f"当前状态 [{event.status}] 不支持自动流转"},
                            status=status.HTTP_400_BAD_REQUEST)

        current_index = stage_flow.index(event.status)

        if current_index < len(stage_flow) - 1:
            next_status = stage_flow[current_index + 1]

            # 使用事务保证赛事状态和团队状态同步更新
            if event.status != 'registration':
                with transaction.atomic():
                    # 1. 识别并锁定“晋级名单”
                    # 注意：必须在修改状态前先获取这个 QuerySet
                    passed_teams = event.teams.filter(status='shortlisted')
                    passed_count = passed_teams.count()

                    # 获取晋级名单的 ID 列表，防止后续 update 影响过滤结果
                    passed_ids = list(passed_teams.values_list('id', flat=True))

                    # 2. 淘汰逻辑：
                    # 只要不在晋级名单里的，全部改为 ended
                    # 这样 draft, submitted, rejected 且未被管理员标记为 shortlisted 的人都会被淘汰
                    event.teams.exclude(id__in=passed_ids).update(status='ended')

                    # 3. 晋级逻辑：
                    # 将名单内的人员状态从 shortlisted 重置为 draft，开启下一轮提交
                    event.teams.filter(id__in=passed_ids).update(status='draft')

            # 更新赛事阶段
            event.status = next_status
            event.save()

            # 3. 发送全员通知
            if next_status in status_messages:
                self._notify_all_participants(event, status_messages[next_status])

            return Response({
                "detail": f"赛事已进入: {event.get_status_display()}。已重置 {passed_count if 'passed_count' in locals() else 0} 个入围团队为草稿状态。",
                "current_status": event.status
            })
        else:
            return Response({"detail": "已到达评奖阶段，下一步请执行归档操作"},
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='set-status')
    def set_specific_status(self, request, pk=None):
        """
        管理员接口：手动强转状态（用于应对突发情况，如打回重新报名）
        data: {"status": "registration"}
        """
        event = self.get_object()
        target_status = request.data.get('status')

        valid_statuses = [s[0] for s in CompetitionEvent.STATUS_CHOICES]
        if target_status not in valid_statuses:
            return Response({"detail": "无效的状态值"}, status=status.HTTP_400_BAD_REQUEST)

        event.status = target_status
        event.save()
        return Response({"detail": f"状态已成功修改为: {event.get_status_display()}"})
    @action(detail=True, methods=['post'], url_path='archive')
    def archive_event(self, request, pk=None):
        """
        管理员接口：关闭并归档赛事
        1. 计算并存入最终统计数据 (参赛人数、获奖人数)
        2. 将赛事状态改为 'archived'
        3. 销毁该赛事下的所有 Team 记录 (释放空间)
        """
        event = self.get_object()

        # 安全检查：只有处于评奖阶段的赛事才能归档
        if event.status != 'awarding':
            return Response({"detail": "赛事尚未完成评奖阶段，不能归档。"},
                            status=status.HTTP_400_BAD_REQUEST)

        # 1. 检查状态，避免重复归档
        if event.status == 'archived':
            return Response({"detail": "该赛事已经处于归档状态。"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # --- A. 统计并持久化数据 ---
                # 1. 获取所有【正式参赛】的团队 (排除草稿和被驳回的)
                # 只有这些团队的人员才算作正式参赛人数
                valid_teams = event.teams.filter(
                    status__in=['shortlisted', 'awarded', 'ended']
                )

                # 2. 统计真实参赛人数 (队长 + 成员 并去重)
                # 使用 values_list 获取所有队长ID和成员ID，然后用 set 去重
                leader_ids = valid_teams.values_list('leader_id', flat=True)
                member_ids = valid_teams.values_list('members__id', flat=True)

                # 合并两个 QuerySet 的结果并去重 (排除 None)
                total_participant_ids = set(list(leader_ids) + list(member_ids))
                if None in total_participant_ids:
                    total_participant_ids.remove(None)

                event.final_participants_count = len(total_participant_ids)

                # 3. 统计获奖人数 (直接从已生成的 Award 记录中统计人员去重)
                # 这样比统计 Team 更准确，因为 Award 记录了最终确定的名单
                awarded_users = get_user_model().objects.filter(
                    Q(awards_as_participant__event=event)
                ).distinct()
                event.final_winners_count = awarded_users.count()

                # --- B. 更新赛事状态 ---
                event.status = 'archived'
                event.save()

                # --- C. 自动销毁关联的所有团队记录 ---
                # 警告：由于 C 操作会级联删除 Team，务必确保 A 操作在 C 之前完成
                event.teams.all().delete()

            return Response({
                "message": "赛事已成功归档",
                "participants": event.final_participants_count,
                "winners": event.final_winners_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": f"归档失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)