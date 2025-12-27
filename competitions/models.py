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