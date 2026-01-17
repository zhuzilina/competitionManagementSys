import os
from celery import Celery

# 设置 Django 默认配置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'competitionManagementSys.settings')

app = Celery('competitionManagementSys')

# 使用字符串可以防止 worker 在 Windows 上启动失败
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现每个 app 下的 tasks.py
app.autodiscover_tasks()