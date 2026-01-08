import os

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from notifications.signals import notify
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from award.models import Award
from certificate.models import Certificate
from team.models import Team
from .serializers import TeamSerializer, TeamFileUploadSerializer


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def is_comp_admin_user(self, user):
        """内部辅助方法：判断是否为竞赛管理员"""
        # 这里复用权限类的核心逻辑
        return user.groups.filter(name='CompetitionAdministrator').exists()

    def get_queryset(self):
        """查询优化：学生看自己的队，老师看指导的队，管理员看全部"""
        user = self.request.user
        if self.is_comp_admin_user(user):
            return Team.objects.all()

        # 返回用户身为队长、成员或指导老师的所有团队
        return Team.objects.filter(
            Q(leader=user) |
            Q(members=user) |
            Q(teachers=user)
        ).distinct()

    @action(detail=True, methods=['patch'], url_path='upload-files')
    def upload_files(self, request, pk=None):
        """
        学生接口：队长上传参赛作品(works)或获奖证书(attachment)
        PATCH /api/teams/{id}/upload-files/
        """
        team = self.get_object()

        # 1. 权限校验
        if team.leader != request.user:
            return Response({"detail": "只有队长有权上传文件"}, status=status.HTTP_403_FORBIDDEN)

        # 2. 状态校验
        if team.event.status == 'archived':
            return Response({"detail": "赛事已归档"}, status=status.HTTP_400_BAD_REQUEST)
        if team.status == 'approved':
            return Response({"detail": "获奖记录已锁定，如需修改请联系管理员"}, status=status.HTTP_403_FORBIDDEN)

        # 3. 使用专门的序列化器处理文件上传
        serializer = TeamFileUploadSerializer(team, data=request.data, partial=True)
        if serializer.is_valid():
            # 保存文件，如果是上传了 attachment，逻辑里会自动改为 submitted
            instance = serializer.save()
            if 'attachment' in request.FILES:
                instance.status = 'submitted'
                instance.save()
            return Response(TeamSerializer(instance).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        user = self.request.user
        event = serializer.validated_data.get('event')

        # 1. 赛事状态校验 (使用异常抛出，确保中断执行)
        if event.status != 'registration':
            raise serializers.ValidationError({"detail": "当前赛事不在报名阶段，无法创建团队。"})

        # 2. 队长唯一性校验
        if Team.objects.filter(event=event, leader=user).exists():
            raise serializers.ValidationError({
                "detail": f"您已经在 '{event.name}' 中担任了队长，无法重复创建。"
            })

        # 3. 自动绑定队长
        serializer.save(leader=user)

    def create(self, request, *args, **kwargs):
        # 使用 .exists() 检查权限，简洁高效
        if not request.user.groups.filter(name='Student').exists():
            return Response(
                {"detail": "只有学生可以创建团队并担任队长。"},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    # 阶段一：初筛审核 (针对报名信息)
    # ---------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='review-shortlist')
    def review_shortlist(self, request, pk=None):
        """
        管理员接口：初筛审核（报名 -> 入围）
        POST /team/info/{id}/review-shortlist/
        data: {"action": "approve" or "reject", "reason": "可选理由"}
        """
        team = self.get_object()
        if team.event.status != 'screening':
            return Response({"detail": "赛事不在初筛阶段"}, status=400)

        if not self.is_comp_admin_user(request.user):
            return Response({"detail": "权限不足"}, status=status.HTTP_403_FORBIDDEN)

        if team.status != 'submitted':
            return Response({"detail": "当前状态不可进行初筛"}, status=status.HTTP_400_BAD_REQUEST)

        action_type = request.data.get('action')
        reason = request.data.get('reason', '无')

        if action_type == 'approve':
            team.status = 'shortlisted'
            verb_msg = f'恭喜！您的团队“{team.name}”已通过初筛，获得参赛资格。'
        elif action_type == 'reject':
            team.status = 'rejected'
            verb_msg = f'很遗憾，您的团队“{team.name}”未通过初筛。原因：{reason}'
        else:
            return Response({"detail": "未知操作"}, status=status.HTTP_400_BAD_REQUEST)

        team.save()

        # 发送通知给队长
        notify.send(
            sender=request.user,
            recipient=team.leader,
            verb=verb_msg,
            target=team
        )

        return Response(TeamSerializer(team).data)

    # ---------------------------------------------------------
    # 阶段二：获奖审核 (针对证书和奖项)
    # ---------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='review-award')
    def review_award(self, request, pk=None):
        """
        管理员接口：终审评奖（入围 -> 获奖/结束）
        POST /team/info/{id}/review-award/
        data: {"action": "award" or "finish"}
        """
        team = self.get_object()
        if team.event.status != 'awarding':
            return Response({"detail": "赛事不在获奖阶段"}, status=400)
        if not self.is_comp_admin_user(request.user):
            return Response({"detail": "权限不足"}, status=status.HTTP_403_FORBIDDEN)

        team = self.get_object()
        if team.status != 'shortlisted':
            return Response({"detail": "只有入围团队可以进行获奖操作"}, status=status.HTTP_400_BAD_REQUEST)

        action_type = request.data.get('action')

        if action_type == 'finish':
            # 参赛了但没得奖
            team.status = 'ended'
            team.save()
            notify.send(
                sender=request.user,
                recipient=team.leader,
                verb=f'您的团队“{team.name}”参赛流程已结束。',
                target=team
            )
            return Response(TeamSerializer(team).data)

        elif action_type == 'award':
            # 获奖逻辑
            if not team.temp_cert_no or not team.attachment:
                return Response({"detail": "证书信息不完整"}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                # 1. 创建证书
                new_cert = Certificate()
                new_cert.cert_no = team.temp_cert_no
                if team.attachment:
                    filename = os.path.basename(team.attachment.name)
                    new_cert.image_uri.save(filename, team.attachment.file, save=False)
                new_cert.save()

                # 2. 创建获奖记录
                new_award = Award.objects.create(
                    competition=team.event.competition,
                    event=team.event,
                    certificate=new_cert,
                    award_level=team.applied_award_level,
                    award_date=timezone.now().date(),
                    team_name_snapshot=team.name,
                    creator=request.user
                )
                new_award.participants.set([team.leader] + list(team.members.all()))
                new_award.instructors.set(team.teachers.all())

                # 3. 更新团队状态
                team.converted_award = new_award
                team.status = 'awarded'
                team.save()

                # 4. 发送获奖通知
                notify.send(
                    sender=request.user,
                    recipient=team.leader,
                    verb=f'您的获奖申请已通过！奖项：{team.applied_award_level}。',
                    target=new_award  # 注意这里 target 改为了生成的 Award 对象
                )

                return Response(TeamSerializer(team).data)

        return Response({"detail": "无效的操作"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='update-info')
    def update_info(self, request, pk=None):
        team = self.get_object()
        event_status = team.event.status

        # 1. 基础权限：必须是队长
        if team.leader != request.user:
            return Response({"detail": "仅限队长操作"}, status=403)

        # 2. 根据赛事阶段控制可修改字段
        if event_status == 'registration':
            # 报名阶段，允许修改所有基础信息
            fields = ['name', 'members', 'teachers']
        elif event_status == 'ongoing':
            # 比赛阶段，只允许提交作品
            fields = ['works']
        elif event_status == 'awarding':
            # 评奖阶段，只允许补充证书信息
            fields = ['temp_cert_no', 'attachment', 'applied_award_level']
        else:
            return Response({"detail": f"当前赛事阶段 ({team.event.get_status_display()}) 不允许修改任何信息"},
                            status=400)

        # 3. 过滤非法字段
        filtered_data = {k: v for k, v in request.data.items() if k in fields}
        if not filtered_data:
            return Response({"detail": "当前阶段无权修改所选字段"}, status=400)

        serializer = self.get_serializer(team, data=filtered_data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='my-participation')
    def my_participation(self, request):
        """
        判断当前用户是否在特定竞赛活动下创建了团队
        GET /team/info/my_participation/?event=1
        """
        event_id = request.query_params.get('event')

        if not event_id:
            return Response({"detail": "请提供 event 参数"}, status=status.HTTP_400_BAD_REQUEST)

        # 检查是否是该竞赛的队长
        is_leader = Team.objects.filter(event_id=event_id, leader=request.user).exists()

        is_member = Team.objects.filter(event_id=event_id, members=request.user).exists()

        return Response({
            "is_leader": is_leader,
            "is_member": is_member,
            "can_create": not is_leader  # 方便前端直接判断是否显示“创建团队”按钮
        })