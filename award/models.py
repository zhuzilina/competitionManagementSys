# Create your models here.
from django.db import models
from django.conf import settings

class Award(models.Model):
    # 1. 关联竞赛 (多对一：一条获奖记录对应一个竞赛)
    competition = models.ForeignKey(
        'competitions.Competition',
        on_delete=models.PROTECT,
        related_name="awards",
        verbose_name="所属竞赛"
    )

    # 2. 关联竞赛活动 (多对一：一条获奖记录对应一个竞赛活动)
    event = models.ForeignKey(
        'competitions.CompetitionEvent',  # 假设你的发布模型叫此名
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="awards",
        verbose_name="所属赛事场次"
    )

    # 3. 关联证书 (一对一：通常一张获奖记录对应一张唯一的证书文件)
    # 使用 OneToOneField 确保证书不被重复绑定
    certificate = models.OneToOneField(
        'certificate.Certificate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="award",
        verbose_name="获奖证书"
    )

    # 4. 关联人员 (多对多)
    # 参与学生
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="student_awards",
        verbose_name="参赛学生"
    )
    # 指导老师
    instructors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="teacher_awards",
        verbose_name="指导老师"
    )

    # 5. 获奖信息
    award_level = models.CharField(max_length=50, verbose_name="获奖等级") # 如：一等奖、金奖
    award_date = models.DateField(verbose_name="获奖日期")

    # 6. 审计信息
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="managed_awards",
        verbose_name="录入人"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sys_award'
        verbose_name = "获奖信息"
        ordering = ['-award_date']

    def __str__(self):
        return f"{self.competition.title} - {self.award_level}"