from django.conf import settings
from django.db import models
from django_fsm import FSMField, transition


class AwardApplication(models.Model):
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # 1. 证书文件直接通过 FileField 处理
    cert_image = models.ImageField(upload_to='temp/apply/%Y/%m/', verbose_name="证书临时文件")
    cert_no = models.CharField(max_length=100, verbose_name="申请证书编号")
    award_level = models.CharField(max_length=50, verbose_name="获奖等级")
    award_date = models.DateField(verbose_name="获奖日期")

    # 2. 竞赛和获奖详情存入 JSON
    # 结构示例: {"comp_title": "ACM", "year": 2024, "category_id": 1, "level_id": 2, "participant_ids": [1,2]}
    payload = models.JSONField(verbose_name="申请详情数据")

    status = FSMField(default='pending', verbose_name="审批状态")
    created_at = models.DateTimeField(auto_now_add=True)

    @transition(field=status, source='pending', target='approved')
    def approve(self):
        pass

    @transition(field=status, source='pending', target='rejected')
    def reject(self):
        pass