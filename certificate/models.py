from django.db import models
import uuid
import os

# Create your models here.
def certificate_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f'{instance.id}.{ext}'
    return os.path.join('certificate',
                        instance.created_at.strftime('%Y/%m'),
                        filename
                        )

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