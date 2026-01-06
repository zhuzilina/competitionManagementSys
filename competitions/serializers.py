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
    # 嵌套显示基础竞赛的标题，方便前端展示
    competition_title = serializers.ReadOnlyField(source='competition.title')
    competition_description = serializers.ReadOnlyField(source='competition.description')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CompetitionEvent
        fields = [
            'id', 'competition', 'competition_title','competition_description', 'name',
            'start_time', 'end_time', 'status', 'status_display',
            'final_participants_count', 'final_winners_count'
        ]
        # 统计数据由系统自动计算，不应通过接口直接修改
        read_only_fields = ['final_participants_count', 'final_winners_count']