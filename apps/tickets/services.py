"""Транзакционный сервисный слой бизнес-логики обработки заявок Helpes."""
import uuid
from typing import Iterable, Optional
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from .models import EquipmentCategory, Ticket, TicketComment, TicketHistory, TicketItem


class TicketConcurrencyError(Exception):
    """Возникает при попытке двух техников одновременно забрать одну свободную заявку."""


def create_public_ticket(
    *,
    employee_name: str,
    location,
    custom_location: str,
    short_description: str,
    detailed_description: str,
    items_data: Iterable[dict],
) -> Ticket:
    """
    Атомарно создаёт заявку от сотрудника, присваивает уникальный номер HELP-XXXXXX,
    суммирует дублирующиеся категории оборудования и записывает историю создания.
    """
    aggregated: dict[EquipmentCategory, int] = {}
    for row in items_data:
        if not row or row.get("DELETE"):
            continue
        category = row.get("category")
        quantity = row.get("quantity")
        if category is None or quantity is None:
            continue
        if int(quantity) < 1:
            raise ValidationError("Количество оборудования должно быть целым числом не меньше 1.")
        aggregated[category] = aggregated.get(category, 0) + int(quantity)


    with transaction.atomic():
        temp_number = f"TMP-{uuid.uuid4().hex[:12].upper()}"
        ticket = Ticket(
            ticket_number=temp_number,
            employee_name=employee_name.strip(),
            location=location,
            custom_location=(custom_location or "").strip(),
            short_description=short_description.strip(),
            detailed_description=(detailed_description or "").strip(),
            status=Ticket.Status.NEW,
        )
        ticket.full_clean()
        ticket.save()

        final_number = f"HELP-{ticket.id:06d}"
        Ticket.objects.filter(pk=ticket.pk).update(ticket_number=final_number)
        ticket.ticket_number = final_number

        for category, qty in aggregated.items():
            TicketItem.objects.create(ticket=ticket, category=category, quantity=qty)

        TicketHistory.objects.create(
            ticket=ticket,
            actor=None,
            action=TicketHistory.Action.CREATED,
            new_status=Ticket.Status.NEW,
            note=f"Заявка отправлена сотрудником {ticket.employee_name}.",
        )
        return ticket


def claim_ticket(*, ticket_number: str, tech_user: User) -> Ticket:
    """
    Безопасное взятие свободной заявки техником с блокировкой строки select_for_update().
    Гарантирует, что два специалиста не заберут одну и ту же заявку одновременно.
    """
    if not tech_user.is_active or not tech_user.is_tech_role:
        raise PermissionDenied("Только активный технический специалист может взять заявку в работу.")

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(ticket_number=ticket_number)
        if ticket.assigned_to_id is not None:
            raise TicketConcurrencyError(
                f"Заявка {ticket.ticket_number} уже назначена специалисту {ticket.assigned_to.display_name}."
            )
        if ticket.status == Ticket.Status.DONE:
            raise ValidationError("Нельзя взять в работу уже выполненную заявку.")

        old_status = ticket.status
        ticket.assigned_to = tech_user
        ticket.status = Ticket.Status.IN_PROGRESS
        ticket.save(update_fields=["assigned_to", "status", "updated_at"])

        TicketHistory.objects.create(
            ticket=ticket,
            actor=tech_user,
            action=TicketHistory.Action.CLAIMED,
            old_status=old_status,
            new_status=ticket.status,
            old_assignee=None,
            new_assignee=tech_user,
            note="Специалист самостоятельно забрал свободную заявку из очереди.",
        )
        return ticket


