from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from competitions.models import CompetitionEvent


class Team(models.Model):
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('submitted', '待审核'),
        ('approved', '已获奖/审核通过'),  # 只有这个状态会生成 Award
        ('rejected', '驳回'),
    )

    # 1. 关联发布的赛事
    event = models.ForeignKey(
        'competitions.CompetitionEvent',
        on_delete=models.CASCADE,
        related_name='teams'
    )

    # 2. 人员结构 (与 Award 对应)
    name = models.CharField(max_length=100, verbose_name="团队名称")
    leader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='led_teams')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='joined_teams', blank=True)
    teachers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='guided_teams', blank=True)
    works = models.FileField(upload_to='temp/team_works/%Y/', null=True, blank=True)

    # 3. 拟申报奖项 (审核通过后，这将变为 Award.award_level)
    applied_award_level = models.CharField(max_length=50, verbose_name="申请奖项等级", help_text="如：一等奖")

    # 4. 证明材料 (审核通过后，这将生成 Certificate 对象)
    attachment = models.FileField(upload_to='temp/temp_certs/%Y/', verbose_name="获奖证书文件", null=True, blank=True)
    temp_cert_no = models.CharField(max_length=100, blank=True, null=True, verbose_name="待核实证书编号")

    # 5. 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # 记录是否已经转化为了Award，防止重复点击
    converted_award = models.OneToOneField(
        'award.Award',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="关联的正式奖项记录"
    )

    def __str__(self):
        return self.name