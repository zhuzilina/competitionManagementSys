from rest_framework import serializers
from .models import Competition, CompetitionCategory, CompetitionLevel, CompetitionEvent


class CompetitionSerializer(serializers.ModelSerializer):
    """
    竞赛信息管理的序列化器
    """
    category_name = serializers.ReadOnlyField(source='category.name')
    level_name = serializers.ReadOnlyField(source='level.name')
    creator_name = serializers.ReadOnlyField(source='creator.username')

    class Meta:
        model = Competition
        fields = '__all__'

        read_only_fields = ['creator', 'created_at']


class CompetitionLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetitionLevel
        fields = '__all__'  # 或者指定具体字段 ['id', 'name', 'description']


class CompetitionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetitionCategory
        fields = '__all__'


class CompetitionEventSerializer(serializers.ModelSerializer):
    competition_title = serializers.ReadOnlyField(source='competition.title')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CompetitionEvent
        fields = [
            'id', 'competition', 'competition_title', 'name',
            'start_time', 'end_time', 'status', 'status_display',
            'final_participants_count', 'final_winners_count'
        ]
        # 将 status 加入只读，强制走模型默认值或后端逻辑
        read_only_fields = ['status', 'final_participants_count', 'final_winners_count']