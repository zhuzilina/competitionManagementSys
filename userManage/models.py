from django.db import models
from django.contrib.auth.models import AbstractUser
from mptt.models import MPTTModel, TreeForeignKey

# Create your models here.
class User(AbstractUser):
    user_id = models.CharField(max_length=11,unique=True,verbose_name="学工号")
    USERNAME_FIELD = 'user_id'

    REQUIRED_FIELDS = ['username']


class Menu(MPTTModel):
    MENU_TYPE_CHOICES = [
        ('M', '目录'),  # Directory
        ('C', '菜单'),  # Menu
        ('F', '按钮'),  # Function/Button
    ]

    title = models.CharField(max_length=50)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    icon = models.CharField(max_length=100, null=True, blank=True, verbose_name="图标")
    path = models.CharField(max_length=200, null=True, blank=True, verbose_name="路由地址")
    component = models.CharField(max_length=200, null=True, blank=True, verbose_name="组件路径")
    permission_code = models.CharField(max_length=100, null=True, blank=True, verbose_name="权限标识")
    menu_type = models.CharField(max_length=1, choices=MENU_TYPE_CHOICES, default='M')
    order_num = models.IntegerField(default=0, verbose_name="显示排序")

    # 关联 Django 内置的 Group (角色)
    roles = models.ManyToManyField('auth.Group', related_name='menus', verbose_name="可见角色")

    class Meta:
        db_table = 'sys_menu'
        ordering = ['order_num']
        verbose_name = "菜单管理"

    def __str__(self):
        return self.title