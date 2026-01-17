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


class AwardImportTask(models.Model):
    """导入任务批次表"""
    STATUS_CHOICES = (
        ('pending', '待处理'),  # 刚上传，解析中
        ('correcting', '待修正'),  # 解析完成，等待用户在前端修复错误
        ('finished', '已完成'),  # 全部入库
        ('failed', '失败'),
    )
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    file_name = models.CharField(max_length=255, verbose_name="原始文件名")
    created_at = models.DateTimeField(auto_now_add=True)


class AwardImportItem(models.Model):
    """
    导入项详情表（每一行 Excel 数据对应一条记录）
    核心思想：raw_data 存原始文本，parsed_data 存解析后的结构化数据
    """
    task = models.ForeignKey(AwardImportTask, related_name='items', on_delete=models.CASCADE)

    # 1. 原始数据快照 (方便前端展示 "你原来填的是啥")
    raw_competition = models.CharField(max_length=255, blank=True)
    raw_participants = models.TextField(blank=True)  # "张三, 李四"
    raw_instructors = models.TextField(blank=True)
    award_level = models.CharField(max_length=50, blank=True)
    award_date = models.DateField(null=True, blank=True)
    cert_no = models.CharField(max_length=100, blank=True)

    # 2. 解析状态
    is_valid = models.BooleanField(default=False)  # 只有当所有字段都匹配成功时为 True
    error_msg = models.TextField(blank=True)  # 汇总错误信息，如 "竞赛未找到; 张三有重名"

    # 3. 解析结果 (JSON)
    # 结构示例：
    # {
    #   "status": "success" | "multiple" | "not_found",
    #   "origin_text": "张三",
    #   "selected_id": 101,  <-- 前端修正时回填这个字段
    #   "options": [ {"id": 101, "name": "张三", "dept": "计院"}, ... ]
    # }
    competition_analysis = models.JSONField(default=dict)
    participants_analysis = models.JSONField(default=list)
    instructors_analysis = models.JSONField(default=list)

    class Meta:
        ordering = ['id']