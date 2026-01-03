import django_filters
from django.contrib.auth.models import Group
from .models import User

class UserFilter(django_filters.FilterSet):
    # 1. 按角色名称筛选 (Group 关联)
    # lookup_expr='exact' 要求角色名完全一致，例如 "admin"
    role = django_filters.CharFilter(field_name='groups__name', lookup_expr='exact', label="角色名称")

    # 2. 按 Profile 中的文本字段筛选
    # 使用 icontains 实现模糊搜索，方便输入部分文字也能匹配
    department = django_filters.CharFilter(field_name='profile__department', lookup_expr='icontains')
    major = django_filters.CharFilter(field_name='profile__major', lookup_expr='icontains')
    clazz = django_filters.CharFilter(field_name='profile__clazz', lookup_expr='icontains')
    real_name = django_filters.CharFilter(field_name='profile__real_name', lookup_expr='icontains')

    class Meta:
        model = User
        # 这里定义的字段会生成默认的精确匹配，上面的自定义字段会覆盖它们
        fields = ['role', 'department', 'major', 'clazz', 'real_name']