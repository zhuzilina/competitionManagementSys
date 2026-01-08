from django.db import models
from django.conf import settings

# Create your models here.
class CompetitionLevel(models.Model):
    """竞赛级别： A，B，C等"""
    name = models.CharField(max_length=20, unique=True, verbose_name="级别名称")
    description = models.TextField(blank=True, null=True, verbose_name="级别描述")

    class Meta:
        db_table = 'sys_competition_level'
        verbose_name="竞赛级别"

    def __str__(self):
        return self.name


class CompetitionCategory(models.Model):
    """竞赛类别: 创新类、算法类"""
    name = models.CharField(max_length=20, unique=True, verbose_name="类别名称")

    class Meta:
        db_table = 'sys_competition_category'
        verbose_name = "竞赛类别"

    def __str__(self):
        return self.name


class Competition(models.Model):
    """竞赛核心信息"""
    title = models.CharField(max_length=255, verbose_name="竞赛名称")
    description = models.TextField(verbose_name="竞赛简介", blank=True, null=True)
    year = models.IntegerField(verbose_name="举办年份")
    uri = models.CharField(max_length=8182, verbose_name="竞赛官网")

    # 使用外键关联动态表
    category = models.ForeignKey(
        CompetitionCategory,
        on_delete=models.PROTECT, # 防止误删类别导致数据丢失
        related_name="competitions",
        verbose_name="竞赛类别"
    )
    level = models.ForeignKey(
        CompetitionLevel,
        on_delete=models.PROTECT,
        related_name="competitions",
        verbose_name="竞赛级别"
    )
    # 审计信息
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_competitions",
        verbose_name="创建者"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sys_competition'
        verbose_name = "竞赛信息"


class CompetitionEvent(models.Model):
    """
    竞赛发布/场次 (Instance)
    例如：第十五届蓝桥杯、2024年ACM校赛
    """
    STATUS_CHOICES = (
        ('registration', '报名中'),  # 学生可以创建 Team, 提交状态为 submitted
        ('screening', '初筛中'),  # 报名截止，管理员调用 review-shortlist
        ('ongoing', '比赛进行中'),  # 初筛结束，入围团队正在准备作品或决赛
        ('awarding', '评奖/审核中'),  # 比赛结束，管理员调用 review-award 录入奖项
        ('archived', '已归档'),  # 全部结束，数据快照已生成
    )

    # 关联基础模型
    competition = models.ForeignKey(
        'Competition',
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name="所属竞赛"
    )

    name = models.CharField(max_length=255, verbose_name="本次赛事名称")  # 如 "2024春季选拔赛"
    start_time = models.DateTimeField(verbose_name="报名开始时间")
    end_time = models.DateTimeField(verbose_name="报名结束时间")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="状态")

    # --- 归档后保留的统计数据 (快照) ---
    final_participants_count = models.IntegerField(default=0, verbose_name="最终参赛人数(归档后)")
    final_winners_count = models.IntegerField(default=0, verbose_name="最终获奖人数(归档后)")

    class Meta:
        db_table = 'sys_competition_event'
        verbose_name = "赛事场次"

    def __str__(self):
        return f"{self.competition.title} - {self.name}"