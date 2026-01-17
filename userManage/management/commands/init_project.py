import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = '初始化项目：执行迁移、创建角色组和初始用户'

    def handle(self, *args, **options):
        User = get_user_model()
        # 1. 执行数据库迁移
        self.stdout.write(self.style.SUCCESS('正在执行数据库迁移...'))
        call_command('migrate')

        # 2. 创建角色组
        roles = ['CompetitionAdministrator', 'Student', 'Teacher','Administrator']
        for role_name in roles:
            group, created = Group.objects.get_or_create(name=role_name)
            if created:
                self.stdout.write(f'成功创建组: {role_name}')
            else:
                self.stdout.write(f'组 {role_name} 已存在')

        # 3. 创建不同角色的用户
        # 定义用户信息：(学工号user_id，用户名, 密码, 组名, 是否是超级用户)
        users_to_create = [
            ('admin1','admin1', 'pass123', None, True),
            ('admin2','admin2', 'pass123', 'Administrator', False),
            ('comp3','comp3', 'pass123', 'CompetitionAdministrator', False),
            ('comp4','comp4', 'pass123', 'CompetitionAdministrator', False),
        ]

        for uid, uname, pwd, gname, is_staff in users_to_create:
            # 注意：这里使用 user_id 进行查询，因为它是你的 USERNAME_FIELD
            if not User.objects.filter(user_id=uid).exists():
                if is_staff:
                    # 创建超级用户
                    User.objects.create_superuser(
                        user_id=uid,
                        username=uname,
                        password=pwd,
                        email=f'{uid}@example.com'
                    )
                    self.stdout.write(self.style.SUCCESS(f'超级用户 {uid}({uname}) 创建成功'))
                else:
                    # 创建普通角色用户
                    user = User.objects.create_user(
                        user_id=uid,
                        username=uname,
                        password=pwd,
                        email=f'{uid}@example.com'
                    )
                    group = Group.objects.get(name=gname)
                    user.groups.add(group)
                    self.stdout.write(self.style.SUCCESS(f'用户 {uid}({uname}) 归属 {gname} 创建成功'))
            else:
                self.stdout.write(self.style.WARNING(f'用户 {uid} 已存在，跳过'))

        self.stdout.write(self.style.SUCCESS('项目初始化完成！'))