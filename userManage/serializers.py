from django.db import transaction
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from userManage.models import Menu
from userProfile.models import Profile
User = get_user_model()


# 定义角色序列化器
class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name']


# 定义用户序列化器
class UserSerializer(serializers.ModelSerializer):
    # 显式定义密码字段，确保密码是只写的
    password = serializers.CharField(write_only=True,required=True,style={'input_type':'password'})
    # 方便查看用户所属的角色
    group_details = GroupSerializer(many=True, read_only=True, source='groups')

    class Meta:
        # 定义Meta类
        model = User
        fields = ['id','user_id','username','password','groups','group_details']

    def create(self, validated_data):
        # 提取角色数据
        groups_data = validated_data.pop('groups', [])

        # 使用create_user创建新用户
        user = User.objects.create_user(
            user_id=validated_data['user_id'],
            username=validated_data.get('username',validated_data['user_id']),# 默认为user_id
            password=validated_data['password']
        )

        # 为用户分配角色
        if groups_data:
            # 使用set方法直接关联多个 Group对象或ID
            user.groups.set(groups_data)

        return user

    def update(self, instance, validated_data):
        # 处理更新逻辑时的角色分配
        groups_data = validated_data.pop('groups', None)
        password = validated_data.pop('password', None)

        # 更新普通字段
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # 处理密码加密更新
        if password is not None:
            instance.set_password(password)

        instance.save()

        # 更新角色
        if groups_data is not None:
            instance.groups.set(groups_data)

        return instance


# 定义注册的序列化器
class RegisterSerializer(serializers.ModelSerializer):
    # 密码确认字段
    re_password = serializers.CharField(write_only=True, required=True)
    # 角色字段
    role_names = serializers.ListField(child=serializers.CharField(),write_only=True, required=False)
    # 档案资料字段
    real_name = serializers.CharField(write_only=True, required=True)
    department = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['user_id', 'username', 'password', 're_password', 'real_name', 'department', 'role_names']
        extra_kwargs = {
            'password':{'write_only':True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['re_password']:
            raise serializers.ValidationError({"password":"两次输入的密码不一致"})
        return attrs

    def create(self, validated_data):
        # 移除不需要存入User模型的字段
        validated_data.pop('re_password')
        real_name = validated_data.pop('real_name')
        department = validated_data.pop('department')
        role_names = validated_data.pop('role_names', [])

        # 创建用户(保证原子性）
        with transaction.atomic():
            user = User.objects.create_user(
                user_id=validated_data['user_id'],
                username=validated_data.get('username',validated_data['user_id']),# 默认为user_id
                password=validated_data['password']
            )
            # 创建对应的Profile信息
            Profile.objects.create(
                user=user,
                real_name=real_name,
                department=department
            )

            # 绑定角色
            if role_names:
                groups = Group.objects.filter(name__in=role_names)
                user.groups.set(groups)
            else:
                # 默认给一个学生角色
                default_group, _ = Group.objects.get_or_create(name='Student')
                user.groups.add(default_group)

        return user


class MenuTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Menu
        fields = ['id', 'parent', 'title', 'icon', 'path', 'component', 'permission_code', 'menu_type', 'children']

    def get_children(self, obj):
        # 从 context 获取有权限的 ID 列表
        valid_menu_ids = self.context.get('valid_menu_ids')

        # 获取该节点下的所有子节点
        children_queryset = obj.children.all()

        # 如果提供了有效 ID 列表，则进行过滤
        if valid_menu_ids is not None:
            children_queryset = children_queryset.filter(id__in=valid_menu_ids)

        if children_queryset.exists():
            # 递归调用时，记得再次传递 context
            return MenuTreeSerializer(
                children_queryset,
                many=True,
                context=self.context
            ).data
        return []


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=6)
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "两次输入的新密码不一致"})
        return data
