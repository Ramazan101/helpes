"""Интерфейс технического специалиста: очередь, карточка заявки, взятие в работу и смена статусов."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import tech_required
from .forms import ReturnToQueueForm, TechStatusUpdateForm, TicketCommentForm
from .models import Ticket
from .services import (
    TicketConcurrencyError,
    add_ticket_comment,
    claim_ticket,
    return_ticket_to_queue,
    update_ticket_status,
)


@tech_required
def tech_queue(request):
    scope = request.GET.get("scope", "available")
    status_filter = request.GET.get("status", "")
    search_q = request.GET.get("q", "").strip()

    qs = (
        Ticket.objects.select_related("location", "location__floor", "location__floor__building", "assigned_to")
        .prefetch_related("items__category")
    )

    if scope == "mine":
        qs = qs.filter(assigned_to=request.user).exclude(status=Ticket.Status.DONE)
    elif scope == "done":
        qs = qs.filter(status=Ticket.Status.DONE)
    elif scope == "all_open":
        qs = qs.exclude(status=Ticket.Status.DONE)
    else:
        # По умолчанию: свободные и новые заявки + назначенные текущему технику
        scope = "available"
        qs = qs.filter(Q(assigned_to__isnull=True) | Q(assigned_to=request.user)).exclude(status=Ticket.Status.DONE)

    if status_filter in dict(Ticket.Status.choices):
        qs = qs.filter(status=status_filter)

    if search_q:
        qs = qs.filter(
            Q(ticket_number__icontains=search_q)
            | Q(employee_name__icontains=search_q)
            | Q(short_description__icontains=search_q)
            | Q(custom_location__icontains=search_q)
            | Q(location__name__icontains=search_q)
        )

    counts = {
        "unassigned": Ticket.objects.filter(assigned_to__isnull=True).exclude(status=Ticket.Status.DONE).count(),
        "mine": Ticket.objects.filter(assigned_to=request.user).exclude(status=Ticket.Status.DONE).count(),
        "all_open": Ticket.objects.exclude(status=Ticket.Status.DONE).count(),
    }

    return render(
        request,
        "tech/queue.html",
        {
            "tickets": qs,
            "scope": scope,
            "status_filter": status_filter,
            "search_q": search_q,
            "counts": counts,
            "status_choices": Ticket.Status.choices,
        },
    )


@tech_required
def tech_ticket_detail(request, ticket_number: str):
    ticket = get_object_or_404(
        Ticket.objects.select_related("location", "location__floor", "location__floor__building", "assigned_to")
        .prefetch_related("items__category", "comments__author", "history__actor", "history__old_assignee", "history__new_assignee"),
        ticket_number=ticket_number,
    )
    status_form = TechStatusUpdateForm(
        initial={"status": ticket.status, "resolution_summary": ticket.resolution_summary}
    )
    comment_form = TicketCommentForm()
    return_form = ReturnToQueueForm()
    can_manage_ticket = request.user.is_admin_role or ticket.assigned_to_id == request.user.id

    return render(
        request,
        "tech/ticket_detail.html",
        {
            "ticket": ticket,
            "status_form": status_form,
            "comment_form": comment_form,
            "return_form": return_form,
            "can_manage_ticket": can_manage_ticket,
        },
    )


@tech_required
@require_POST
def tech_claim_ticket(request, ticket_number: str):
    try:
        ticket = claim_ticket(ticket_number=ticket_number, tech_user=request.user)
        messages.success(request, f"Заявка {ticket.ticket_number} закреплена за вами и переведена в статус «В работе».")
    except TicketConcurrencyError as exc:
        messages.error(request, str(exc))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("tickets:tech_detail", ticket_number=ticket_number)


@tech_required
@require_POST
def tech_update_status(request, ticket_number: str):
    form = TechStatusUpdateForm(request.POST)
    if form.is_valid():
        try:
            ticket = update_ticket_status(
                ticket_number=ticket_number,
                actor=request.user,
                new_status=form.cleaned_data["status"],
                resolution_summary=form.cleaned_data["resolution_summary"],
                comment_text=form.cleaned_data["comment_text"],
            )
            messages.success(request, f"Статус заявки {ticket.ticket_number} обновлён на «{ticket.get_status_display()}».")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, "Проверьте правильность заполнения формы смены статуса.")
    return redirect("tickets:tech_detail", ticket_number=ticket_number)


@tech_required
@require_POST
def tech_add_comment(request, ticket_number: str):
    form = TicketCommentForm(request.POST)
    if form.is_valid():
        try:
            add_ticket_comment(
                ticket_number=ticket_number,
                author=request.user,
                body=form.cleaned_data["body"],
            )
            messages.success(request, "Комментарий добавлен.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, "Введите текст комментария.")
    return redirect("tickets:tech_detail", ticket_number=ticket_number)


@tech_required
@require_POST
def tech_return_to_queue(request, ticket_number: str):
    form = ReturnToQueueForm(request.POST)
    if form.is_valid():
        try:
            return_ticket_to_queue(
                ticket_number=ticket_number,
                actor=request.user,
                reason=form.cleaned_data["reason"],
            )
            messages.warning(request, f"Заявка {ticket_number} возвращена в общую очередь.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, "Укажите причину возврата заявки в очередь.")
    return redirect("tickets:tech_detail", ticket_number=ticket_number)
