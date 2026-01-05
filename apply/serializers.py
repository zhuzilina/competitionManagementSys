from rest_framework import serializers

from .models import AwardApplication

class AwardApplicationBaseSerializer(serializers.ModelSerializer):
    payload = serializers.JSONField()

    class Meta:
        model = AwardApplication
        fields = ['id', 'cert_image', 'cert_no','award_level','award_date', 'payload', 'status', 'created_at', 'applicant']
        read_only_fields = ['status', 'created_at', 'applicant']


class AwardApplySerializer(AwardApplicationBaseSerializer):
    def validate(self, attrs):
        # 获取当前实例（如果是更新操作）
        instance = self.instance

        # 优化点 1：只读限制
        if instance and instance.status != 'pending':
            raise serializers.ValidationError(
                f"当前状态为 {instance.status}，无法修改已完成审批的申请。"
            )

        # 优化点 2：Payload 业务校验
        self.validate_business_logic(attrs.get('payload', {}))

        return attrs

    def validate_business_logic(self, payload):
        """校验 JSON 内部的关联 ID 是否合法"""
        from competitions.models import CompetitionCategory, CompetitionLevel

        category_id = payload.get('category_id')
        level_id = payload.get('level_id')

        # 校验竞赛类别
        if category_id:
            if not CompetitionCategory.objects.filter(pk=category_id).exists():
                raise serializers.ValidationError({"payload": f"竞赛类别 ID {category_id} 不存在"})
        else:
            raise serializers.ValidationError({"payload": "必须提供 category_id"})

        # 校验竞赛级别
        if level_id:
            if not CompetitionLevel.objects.filter(pk=level_id).exists():
                raise serializers.ValidationError({"payload": f"竞赛级别 ID {level_id} 不存在"})
        else:
            raise serializers.ValidationError({"payload": "必须提供 level_id"})

        # 校验用户ID 是否合法
        from django.contrib.auth import get_user_model
        User = get_user_model()
        participant_ids = payload.get('participant_ids', [])
        instructor_ids = payload.get('instructor_ids', [])
        if participant_ids:
            exists_count = User.objects.filter(user_id__in=participant_ids).count()
            if exists_count != len(participant_ids):
                raise serializers.ValidationError({"payload": "部分参与人 user_id 无效"})
        if instructor_ids:
            exists_count = User.objects.filter(user_id__in=instructor_ids).count()
            if exists_count != len(participant_ids):
                raise serializers.ValidationError({"payload": "部分指导老师 user_id 无效"})


class AwardApproveSerializer(AwardApplicationBaseSerializer):
    class Meta(AwardApplicationBaseSerializer.Meta):
        # 审批时，管理员可以查看更多信息，或者某些字段变为可写
        read_only_fields = ['created_at', 'applicant']