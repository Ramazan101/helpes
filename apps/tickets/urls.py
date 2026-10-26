from django.urls import path
from . import views_admin, views_public, views_tech

app_name = "tickets"

urlpatterns = [
    # 1. Интерфейс сотрудника (без авторизации)
    path("", views_public.public_ticket_create, name="public_create"),
    path("success/<str:ticket_number>/", views_public.public_ticket_success, name="public_success"),
    # 2. Интерфейс технического специалиста
    path("tech/queue/", views_tech.tech_queue, name="tech_queue"),
    path("tech/tickets/<str:ticket_number>/", views_tech.tech_ticket_detail, name="tech_detail"),
    path("tech/tickets/<str:ticket_number>/claim/", views_tech.tech_claim_ticket, name="tech_claim"),
    path("tech/tickets/<str:ticket_number>/status/", views_tech.tech_update_status, name="tech_update_status"),
    path("tech/tickets/<str:ticket_number>/comment/", views_tech.tech_add_comment, name="tech_add_comment"),
    path("tech/tickets/<str:ticket_number>/return/", views_tech.tech_return_to_queue, name="tech_return_to_queue"),
    # 3. Интерфейс администратора
    path("manage/tickets/", views_admin.admin_ticket_list, name="admin_ticket_list"),
    path("manage/tickets/<str:ticket_number>/", views_admin.admin_ticket_detail, name="admin_ticket_detail"),
    path("manage/tickets/<str:ticket_number>/assign/", views_admin.admin_assign_ticket_view, name="admin_assign_ticket"),
    path("manage/tickets/<str:ticket_number>/reopen/", views_admin.admin_reopen_ticket_view, name="admin_reopen_ticket"),
    path("manage/categories/", views_admin.admin_categories, name="admin_categories"),
    path("manage/categories/<int:pk>/edit/", views_admin.admin_category_edit, name="admin_category_edit"),
]
