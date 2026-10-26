"""Интерфейс администратора: диспетчеризация заявок и справочник категорий оборудования."""
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.accounts.permissions import admin_required
from .forms import AdminAssignTicketForm, AdminReopenTicketForm, EquipmentCategoryForm
from .models import EquipmentCategory, Ticket
from .services import admin_assign_ticket, admin_reopen_ticket


@admin_required
def admin_ticket_list(request):
    filter_mode = request.GET.get("filter", "all")
    status_filter = request.GET.get("status", "")
    tech_filter = request.GET.get("tech", "")

    qs = (
        Ticket.objects.select_related("location", "location__floor", "location__floor__building", "assigned_to")
        .prefetch_related("items__category")
    )

    stale_cutoff = timezone.now() - timedelta(hours=getattr(settings, "STALE_TICKET_HOURS", 24))

    if filter_mode == "unassigned":
        qs = qs.filter(assigned_to__isnull=True).exclude(status=Ticket.Status.DONE)
    elif filter_mode == "stale":
        qs = qs.exclude(status=Ticket.Status.DONE).filter(updated_at__lt=stale_cutoff)

    if status_filter in dict(Ticket.Status.choices):
        qs = qs.filter(status=status_filter)

    if tech_filter.isdigit():
        qs = qs.filter(assigned_to_id=int(tech_filter))

    techs = User.objects.filter(role__in=[User.Role.TECH, User.Role.ADMIN]).order_by("-is_active", "username")

    stats = {
        "total": Ticket.objects.count(),
        "unassigned": Ticket.objects.filter(assigned_to__isnull=True).exclude(status=Ticket.Status.DONE).count(),
        "stale": Ticket.objects.exclude(status=Ticket.Status.DONE).filter(updated_at__lt=stale_cutoff).count(),
        "done": Ticket.objects.filter(status=Ticket.Status.DONE).count(),
    }

    return render(
        request,
        "manage/ticket_list.html",
        {
            "tickets": qs,
            "filter_mode": filter_mode,
            "status_filter": status_filter,
            "tech_filter": tech_filter,
            "techs": techs,
            "stats": stats,
            "status_choices": Ticket.Status.choices,
        },
    )


@admin_required
def admin_ticket_detail(request, ticket_number: str):
    ticket = get_object_or_404(
        Ticket.objects.select_related("location", "location__floor", "location__floor__building", "assigned_to")
        .prefetch_related("items__category", "comments__author", "history__actor", "history__old_assignee", "history__new_assignee"),
        ticket_number=ticket_number,
    )
    assign_form = AdminAssignTicketForm(initial={"assigned_to": ticket.assigned_to_id})
    reopen_form = AdminReopenTicketForm(initial={"assigned_to": ticket.assigned_to_id})
    return render(
        request,
        "manage/ticket_detail.html",
        {
            "ticket": ticket,
            "assign_form": assign_form,
            "reopen_form": reopen_form,
        },
    )


@admin_required
@require_POST
def admin_assign_ticket_view(request, ticket_number: str):
    form = AdminAssignTicketForm(request.POST)
    if form.is_valid():
        try:
            ticket = admin_assign_ticket(
                ticket_number=ticket_number,
                admin_user=request.user,
                new_assignee=form.cleaned_data["assigned_to"],
                note=form.cleaned_data["note"],
            )
            if ticket.assigned_to:
                messages.success(
                    request,
                    f"Заявка {ticket.ticket_number} назначена специалисту {ticket.assigned_to.display_name}.",
                )
            else:
                messages.warning(request, f"Заявка {ticket.ticket_number} возвращена в общую очередь.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, "Не удалось изменить назначение заявки.")
    return redirect("tickets:admin_ticket_detail", ticket_number=ticket_number)


@admin_required
@require_POST
def admin_reopen_ticket_view(request, ticket_number: str):
    form = AdminReopenTicketForm(request.POST)
    if form.is_valid():
        try:
            ticket = admin_reopen_ticket(
                ticket_number=ticket_number,
                admin_user=request.user,
                reason=form.cleaned_data["reason"],
                assignee=form.cleaned_data["assigned_to"],
            )
            messages.success(request, f"Заявка {ticket.ticket_number} повторно открыта. Предыдущая история сохранена.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, "Укажите причину повторного открытия заявки.")
    return redirect("tickets:admin_ticket_detail", ticket_number=ticket_number)


@admin_required
def admin_categories(request):
    if request.method == "POST":
        form = EquipmentCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Категория «{cat.name}» добавлена и доступна сотрудникам.")
            return redirect("tickets:admin_categories")
    else:
        form = EquipmentCategoryForm()

    categories = EquipmentCategory.objects.all()
    return render(
        request,
        "manage/category_list.html",
        {"categories": categories, "form": form},
    )


@admin_required
def admin_category_edit(request, pk: int):
    category = get_object_or_404(EquipmentCategory, pk=pk)
    if request.method == "POST":
        form = EquipmentCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Категория «{category.name}» обновлена.")
            return redirect("tickets:admin_categories")
    else:
        form = EquipmentCategoryForm(instance=category)
    return render(
        request,
        "manage/location_edit.html",
        {"form": form, "title": f"Редактирование категории: {category.name}"},
    )