def update_ticket_status(
    *,
    ticket_number: str,
    actor: User,
    new_status: str,
    resolution_summary: str = "",
    comment_text: str = "",
) -> Ticket:
    """Смена статуса заявки техником или администратором с фиксацией результата ремонта."""
    if not actor.is_active or not actor.is_tech_role:
        raise PermissionDenied("Учётная запись неактивна или не имеет прав технической службы.")

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(ticket_number=ticket_number)
        if not actor.is_admin_role and ticket.assigned_to_id != actor.id:
            raise PermissionDenied("Вы можете менять статус только по назначенным на вас заявкам.")

        if new_status not in dict(Ticket.Status.choices):
            raise ValidationError("Некорректный статус заявки.")

        clean_resolution = (resolution_summary or "").strip()
        clean_comment = (comment_text or "").strip()

        if new_status == Ticket.Status.DONE and not (clean_resolution or ticket.resolution_summary):
            raise ValidationError("Для завершения заявки необходимо указать выполненные действия и результат ремонта.")

        if new_status == Ticket.Status.WAITING and not clean_comment:
            raise ValidationError("При переводе заявки в статус «Ожидает» укажите причину в комментарии.")

        old_status = ticket.status
        ticket.status = new_status
        if clean_resolution:
            ticket.resolution_summary = clean_resolution
        if new_status == Ticket.Status.DONE:
            ticket.completed_at = timezone.now()
            action_code = TicketHistory.Action.COMPLETED
        else:
            action_code = TicketHistory.Action.STATUS_CHANGED

        ticket.save()

        if clean_comment:
            TicketComment.objects.create(ticket=ticket, author=actor, body=clean_comment)

        TicketHistory.objects.create(
            ticket=ticket,
            actor=actor,
            action=action_code,
            old_status=old_status,
            new_status=new_status,
            old_assignee=ticket.assigned_to,
            new_assignee=ticket.assigned_to,
            note=clean_resolution or clean_comment or f"Статус изменён на «{ticket.get_status_display()}».",
        )
        return ticket


def add_ticket_comment(*, ticket_number: str, author: User, body: str) -> TicketComment:
    if not author.is_active or not author.is_tech_role:
        raise PermissionDenied("Учётная запись неактивна или не имеет прав технической службы.")
    clean_body = (body or "").strip()
    if not clean_body:
        raise ValidationError("Текст комментария не может быть пустым.")

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(ticket_number=ticket_number)
        comment = TicketComment.objects.create(ticket=ticket, author=author, body=clean_body)
        ticket.save(update_fields=["updated_at"])
        TicketHistory.objects.create(
            ticket=ticket,
            actor=author,
            action=TicketHistory.Action.COMMENT_ADDED,
            old_status=ticket.status,
            new_status=ticket.status,
            old_assignee=ticket.assigned_to,
            new_assignee=ticket.assigned_to,
            note=clean_body,
        )
        return comment


def return_ticket_to_queue(*, ticket_number: str, actor: User, reason: str) -> Ticket:
    """Возврат заявки в общую очередь (очистка исполнителя и перевод в статус «Новая»)."""
    if not actor.is_active or not actor.is_tech_role:
        raise PermissionDenied("Учётная запись неактивна или не имеет прав технической службы.")
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise ValidationError("Укажите причину возврата заявки в общую очередь.")

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(ticket_number=ticket_number)
        if not actor.is_admin_role and ticket.assigned_to_id != actor.id:
            raise PermissionDenied("Нельзя вернуть в очередь чужую заявку.")
        if ticket.status == Ticket.Status.DONE:
            raise ValidationError("Выполненную заявку нельзя вернуть в очередь без повторного открытия администратором.")

        old_status = ticket.status
        old_assignee = ticket.assigned_to
        ticket.assigned_to = None
        ticket.status = Ticket.Status.NEW
        ticket.save(update_fields=["assigned_to", "status", "updated_at"])

        TicketComment.objects.create(
            ticket=ticket,
            author=actor,
            body=f"Возврат в общую очередь: {clean_reason}",
        )
        TicketHistory.objects.create(
            ticket=ticket,
            actor=actor,
            action=TicketHistory.Action.RETURNED_TO_QUEUE,
            old_status=old_status,
            new_status=Ticket.Status.NEW,
            old_assignee=old_assignee,
            new_assignee=None,
            note=clean_reason,
        )
        return ticket


def admin_assign_ticket(
    *,
    ticket_number: str,
    admin_user: User,
    new_assignee: Optional[User],
    note: str = "",
) -> Ticket:
    """Назначение, переназначение заявки администратором или сброс в очередь."""
    if not admin_user.is_admin_role:
        raise PermissionDenied("Только администратор может назначать или переназначать заявки.")
    if new_assignee is not None and not new_assignee.is_active:
        raise ValidationError("Нельзя назначить заявку деактивированному специалисту.")

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(ticket_number=ticket_number)
        old_status = ticket.status
        old_assignee = ticket.assigned_to

        if new_assignee is None:
            ticket.assigned_to = None
            if ticket.status != Ticket.Status.DONE:
                ticket.status = Ticket.Status.NEW
            action = TicketHistory.Action.RETURNED_TO_QUEUE
        else:
            ticket.assigned_to = new_assignee
            if ticket.status == Ticket.Status.NEW:
                ticket.status = Ticket.Status.IN_PROGRESS
            action = TicketHistory.Action.ASSIGNED

        ticket.save(update_fields=["assigned_to", "status", "updated_at"])
        TicketHistory.objects.create(
            ticket=ticket,
            actor=admin_user,
            action=action,
            old_status=old_status,
            new_status=ticket.status,
            old_assignee=old_assignee,
            new_assignee=new_assignee,
            note=(note or "").strip() or (
                f"Назначен специалист {new_assignee.display_name}."
                if new_assignee else "Заявка возвращена в общую очередь администратором."
            ),
        )
        return ticket


