from django.urls import path
from . import views

app_name = "locations"

urlpatterns = [
    path("", views.admin_locations, name="admin_locations"),
    path("buildings/add/", views.building_add, name="building_add"),
    path("buildings/<int:pk>/edit/", views.building_edit, name="building_edit"),
    path("floors/add/", views.floor_add, name="floor_add"),
    path("floors/<int:pk>/edit/", views.floor_edit, name="floor_edit"),
    path("rooms/add/", views.room_add, name="room_add"),
    path("rooms/<int:pk>/edit/", views.room_edit, name="room_edit"),
]
