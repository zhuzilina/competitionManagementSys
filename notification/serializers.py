from rest_framework import serializers
from notifications.models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    # 格式化动作描述
    actor_name = serializers.CharField(source='actor.username', read_only=True)
    target_object = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'actor_name', 'verb', 'unread', 'timestamp', 'target_object', 'description']

    def get_target_object(self, obj):
        # 如果有关联对象（如 Award），返回它的基本信息或 ID
        if obj.target:
            return {"id": obj.target.id, "type": obj.target.__class__.__name__}
        return None