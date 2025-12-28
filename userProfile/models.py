from django.db import models
from django.conf import settings


class Profile(models.Model):
    # 核心关联：使用 user_id 所在的 User 模型
    # on_delete=models.CASCADE 意味着用户账号删除，档案也随之删除
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        to_field='user_id'  # 明确指定关联到自定义的 user_id 字段
    )

    # 基础信息
    real_name = models.CharField(max_length=50, verbose_name="真实姓名")
    phone = models.CharField(max_length=11, verbose_name="手机号", blank=True, null=True)
    email = models.EmailField(verbose_name="邮箱地址", blank=True, null=True)

    # 学业/组织信息
    department = models.CharField(max_length=100, verbose_name="院系")
    major = models.CharField(max_length=100, verbose_name="专业", blank=True, null=True)
    clazz = models.CharField(max_length=50, verbose_name="班级", blank=True, null=True)

    # 职业信息
    title = models.CharField(
        max_length=50,
        verbose_name="职称",
        help_text="仅老师/管理员填写",
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'sys_user_profile'
        verbose_name = "个人档案"

    def __str__(self):
        return f"{self.real_name} ({self.user.user_id})"