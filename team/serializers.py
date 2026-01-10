import os
import time

from django.utils.text import get_valid_filename
from rest_framework import serializers

from userProfile.serializers import UserDetailSerializer
from .models import Team
from django.contrib.auth import get_user_model

User = get_user_model()


class TeamSerializer(serializers.ModelSerializer):
    # 基础信息显示
    leader_user_id = serializers.ReadOnlyField(source='leader.user_id')
    event_name = serializers.ReadOnlyField(source='event.name')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # 展开详细信息（只读，用于前端渲染列表或详情）
    leader_detail = UserDetailSerializer(source='leader', read_only=True)
    members_detail = UserDetailSerializer(source='members', many=True, read_only=True)
    teachers_detail = UserDetailSerializer(source='teachers', many=True, read_only=True)

    # 录入字段（写时使用 user_id 列表）
    members = serializers.SlugRelatedField(
        required=False, many=True, queryset=User.objects.all(), slug_field='user_id'
    )
    teachers = serializers.SlugRelatedField(
        required=False, many=True, queryset=User.objects.all(), slug_field='user_id'
    )

    class Meta:
        model = Team
        fields = [
            'id', 'event', 'event_name', 'name',
            'leader', 'leader_user_id', 'leader_detail',
            'members', 'members_detail',
            'teachers', 'teachers_detail',
            'works', 'applied_award_level', 'temp_cert_no',
            'attachment', 'status', 'status_display', 'converted_award'
        ]
        read_only_fields = ['leader', 'status', 'converted_award']

    def validate_works(self, value):
        """处理作品上传重命名：队名.后缀"""
        if value and self.instance:
            ext = os.path.splitext(value.name)[1]
            # 使用 django 工具清理非法字符，保留中文
            safe_name = get_valid_filename(self.instance.name)
            value.name = f"{safe_name}{ext}"
        return value

    def validate_teachers(self, value):
        """确保老师角色校验"""
        for user in value:
            if not user.groups.filter(name='Teacher').exists():
                raise serializers.ValidationError(f"用户 {user.user_id} 不是指导老师角色。")
        return value

    def validate(self, data):
        user = self.context['request'].user
        instance = self.instance

        # 校验：队长不能在成员列表中
        members = data.get('members')
        current_leader = instance.leader if instance else user
        if members and current_leader in members:
            raise serializers.ValidationError({"members": "队长已在团队中，无需重复添加。"})

        # 重复建队校验（仅创建时）
        if not instance:
            event = data.get('event')
            if Team.objects.filter(leader=user, event=event).exists():
                raise serializers.ValidationError({"detail": "您已在该赛事中创建过团队。"})

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

    def validate_works(self, value):
        if value:
            # 1. 获取团队名称 (从 self.instance 获取，因为这是 PATCH 操作)
            team_name = self.instance.name

            # 2. 获取原始文件的后缀名
            ext = os.path.splitext(value.name)[1]  # 例如 '.pdf' 或 '.zip'

            # 3.清洗文件名
            clean_name = get_valid_filename(team_name)

            # 3. 构造新的文件名： 团队名.后缀
            # 注意：为了防止文件名包含非法字符，可以使用 django.utils.text.slugify 或简单替换
            new_filename = f"{clean_name}_{int(time.time())}{ext}"

            # 4. 重新赋值文件名
            value.name = new_filename

        return value