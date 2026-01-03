from django.db import models
import uuid
import os

from django.utils import timezone


# Create your models here.
def certificate_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    # 此时 id 已经由 UUIDField 的 default 产生
    new_filename = f'{instance.id}.{ext}'

    # 关键修改：直接使用 timezone.now()
    # 因为上传那一刻的时间基本上就是创建时间
    date_path = timezone.now().strftime('%Y/%m')

    return os.path.join('certificate', date_path, new_filename)

class Certificate(models.Model):
    # 使用uuid作为证书id
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # 证书编号
    cert_no = models.CharField(max_length=100,unique=True,verbose_name="证书编号")
    # 证书文件
    image_uri = models.ImageField(upload_to=certificate_upload_path, verbose_name="证书图片路径")
    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'certificate'
        verbose_name = "证书信息"

    def __str__(self):
        return self.cert_no