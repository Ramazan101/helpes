"""Открытый интерфейс сотрудника для подачи заявки без авторизации."""
from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import PublicTicketForm, TicketItemFormSet
from .models import Ticket
from .services import create_public_ticket


def _is_rate_limited(request) -> bool:
    limit = getattr(settings, "PUBLIC_FORM_RATE_LIMIT", 5)
    if limit <= 0:
        return False
    ip = request.META.get("REMOTE_ADDR", "local")
    key = f"public_ticket_rate:{ip}"
    current = cache.get(key, 0)
    if current >= limit:
        return True
    cache.set(key, current + 1, timeout=60)
    return False


def public_ticket_create(request):
    if request.method == "POST":
        form = PublicTicketForm(request.POST)
        formset = TicketItemFormSet(request.POST, prefix="items")
        if _is_rate_limited(request):
            messages.error(
                request,
                "Превышен лимит отправки заявок в минуту. Пожалуйста, подождите немного и попробуйте снова.",
            )
        elif form.is_valid() and formset.is_valid():
            try:
                ticket = create_public_ticket(
                    employee_name=form.cleaned_data["employee_name"],
                    location=None,
                    custom_location=form.cleaned_data["custom_location"],
                    short_description=form.cleaned_data["short_description"],
                    detailed_description="",
                    items_data=formset.cleaned_data,
                )
                submitted = list(request.session.get("submitted_tickets", []))
                if ticket.ticket_number not in submitted:
                    submitted.append(ticket.ticket_number)
                request.session["submitted_tickets"] = submitted[-20:]
                token = signing.dumps(ticket.ticket_number, salt="helpes.public.success")
                return redirect(f"{reverse('tickets:public_success', args=[ticket.ticket_number])}?t={token}")
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки в форме и проверьте количество оборудования.")
    else:
        form = PublicTicketForm()
        formset = TicketItemFormSet(prefix="items")

    return render(
        request,
        "public/ticket_create.html",
        {"form": form, "formset": formset},
    )


def public_ticket_success(request, ticket_number: str):
    submitted = request.session.get("submitted_tickets", [])
    token = request.GET.get("t", "")
    token_valid = False
    if token:
        try:
            unsigned = signing.loads(token, salt="helpes.public.success", max_age=3600)
            token_valid = unsigned == ticket_number
        except signing.BadSignature:
            token_valid = False

    if ticket_number not in submitted and not token_valid and not request.user.is_authenticated:
        raise Http404("Страница подтверждения доступна только сразу после отправки заявки.")

    ticket = get_object_or_404(
        Ticket.objects.select_related("location", "location__floor", "location__floor__building")
        .prefetch_related("items__category"),
        ticket_number=ticket_number,
    )
    return render(request, "public/ticket_success.html", {"ticket": ticket})
