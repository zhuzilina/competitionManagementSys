import os

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from notifications.signals import notify

from award.models import Award
from certificate.models import Certificate
from competitions.models import Competition, CompetitionCategory, CompetitionLevel
from userManage.permissions import IsCompAdmin
from .models import AwardApplication
from .serializers import AwardApplySerializer, AwardApproveSerializer
from .utils import get_users_by_group

User = get_user_model()

class AwardApproveViewSet(viewsets.ModelViewSet):
    permission_classes = [IsCompAdmin]
    queryset = AwardApplication.objects.all()
    serializer_class = AwardApplySerializer

    @action(detail=True, methods=['post'])
    def do_approve(self, request, pk=None):
        app = self.get_object()

        if app.status != 'pending':
            return Response({"detail": "该申请已处理，请勿重复操作"}, status=status.HTTP_400_BAD_REQUEST)

        data = app.payload

        try:
            with transaction.atomic():
                # --- 1. 验证基础数据 ---
                if not data.get('comp_id'):
                    if not CompetitionCategory.objects.filter(pk=data.get('category_id')).exists():
                        raise ValueError(f"竞赛类别ID {data.get('category_id')} 不存在")
                    if not CompetitionLevel.objects.filter(pk=data.get('level_id')).exists():
                        raise ValueError(f"竞赛级别ID {data.get('level_id')} 不存在")

                # --- 2. 处理竞赛 ---
                comp_id = data.get('comp_id')
                if comp_id:
                    competition = Competition.objects.get(pk=comp_id)
                else:
                    competition, _ = Competition.objects.get_or_create(
                        title=data.get('comp_title'),
                        year=data.get('year'),
                        defaults={
                            'description': data.get('description', ''),
                            'uri': data.get('uri', ''),
                            'category_id': data.get('category_id'),
                            'level_id': data.get('level_id'),
                            'creator': app.applicant
                        }
                    )

                # --- 3. 处理证书 (关键：如果保存失败会抛错触发回滚) ---
                # 读取原始文件内容
                file_content = app.cert_image.read()
                file_name = os.path.basename(app.cert_image.name)

                new_cert = Certificate(cert_no=app.cert_no)
                # save(name, content, save=False) 这里的 save=False 是指暂不提交数据库，但会处理文件流
                new_cert.image_uri.save(file_name, ContentFile(file_content), save=False)
                new_cert.save()

                # --- 4. 创建正式 Award ---
                # 如果这一步失败（例如 award_level 为空），前面的 new_cert 产生的文件和记录都会回滚
                award = Award.objects.create(
                    competition=competition,
                    certificate=new_cert,
                    creator=app.applicant,
                    award_level=app.award_level,
                    award_date=app.award_date,
                )

                # --- 5. 关联人员 (校验学号) ---
                for field_name, ids_key in [('participants', 'participant_ids'), ('instructors', 'instructor_ids')]:
                    u_ids = data.get(ids_key, [])
                    if u_ids:
                        user_objs = User.objects.filter(user_id__in=u_ids)
                        if user_objs.count() != len(u_ids):
                            found_ids = list(user_objs.values_list('user_id', flat=True))
                            missing = set(u_ids) - set(found_ids)
                            raise ValueError(f"以下人员 ID 不存在: {list(missing)}")

                        getattr(award, field_name).set(user_objs)

                # --- 6. 状态流转与保存 ---
                app.approve()
                app.save()

                # --- 7. 发送通知 ---
                notify.send(
                    sender=request.user,
                    recipient=app.applicant,
                    verb='您的获奖申请已通过并入库',
                    target=award
                )

            return Response({"detail": "审批通过，正式记录已生成"}, status=status.HTTP_200_OK)

        except Competition.DoesNotExist:
            return Response({"detail": "关联的竞赛已不存在"}, status=400)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        except Exception as e:
            import logging
            logging.error(f"Approval Error: {str(e)}")
            # 这里的异常捕获确保了只要 atomic 内部有任何报错，证书记录和 Award 记录都不会留在数据库里
            return Response({"detail": f"操作失败，数据已回滚: {str(e)}"}, status=400)

    @action(detail=True, methods=['post'])
    def do_reject(self, request, pk=None):
        """增加拒绝申请的接口"""
        app = self.get_object()
        if app.status != 'pending':
            return Response({"detail": "该申请已处理"}, status=status.HTTP_400_BAD_REQUEST)

        app.reject()
        app.admin_remark = request.data.get('remark', '')
        app.save()

        notify.send(sender=request.user, recipient=app.applicant, verb='您的获奖申请已被退回')
        return Response({"detail": "已拒绝该申请"})


class AwardApplyViewSet(viewsets.ModelViewSet):
    queryset = AwardApplication.objects.all()
    serializer_class = AwardApproveSerializer
    # 只要登录的用户都可以提交申请
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # 权限隔离：普通用户只能看到自己提交的申请记录
        user = self.request.user
        if user.groups.filter(name='CompetitionAdministrator').exists():
            return AwardApplication.objects.all()
        return AwardApplication.objects.filter(applicant=user)

    def perform_create(self, serializer):
        # 1. 保存申请单
        instance = serializer.save(applicant=self.request.user)

        # 2. 获取属于 "CompetitionAdministrator" 组的所有用户
        admins = get_users_by_group('CompetitionAdministrator')

        if admins.exists():
            # 3. 发送消息
            # recipient 可以是一个 QuerySet，django-notifications 会自动处理批量发送
            notify.send(
                sender=self.request.user,
                recipient=admins,
                verb='提交了新的获奖审批申请',
                target=instance,
                description=f"待审批竞赛：{instance.payload.get('comp_title')}"
            )

    def perform_update(self, serializer):
        # 即使前端绕过了验证，后端在保存前最后一次守卫
        instance = self.get_object()
        if instance.status != 'pending':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("已审核的申请不可修改")
        serializer.save()

    def perform_destroy(self, serializer):
        # 同样的逻辑也适用于删除：不允许删除已通过的申请
        instance = self.get_object()
        if instance.status == 'approved':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("已通过的申请不可删除，如需撤销请联系管理员")
        instance.delete()