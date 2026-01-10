from django.contrib.auth import get_user_model
from rest_framework import serializers

from certificate.models import Certificate
from userProfile.serializers import UserDetailSerializer
from .models import Award

User = get_user_model()


class CertificateSerializer(serializers.ModelSerializer):
    """用于展示证书的详细信息"""

    class Meta:
        model = Certificate
        fields = ['id', 'cert_no', 'image_uri']


class AwardSerializer(serializers.ModelSerializer):
    # 1. 证书关联字段 (用于写入：接受 UUID 字符串)
    certificate = serializers.PrimaryKeyRelatedField(
        queryset=Certificate.objects.all(),
        required=False,
        allow_null=True
    )

    # 2. 证书详情字段 (用于展示：返回编号和图片地址)
    certificate_details = CertificateSerializer(source='certificate', read_only=True)

    # 竞赛名称快捷字段
    competition_name = serializers.ReadOnlyField(source='competition.title')

    # 用户关联字段（保持你之前的 SlugRelatedField 设置）
    participants = serializers.SlugRelatedField(
        many=True,
        queryset=User.objects.all(),
        slug_field='user_id'
    )
    instructors = serializers.SlugRelatedField(
        many=True,
        queryset=User.objects.all(),
        slug_field='user_id'
    )

    # --- 4. 参与者 & 指导老师 (Profile 详情展示) ---
    participant_details = UserDetailSerializer(source='participants', many=True, read_only=True)
    instructor_details = UserDetailSerializer(source='instructors', many=True, read_only=True)

    class Meta:
        model = Award
        fields = [
            'id', 'competition', 'competition_name',
            'certificate', 'certificate_details',  # 包含这两个字段
            'participants', 'participant_details',
            'instructors', 'instructor_details',
            'award_level', 'award_date', 'creator'
        ]
        read_only_fields = ['creator']


class AwardInfoSerializer(serializers.ModelSerializer):
    """用于报表内部展示的获奖简要信息"""
    competition_name = serializers.ReadOnlyField(source='competition.title')

    class Meta:
        model = Award
        fields = ['id', 'competition_name', 'award_level', 'award_date']


class AwardReportSerializer(serializers.Serializer):
    """通用的报表序列化器"""
    user_id = serializers.CharField()
    real_name = serializers.CharField()
    department = serializers.CharField()
    major = serializers.CharField()
    clazz = serializers.CharField()
    title = serializers.CharField()  # 职称
    awards = AwardInfoSerializer(many=True)  # 该成员关联的所有奖项