from rest_framework import serializers
from .models import Award
from userManage.serializers import UserSerializer


class AwardSerializer(serializers.ModelSerializer):
    # 用于展示详细信息
    competition_name = serializers.ReadOnlyField(source='competition.title')
    certificate_no = serializers.ReadOnlyField(source='certificate.cert_no')

    # 获取学生和老师的简要信息列表
    participant_details = UserSerializer(source='participants', many=True, read_only=True)
    instructor_details = UserSerializer(source='instructors', many=True, read_only=True)

    class Meta:
        model = Award
        fields = [
            'id', 'competition', 'competition_name',
            'certificate', 'certificate_no',
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