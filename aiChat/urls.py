from django.urls import path, include

from .views import AIStreamChatView,ChatHistoryView
# 访问接口 /ai/chat/
urlpatterns = [
    path('chat/', AIStreamChatView.as_view(), name='chat'),
    path('history/', ChatHistoryView.as_view(), name='history'),
]