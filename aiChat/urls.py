from django.urls import path, include

from .views import AIStreamChatView
# 访问接口 /ai/chat/
urlpatterns = [
    path('chat/', AIStreamChatView.as_view(), name='chat'),
]