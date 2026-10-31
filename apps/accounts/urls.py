from django.urls import path
from . import views, views_api

app_name = "accounts"

urlpatterns = [
    path("accounts/login/", views.HelpesLoginView.as_view(), name="login"),
    path("accounts/logout/", views.HelpesLogoutView.as_view(), name="logout"),
    path("accounts/api/session/", views_api.session_status_api, name="api_session_status"),
    path("manage/users/", views.user_list, name="user_list"),
    path("manage/users/add/", views.user_add, name="user_add"),
    path("manage/users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("manage/users/<int:pk>/deactivate/", views.user_deactivate, name="user_deactivate"),
]
