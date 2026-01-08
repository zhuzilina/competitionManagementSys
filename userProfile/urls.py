from django.urls import path
from .views import MyProfileView, ProfileSearchByFieldNameView, ProfileRetrieveByUserIdView

urlpatterns = [
    path('view/',
         MyProfileView.as_view(),
         name='profile'),
    path('search/',
         ProfileSearchByFieldNameView.as_view(), ),
    path('by-user-id/<str:user_id>/', ProfileRetrieveByUserIdView.as_view(), ),
]