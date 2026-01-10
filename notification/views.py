from django.shortcuts import render

# Create your views here.
from notifications.models import Notification
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from .serializers import NotificationSerializer


class NotificationViewSet(mixins.ListModelMixin,
                          mixins.UpdateModelMixin,
                          mixins.DestroyModelMixin,
                          viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        # 只看当前用户的消息
        return self.request.user.notifications.all()

    @action(detail=False, methods=['get'],url_path='unread-count')
    def unread_count(self, request):
        """获取未读消息数: /notification/info/unread-count/"""
        count = self.request.user.notifications.unread().count()
        return Response({'unread_count': count})

    @action(detail=True, methods=['post'],url_path='mark-as-read')
    def mark_as_read(self, request, pk=None):
        """标记单条已读: /notification/info/{id}/mark-as-read/"""
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'status': 'marked as read'})

    @action(detail=False, methods=['post'], url_path='mark-all-as-read')
    def mark_all_as_read(self, request):
        """全部标记已读: /notification/info/mark-all-as-read/"""
        self.request.user.notifications.mark_all_as_read()
        return Response({'status': 'all marked as read'})