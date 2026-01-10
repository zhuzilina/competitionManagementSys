from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Profile

class ProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.ReadOnlyField(source='user.user_id')
    role_name = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'user_id', 'real_name', 'phone', 'email',
            'department', 'major', 'clazz', 'title', 'role_name'
        ]

    def get_role_name(self, obj):
        # 返回用户所属的第一个组名（角色）
        group = obj.user.groups.first()
        return group.name if group else "普通用户"

    def to_representation(self, instance):
        """动态处理字段显隐"""
        ret = super().to_representation(instance)
        # 逻辑判断：如果用户属于 'Student' 组，则在返回结果中移除 title
        if instance.user.groups.filter(name='Student').exists():
            ret.pop('title', None)
        return ret


class UserDetailSerializer(serializers.ModelSerializer):
    # 通过 related_name='profile' 嵌套你现有的序列化器
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = get_user_model()
        fields = ['user_id', 'username', 'profile']