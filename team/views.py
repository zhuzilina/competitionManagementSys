import os

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status
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

    def get_queryset(self):
        """查询优化：学生看自己的队，老师看指导的队，管理员看全部"""
        user = self.request.user
        if user.is_staff:
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
        """创建时自动绑定队长"""
        serializer.save(leader=self.request.user)

    def create(self, request, *args, **kwargs):
        """重写创建方法，增加对非学生角色的限制（可选）"""
        if not request.user.groups.filter(name='Student').exists():
            return Response({"detail": "只有学生角色可以创建团队并担任队长。"},
                            status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        old_status = instance.status
        new_status = request.data.get('status')

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # 判断审核通过动作
        if new_status == 'approved' and old_status != 'approved':
            # 1. 获取学生提交的证书编号
            cert_no = instance.temp_cert_no
            if not cert_no:
                return Response({"detail": "学生尚未提供证书编号，无法通过审核"}, status=status.HTTP_400_BAD_REQUEST)

            # 2. 校验：只有管理员或老师有权审核
            if not (request.user.is_staff or request.user.groups.filter(name__in=['CompetitionAdministrator']).exists()):
                return Response({"detail": "您没有权限执行审核操作"}, status=status.HTTP_403_FORBIDDEN)

            # 3. 校验：必须有附件
            if not instance.attachment:
                return Response({"detail": "该团队尚未上传证书附件，无法通过审核"}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                # --- A. 创建正式证书 (Certificate) ---
                new_cert = Certificate()
                new_cert.cert_no = cert_no  # 使用前端传来的编号

                if instance.attachment:
                    filename = os.path.basename(instance.attachment.name)
                    new_cert.image_uri.save(
                        filename,
                        instance.attachment.file,
                        save=False
                    )
                new_cert.save()

                # --- B. 创建获奖记录 (Award) ---
                new_award = Award.objects.create(
                    competition=instance.event.competition,
                    event=instance.event,
                    certificate=new_cert,
                    award_level=instance.applied_award_level,
                    award_date=timezone.now().date(),
                    team_name_snapshot=instance.name,
                    creator=request.user
                )

                # --- C. 关联参与人 ---
                all_students = [instance.leader] + list(instance.members.all())
                new_award.participants.set(all_students)
                new_award.instructors.set(instance.teachers.all())

                # --- D. 更新 Team 状态和关联关系 ---
                instance.converted_award = new_award
                instance.status = 'approved'
                instance.save()

                return Response(TeamSerializer(instance).data)

        # 常规修改
        self.perform_update(serializer)
        return Response(serializer.data)