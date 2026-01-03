from django.urls import path
from .views import (
    RegisterView,
    LoginTokenObtainPairView,
    UserListView, UserDetailView, UserMenuView, ChangePasswordView, UserRoleStatisticsView, RoleListView
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
    path('menu/',UserMenuView.as_view(), name='user_menu'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('statistic/', UserRoleStatisticsView.as_view(), name='statistic'),
    path('roles/', RoleListView.as_view(), name='role_statistics'),
]