from rest_framework import serializers
from .models import Certificate  # 建议将类名从 Competition 改为 Certificate

class CertificateSerializer(serializers.ModelSerializer):
    # 使用 ImageField 时，DRF 会自动返回完整的 URL 路径
    class Meta:
        model = Certificate
        fields = ['id', 'cert_no', 'image_uri', 'created_at']
        read_only_fields = ['id', 'created_at']