"""Автоматические тесты всех 16 критериев приёмки и интерфейса MVP Helpes."""
import pytest
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.accounts.models import User
from apps.locations.models import Building, Floor, Location
from apps.tickets.forms import PublicTicketForm
from apps.tickets.models import EquipmentCategory, Ticket, TicketHistory
from apps.tickets.services import (
    TicketConcurrencyError,
    add_ticket_comment,
    admin_assign_ticket,
    admin_reopen_ticket,
    claim_ticket,
    create_public_ticket,
    deactivate_user_and_redistribute_tickets,
    return_ticket_to_queue,
    update_ticket_status,
)


@pytest.fixture
def base_setup(db):
    cache.clear()
    floor1 = Floor.objects.create(name="1 этаж", sort_order=1)
    room101 = Location.objects.create(floor=floor1, name="Кабинет 101", sort_order=1)
    cat_pc = EquipmentCategory.objects.create(name="Компьютер или ноутбук", sort_order=10)
    cat_prn = EquipmentCategory.objects.create(name="Принтер", sort_order=20)
    tech1 = User.objects.create_user(
        username="tech1", password="password123", full_name="Техник Один", role=User.Role.TECH
    )
    tech2 = User.objects.create_user(
        username="tech2", password="password123", full_name="Техник Два", role=User.Role.TECH
    )
    admin = User.objects.create_user(
        username="admin1", password="password123", full_name="Админ Системы", role=User.Role.ADMIN
    )
    return {
        "floor1": floor1,
        "room101": room101,
        "cat_pc": cat_pc,
        "cat_prn": cat_prn,
        "tech1": tech1,
        "tech2": tech2,
        "admin": admin,
    }


def test_1_to_5_and_14_public_ticket_creation_and_validation(client, base_setup):
    response = client.post(
        reverse("tickets:public_create"),
        data={
            "employee_name": "Асанов Бакыт",
            "location": base_setup["room101"].id,
            "custom_location": "",
            "short_description": "Не работают ПК и принтер",
            "detailed_description": "После отключения света",
            "website_honeypot": "",
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-category": base_setup["cat_pc"].id,
            "items-0-quantity": "3",
            "items-1-category": base_setup["cat_prn"].id,
            "items-1-quantity": "1",
        },
    )
    assert response.status_code == 302
    ticket = Ticket.objects.get()
    assert ticket.ticket_number.startswith("HELP-")
    assert ticket.employee_name == "Асанов Бакыт"
    assert ticket.items.count() == 2
    assert ticket.total_equipment_count == 4

    success_resp = client.get(response.url)
    assert success_resp.status_code == 200
    assert ticket.ticket_number.encode() in success_resp.content

    other_client = client.__class__()
    idor_resp = other_client.get(reverse("tickets:public_success", args=[ticket.ticket_number]))
    assert idor_resp.status_code == 404

    invalid_resp = client.post(
        reverse("tickets:public_create"),
        data={
            "employee_name": "Мамытов Эрмек",
            "location": base_setup["room101"].id,
            "custom_location": "",
            "short_description": "Сломался монитор",
            "detailed_description": "",
            "website_honeypot": "",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-category": base_setup["cat_pc"].id,
            "items-0-quantity": "0",
        },
    )
    assert invalid_resp.status_code == 200
    assert "Мамытов Эрмек".encode() in invalid_resp.content
    assert Ticket.objects.count() == 1

    with pytest.raises(ValidationError):
        create_public_ticket(
            employee_name="Тест",
            location=base_setup["room101"],
            custom_location="",
            short_description="Ошибка",
            detailed_description="",
            items_data=[{"category": base_setup["cat_pc"], "quantity": -2}],
        )


def test_custom_location_and_duplicate_category_aggregation(base_setup):
    ticket = create_public_ticket(
        employee_name="Садыков К.",
        location=None,
        custom_location="Складской блок, 2 этаж",
        short_description="Не печатают два принтера",
        detailed_description="",
        items_data=[
            {"category": base_setup["cat_prn"], "quantity": 1},
            {"category": base_setup["cat_prn"], "quantity": 2},
        ],
    )
    assert ticket.location is None
    assert ticket.location_display == "Складской блок, 2 этаж"
    assert ticket.items.count() == 1
    assert ticket.total_equipment_count == 3


def test_6_to_7_admin_adds_and_deactivates_floor_room_and_category(client, base_setup):
    client.force_login(base_setup["admin"])
    client.post(reverse("locations:building_add"), {"name": "Главный корпус", "sort_order": 1, "is_active": True})
    building = Building.objects.get(name="Главный корпус")
    client.post(
        reverse("locations:floor_add"),
        {"building": building.id, "name": "5 этаж", "sort_order": 5, "is_active": True},
    )
    floor5 = Floor.objects.get(name="5 этаж")
    client.post(
        reverse("locations:room_add"),
        {"floor": floor5.id, "name": "Кабинет 505", "sort_order": 1, "is_active": True},
    )
    room505 = Location.objects.get(name="Кабинет 505")
    assert room505.is_active is True

    client.post(
        reverse("tickets:admin_categories"),
        {"name": "Плоттер", "description": "Широкоформатный", "sort_order": 80, "is_active": True},
    )
    plotter = EquipmentCategory.objects.get(name="Плоттер")
    assert plotter.is_active is True

    room505.is_active = False
    room505.save()
    public_form = PublicTicketForm()
    assert room505 not in public_form.fields["location"].queryset


