from rest_framework import serializers
from .models import Competition,CompetitionCategory,CompetitionLevel

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