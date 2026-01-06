from rest_framework import serializers
from .models import Team
from django.contrib.auth import get_user_model

User = get_user_model()


class TeamSerializer(serializers.ModelSerializer):
    # 显示字段
    leader_name = serializers.ReadOnlyField(source='leader.username')
    event_name = serializers.ReadOnlyField(source='event.name')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # 文件字段在读时会返回 URL，在写时接收文件流
    # 设置为 required=False 允许在最初创建时不传，后续通过 PATCH 补传
    works = serializers.FileField(required=False, allow_null=True)
    attachment = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = Team
        fields = [
            'id', 'event', 'event_name', 'name', 'leader', 'leader_name',
            'members', 'teachers', 'works', 'applied_award_level',
            'attachment', 'status', 'status_display', 'converted_award'
        ]
        # leader 是自动绑定的，status 和 converted_award 由后端逻辑控制
        read_only_fields = ['leader', 'status', 'converted_award']

    def validate_event(self, value):
        """校验赛事是否处于可报名状态"""
        if value.status != 'active':
            raise serializers.ValidationError("当前赛事不在报名阶段或已结束。")
        return value

    def validate_teachers(self, value):
        """确保加入 teachers 字段的用户确实拥有 Teacher 角色"""
        for user in value:
            if not user.groups.filter(name='Teacher').exists():
                raise serializers.ValidationError(f"用户 {user.username} 不是老师，不能作为指导老师。")
        return value

    def validate(self, data):
        """业务逻辑校验"""
        user = self.context['request'].user
        # 1. 校验队长唯一性：一个学生只能担任一个队伍的队长
        if Team.objects.filter(leader=user).exists():
            raise serializers.ValidationError({"leader": "你已经作为队长创建过团队了，无法再次创建。"})

        return data


class TeamFileUploadSerializer(serializers.ModelSerializer):
    """
    专门用于补传文件或修改申报奖项的序列化器
    """
    class Meta:
        model = Team
        fields = ['works', 'attachment', 'applied_award_level','temp_cert_no']

    def update(self, instance, validated_data):
        # 只要有文件上传，就自动将状态改为“待审核”
        # 如果你希望作品上传和证书上传分开处理，可以在这里加逻辑判断
        if 'attachment' in validated_data:
            instance.status = 'submitted'
        return super().update(instance, validated_data)