"""Представления авторизации и управления пользователями."""
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.tickets.models import Ticket
from apps.tickets.services import deactivate_user_and_redistribute_tickets
from .forms import DeactivateUserForm, HelpesLoginForm, StaffUserCreateForm, StaffUserUpdateForm
from .models import User
from .permissions import admin_required


class HelpesLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = HelpesLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if getattr(user, "is_admin_role", False):
            return reverse("tickets:admin_ticket_list")
        return reverse("tickets:tech_queue")


class HelpesLogoutView(LogoutView):
    next_page = "accounts:login"


@admin_required
def user_list(request):
    users = User.objects.annotate(
        open_tickets_count=Count(
            "assigned_tickets",
            filter=~Q(assigned_tickets__status=Ticket.Status.DONE),
        )
    ).order_by("-is_active", "role", "username")
    return render(request, "manage/user_list.html", {"users": users})


@admin_required
def user_add(request):
    if request.method == "POST":
        form = StaffUserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            messages.success(request, f"Учётная запись «{new_user.display_name}» успешно создана.")
            return redirect("accounts:user_list")
    else:
        form = StaffUserCreateForm()
    return render(request, "manage/user_form.html", {"form": form, "is_create": True})


@admin_required
def user_edit(request, pk: int):
    target_user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = StaffUserUpdateForm(request.POST, instance=target_user)
        if form.is_valid():
            # Если администратор снимает галочку is_active, а у пользователя есть открытые заявки —
            # перенаправляем на безопасный мастер деактивации.
            if not form.cleaned_data["is_active"] and target_user.assigned_tickets.exclude(status=Ticket.Status.DONE).exists():
                messages.warning(
                    request,
                    "У специалиста есть незавершённые заявки. Пожалуйста, укажите способ их перераспределения.",
                )
                return redirect("accounts:user_deactivate", pk=target_user.pk)
            form.save()
            messages.success(request, f"Данные пользователя «{target_user.display_name}» обновлены.")
            return redirect("accounts:user_list")
    else:
        form = StaffUserUpdateForm(instance=target_user)
    return render(
        request,
        "manage/user_form.html",
        {"form": form, "target_user": target_user, "is_create": False},
    )


@admin_required
def user_deactivate(request, pk: int):
    target_user = get_object_or_404(User, pk=pk)
    if target_user.pk == request.user.pk:
        messages.error(request, "Нельзя деактивировать собственную учётную запись.")
        return redirect("accounts:user_list")

    open_tickets = list(
        target_user.assigned_tickets.exclude(status=Ticket.Status.DONE)
        .select_related("location", "location__floor")
        .order_by("-created_at")
    )

    if request.method == "POST":
        form = DeactivateUserForm(request.POST, user_to_deactivate=target_user)
        if form.is_valid():
            new_assignee = (
                form.cleaned_data["target_tech"]
                if form.cleaned_data["action_mode"] == DeactivateUserForm.ACTION_REASSIGN
                else None
            )
            processed_count = deactivate_user_and_redistribute_tickets(
                target_user=target_user,
                actor=request.user,
                new_assignee=new_assignee,
            )
            messages.success(
                request,
                f"Учётная запись «{target_user.display_name}» деактивирована. "
                f"Обработано открытых заявок: {processed_count}. История работ сохранена.",
            )
            return redirect("accounts:user_list")
    else:
        form = DeactivateUserForm(user_to_deactivate=target_user)

    return render(
        request,
        "manage/user_deactivate.html",
        {
            "target_user": target_user,
            "open_tickets": open_tickets,
            "form": form,
        },
    )
