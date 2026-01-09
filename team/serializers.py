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

    # 使用 user_id 而不是默认的 pk 进行关联录入
    members = serializers.SlugRelatedField(
        required=False,
        many=True,
        queryset=User.objects.all(),
        slug_field='user_id'  # 假设你的 User 模型中存储学号的字段名是 user_id
    )
    teachers = serializers.SlugRelatedField(
        required=False,
        many=True,
        queryset=User.objects.all(),
        slug_field='user_id'
    )

    class Meta:
        model = Team
        fields = [
            'id', 'event', 'event_name', 'name', 'leader', 'leader_name',
            'members', 'teachers', 'works', 'applied_award_level','temp_cert_no',
            'attachment', 'status', 'status_display', 'converted_award'
        ]
        # leader 是自动绑定的，status 和 converted_award 由后端逻辑控制
        read_only_fields = ['leader', 'status', 'converted_award']

    def validate_teachers(self, value):
        """确保加入 teachers 字段的用户确实拥有 Teacher 角色"""
        for user in value:
            if not user.groups.filter(name='Teacher').exists():
                raise serializers.ValidationError(f"用户 {user.username} 不是老师，不能作为指导老师。")
        return value

    def validate(self, data):
        user = self.context['request'].user
        instance = self.instance

        # 1. 获取当前操作中的成员列表（如果是 PATCH 请求且没传 members，则从实例中取）
        # data.get('members') 获取的是请求中新传的成员
        members = data.get('members')

        # 2. 获取队长对象
        # 创建时队长是当前用户；更新时如果 leader 是只读的，队长通常是 instance.leader
        current_leader = instance.leader if instance else user

        # 3. 校验逻辑：队长不能在成员列表中
        if members and current_leader in members:
            raise serializers.ValidationError({
                "members": "队长已在团队中，无需重复添加到成员列表。"
            })

        # 4. “重复建队”校验
        if not instance:
            event = data.get('event')
            if Team.objects.filter(leader=user, event=event).exists():
                raise serializers.ValidationError({"detail": "在该竞赛活动中，你已经创建过团队了。"})

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