def admin_reopen_ticket(*, ticket_number: str, admin_user: User, reason: str, assignee: Optional[User] = None) -> Ticket:
    """Повторное открытие выполненной заявки с сохранением предыдущего результата ремонта в истории."""
    if not admin_user.is_admin_role:
        raise PermissionDenied("Только администратор может повторно открывать завершённые заявки.")
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise ValidationError("Укажите причину повторного открытия заявки.")
    if assignee is not None and not assignee.is_active:
        raise ValidationError("Нельзя назначить заявку деактивированному специалисту.")

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(ticket_number=ticket_number)
        if ticket.status != Ticket.Status.DONE:
            raise ValidationError("Повторно открыть можно только выполненную заявку.")

        old_status = ticket.status
        old_assignee = ticket.assigned_to
        prev_resolution = ticket.resolution_summary
        completed_str = (
            f" ({timezone.localtime(ticket.completed_at):%d.%m.%Y %H:%M})"
            if ticket.completed_at
            else ""
        )

        ticket.assigned_to = assignee
        ticket.status = Ticket.Status.IN_PROGRESS if assignee else Ticket.Status.NEW
        ticket.completed_at = None
        ticket.save(update_fields=["assigned_to", "status", "completed_at", "updated_at"])

        history_note = f"Причина повторного открытия: {clean_reason}"
        if prev_resolution:
            history_note += f" | Предыдущий результат ремонта{completed_str}: {prev_resolution}"

        TicketHistory.objects.create(
            ticket=ticket,
            actor=admin_user,
            action=TicketHistory.Action.REOPENED,
            old_status=old_status,
            new_status=ticket.status,
            old_assignee=old_assignee,
            new_assignee=assignee,
            note=history_note,
        )
        return ticket


def deactivate_user_and_redistribute_tickets(
    *,
    target_user: User,
    actor: User,
    new_assignee: Optional[User] = None,
) -> int:
    """
    Безопасная деактивация техника: переназначает его открытые заявки другому активному
    специалисту либо возвращает их в очередь, полностью сохраняя историю выполненных работ.
    """
    if not actor.is_admin_role:
        raise PermissionDenied("Только администратор может отключать учётные записи.")
    if new_assignee is not None and (not new_assignee.is_active or new_assignee.pk == target_user.pk):
        raise ValidationError("Некорректный получатель для переназначения открытых заявок.")

    with transaction.atomic():
        open_tickets = list(
            Ticket.objects.select_for_update()
            .filter(assigned_to=target_user)
            .exclude(status=Ticket.Status.DONE)
        )
        for ticket in open_tickets:
            old_status = ticket.status
            if new_assignee is not None:
                ticket.assigned_to = new_assignee
                if ticket.status == Ticket.Status.NEW:
                    ticket.status = Ticket.Status.IN_PROGRESS
                action = TicketHistory.Action.ASSIGNED
                note = f"Переназначено в связи с деактивацией учётной записи {target_user.display_name}."
            else:
                ticket.assigned_to = None
                ticket.status = Ticket.Status.NEW
                action = TicketHistory.Action.RETURNED_TO_QUEUE
                note = f"Возвращено в общую очередь в связи с деактивацией {target_user.display_name}."

            ticket.save(update_fields=["assigned_to", "status", "updated_at"])
            TicketHistory.objects.create(
                ticket=ticket,
                actor=actor,
                action=action,
                old_status=old_status,
                new_status=ticket.status,
                old_assignee=target_user,
                new_assignee=new_assignee,
                note=note,
            )

        target_user.is_active = False
        target_user.save(update_fields=["is_active"])
        return len(open_tickets)
