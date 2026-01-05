from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model

User = get_user_model()

def get_users_by_group(group_name):
    """根据组名获取用户列表"""
    return User.objects.filter(groups__name=group_name)