def test_8_to_13_full_lifecycle_reopen_roles_and_deactivation(client, base_setup):
    ticket = create_public_ticket(
        employee_name="Иванов И.",
        location=base_setup["room101"],
        custom_location="",
        short_description="Не печатает",
        detailed_description="",
        items_data=[{"category": base_setup["cat_prn"], "quantity": 1}],
    )
    claimed = claim_ticket(ticket_number=ticket.ticket_number, tech_user=base_setup["tech1"])
    assert claimed.assigned_to == base_setup["tech1"]
    assert claimed.status == Ticket.Status.IN_PROGRESS

    with pytest.raises(TicketConcurrencyError):
        claim_ticket(ticket_number=ticket.ticket_number, tech_user=base_setup["tech2"])

    with pytest.raises(PermissionDenied):
        admin_assign_ticket(
            ticket_number=ticket.ticket_number,
            admin_user=base_setup["tech1"],
            new_assignee=base_setup["tech2"],
        )
    client.force_login(base_setup["tech1"])
    for admin_url in [
        reverse("tickets:admin_ticket_list"),
        reverse("tickets:admin_categories"),
        reverse("locations:admin_locations"),
        reverse("accounts:user_list"),
    ]:
        assert client.get(admin_url).status_code == 403

    add_ticket_comment(ticket_number=ticket.ticket_number, author=base_setup["tech1"], body="Проверен кабель USB")
    waiting = update_ticket_status(
        ticket_number=ticket.ticket_number,
        actor=base_setup["tech1"],
        new_status=Ticket.Status.WAITING,
        comment_text="Ожидаем тонер-картридж",
    )
    assert waiting.status == Ticket.Status.WAITING

    returned = return_ticket_to_queue(
        ticket_number=ticket.ticket_number,
        actor=base_setup["tech1"],
        reason="Передано дежурной смене",
    )
    assert returned.assigned_to is None
    assert returned.status == Ticket.Status.NEW

    admin_assign_ticket(
        ticket_number=ticket.ticket_number,
        admin_user=base_setup["admin"],
        new_assignee=base_setup["tech1"],
    )
    processed = deactivate_user_and_redistribute_tickets(
        target_user=base_setup["tech1"],
        actor=base_setup["admin"],
        new_assignee=base_setup["tech2"],
    )
    assert processed == 1
    ticket.refresh_from_db()
    base_setup["tech1"].refresh_from_db()
    assert not base_setup["tech1"].is_active
    assert ticket.assigned_to == base_setup["tech2"]

    completed = update_ticket_status(
        ticket_number=ticket.ticket_number,
        actor=base_setup["tech2"],
        new_status=Ticket.Status.DONE,
        resolution_summary="Заменён картридж и ролик захвата бумаги",
    )
    assert completed.status == Ticket.Status.DONE
    assert completed.completed_at is not None

    reopened = admin_reopen_ticket(
        ticket_number=ticket.ticket_number,
        admin_user=base_setup["admin"],
        reason="Снова заминает бумагу",
        assignee=base_setup["tech2"],
    )
    assert reopened.status == Ticket.Status.IN_PROGRESS
    assert reopened.completed_at is None

    reopen_history = TicketHistory.objects.filter(
        ticket=ticket, action=TicketHistory.Action.REOPENED
    ).first()
    assert reopen_history is not None
    assert "Заменён картридж и ролик захвата бумаги" in reopen_history.note
    assert "if ticket.completed_at" not in reopen_history.note


def test_15_ui_filters_and_admin_views_render(client, base_setup):
    ticket = create_public_ticket(
        employee_name="Токтогулов А.",
        location=base_setup["room101"],
        custom_location="",
        short_description="Не работает сетевая розетка",
        detailed_description="Мигает индикатор на системном блоке",
        items_data=[{"category": base_setup["cat_pc"], "quantity": 2}],
    )
    client.force_login(base_setup["tech1"])
    queue_resp = client.get(reverse("tickets:tech_queue"), {"q": "Токтогулов", "status": "NEW"})
    assert queue_resp.status_code == 200
    assert ticket.ticket_number.encode() in queue_resp.content

    client.force_login(base_setup["admin"])
    admin_list_resp = client.get(reverse("tickets:admin_ticket_list"), {"filter": "unassigned", "status": "NEW"})
    assert admin_list_resp.status_code == 200
    assert ticket.ticket_number.encode() in admin_list_resp.content

    admin_detail_resp = client.get(reverse("tickets:admin_ticket_detail", args=[ticket.ticket_number]))
    assert admin_detail_resp.status_code == 200
    assert "Не работает сетевая розетка".encode() in admin_detail_resp.content
    assert "Мигает индикатор на системном блоке".encode() in admin_detail_resp.content
