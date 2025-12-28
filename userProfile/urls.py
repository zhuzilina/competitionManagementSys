from django.urls import path
from .views import MyProfileView, ProfileSearchByFieldNameView

urlpatterns = [
    path('view/',
         MyProfileView.as_view(),
         name='profile'),
    path('search/',
         ProfileSearchByFieldNameView.as_view(), )
]