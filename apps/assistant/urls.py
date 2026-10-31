from django.urls import path
from . import views

app_name = "assistant"

urlpatterns = [
    path("", views.assistant_chat_page, name="chat_page"),
    path("widget/", views.assistant_widget_view, name="widget_window"),
    path("api/chat/", views.assistant_chat_api, name="chat_api"),
]

