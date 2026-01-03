from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from userManage.models import Menu  # 请确保路径正确


class Command(BaseCommand):
    help = '按照角色需求初始化系统菜单树'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('开始清理并重新初始化菜单数据...'))

        # 1. 清理数据（可选，防止重复执行脚本产生冗余）
        Menu.objects.all().delete()

        # --- 第一部分：创建菜单项 ---

        # [获奖管理] 目录及子菜单
        award_mgt = Menu.objects.create(title="获奖管理", icon="Award", path="/award", component="Layout",
                                        menu_type="M", order_num=100)
        my_award = Menu.objects.create(title="我的获奖", parent=award_mgt, path="my", component="award/my/index",
                                       menu_type="C", order_num=1)
        award_overview = Menu.objects.create(title="总览", parent=award_mgt, path="overview",
                                             component="award/overview/index", menu_type="C", order_num=2)
        award_search = Menu.objects.create(title="获奖查询", parent=award_mgt, path="search",
                                           component="award/search/index", menu_type="C", order_num=3)
        award_entry = Menu.objects.create(title="奖项录入", parent=award_mgt, path="entry",
                                          component="award/entry/index", menu_type="C", order_num=4)
        award_report = Menu.objects.create(title="报表打印", parent=award_mgt, path="report",
                                           component="award/report/index", menu_type="C", order_num=5)

        # [竞赛管理] 目录及子菜单
        comp_mgt = Menu.objects.create(title="竞赛管理", icon="Competition", path="/competition", component="Layout",
                                       menu_type="M", order_num=200)
        comp_overview = Menu.objects.create(title="总览", parent=comp_mgt, path="overview",
                                            component="competition/overview/index", menu_type="C", order_num=1)
        comp_search = Menu.objects.create(title="查询竞赛", parent=comp_mgt, path="search",
                                          component="competition/search/index", menu_type="C", order_num=2)
        comp_entry = Menu.objects.create(title="竞赛录入", parent=comp_mgt, path="entry",
                                         component="competition/entry/index", menu_type="C", order_num=3)

        # [证书管理] 目录及子菜单
        cert_mgt = Menu.objects.create(title="证书管理", icon="Certificate", path="/certificate", component="Layout",
                                       menu_type="M", order_num=300)
        cert_overview = Menu.objects.create(title="总览", parent=cert_mgt, path="overview",
                                            component="certificate/overview/index", menu_type="C", order_num=1)
        cert_search = Menu.objects.create(title="证书查询", parent=cert_mgt, path="search",
                                          component="certificate/search/index", menu_type="C", order_num=2)

        # [用户管理] 目录及子菜单 (超级管理员专用)
        user_mgt = Menu.objects.create(title="用户管理", icon="User", path="/user", component="Layout", menu_type="M",
                                       order_num=400)
        user_overview = Menu.objects.create(title="总览", parent=user_mgt, path="overview",
                                            component="user/overview/index", menu_type="C", order_num=1)
        user_create = Menu.objects.create(title="创建用户", parent=user_mgt, path="create",
                                          component="user/create/index", menu_type="C", order_num=2)
        user_search = Menu.objects.create(title="查询用户", parent=user_mgt, path="search",
                                          component="user/search/index", menu_type="C", order_num=3)

        # --- 第二部分：创建角色并分配菜单 ---

        # 1. Student 角色
        student_group, _ = Group.objects.get_or_create(name='Student')
        student_group.menus.set([award_mgt, my_award])

        # 2. Teacher 角色
        teacher_group, _ = Group.objects.get_or_create(name='Teacher')
        teacher_group.menus.set([award_mgt, my_award])

        # 3. CompetitionAdministrator 角色
        comp_admin_group, _ = Group.objects.get_or_create(name='CompetitionAdministrator')
        comp_admin_group.menus.set([
            award_mgt, award_overview, award_search, award_entry, award_report,
            comp_mgt, comp_overview, comp_search, comp_entry,
            cert_mgt, cert_overview, cert_search
        ])

        # 4. 超级管理员角色 (获取所有权限)
        # 注意：你在 View 里写了 superuser 逻辑，这里主要是给分配了该 Group 的非 superuser 使用
        admin_group, _ = Group.objects.get_or_create(name='Administrator')
        admin_group.menus.set(Menu.objects.all())

        self.stdout.write(self.style.SUCCESS('菜单及角色权限初始化成功！'))