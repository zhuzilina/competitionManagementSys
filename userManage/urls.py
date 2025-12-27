from django.urls import path
from .views import (
    RegisterView,
    LoginTokenObtainPairView,
    UserListView, UserDetailView
)
from rest_framework_simplejwt.views import (
    TokenRefreshView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('login/', LoginTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/<int:user_id>/', UserDetailView.as_view(), name='user_detail'),
]