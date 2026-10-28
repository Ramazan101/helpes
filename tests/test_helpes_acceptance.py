"""РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРёРµ С‚РµСЃС‚С‹ РІСЃРµС… 16 РєСЂРёС‚РµСЂРёРµРІ РїСЂРёС‘РјРєРё Рё РёРЅС‚РµСЂС„РµР№СЃР° MVP Helpes."""
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
    floor1 = Floor.objects.create(name="1 СЌС‚Р°Р¶", sort_order=1)
    room101 = Location.objects.create(floor=floor1, name="РљР°Р±РёРЅРµС‚ 101", sort_order=1)
    cat_pc = EquipmentCategory.objects.create(name="РљРѕРјРїСЊСЋС‚РµСЂ РёР»Рё РЅРѕСѓС‚Р±СѓРє", sort_order=10)
    cat_prn = EquipmentCategory.objects.create(name="РџСЂРёРЅС‚РµСЂ", sort_order=20)
    tech1 = User.objects.create_user(
        username="tech1", password="password123", full_name="РўРµС…РЅРёРє РћРґРёРЅ", role=User.Role.TECH
    )
    tech2 = User.objects.create_user(
        username="tech2", password="password123", full_name="РўРµС…РЅРёРє Р”РІР°", role=User.Role.TECH
    )
    admin = User.objects.create_user(
        username="admin1", password="password123", full_name="РђРґРјРёРЅ РЎРёСЃС‚РµРјС‹", role=User.Role.ADMIN
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
            "employee_name": "РђСЃР°РЅРѕРІ Р‘Р°РєС‹С‚",
            "custom_location": "Office 101",
            "short_description": "РќРµ СЂР°Р±РѕС‚Р°СЋС‚ РџРљ Рё РїСЂРёРЅС‚РµСЂ",
            "website_honeypot": "",
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-category": base_setup["cat_pc"].id,
            "items-0-quantity": "3",
            "items-1-category": base_setup["cat_prn"].id,
            "items-1-quantity": "1",
        },
    )
    assert response.status_code == 302, (
        f"form errors: {response.context.get('form').errors}; "
        f"formset errors: {response.context.get('formset').errors}; "
        f"formset non-form errors: {response.context.get('formset').non_form_errors()}"
    )
    ticket = Ticket.objects.get()
    assert ticket.ticket_number.startswith("HELP-")
    assert ticket.employee_name == "РђСЃР°РЅРѕРІ Р‘Р°РєС‹С‚"
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
            "employee_name": "РњР°РјС‹С‚РѕРІ Р­СЂРјРµРє",
            "custom_location": "Office 101",
            "short_description": "РЎР»РѕРјР°Р»СЃСЏ РјРѕРЅРёС‚РѕСЂ",
            "website_honeypot": "",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-category": base_setup["cat_pc"].id,
            "items-0-quantity": "0",
        },
    )
    assert invalid_resp.status_code == 200
    assert "РњР°РјС‹С‚РѕРІ Р­СЂРјРµРє".encode() in invalid_resp.content
    assert Ticket.objects.count() == 1

    with pytest.raises(ValidationError):
        create_public_ticket(
            employee_name="РўРµСЃС‚",
            location=base_setup["room101"],
            custom_location="",
            short_description="РћС€РёР±РєР°",
            detailed_description="",
            items_data=[{"category": base_setup["cat_pc"], "quantity": -2}],
        )


def test_custom_location_and_duplicate_category_aggregation(base_setup):
    ticket = create_public_ticket(
        employee_name="РЎР°РґС‹РєРѕРІ Рљ.",
        location=None,
        custom_location="РЎРєР»Р°РґСЃРєРѕР№ Р±Р»РѕРє, 2 СЌС‚Р°Р¶",
        short_description="РќРµ РїРµС‡Р°С‚Р°СЋС‚ РґРІР° РїСЂРёРЅС‚РµСЂР°",
        detailed_description="",
        items_data=[
            {"category": base_setup["cat_prn"], "quantity": 1},
            {"category": base_setup["cat_prn"], "quantity": 2},
        ],
    )
    assert ticket.location is None
    assert ticket.location_display == "РЎРєР»Р°РґСЃРєРѕР№ Р±Р»РѕРє, 2 СЌС‚Р°Р¶"
    assert ticket.items.count() == 1
    assert ticket.total_equipment_count == 3


def test_6_to_7_admin_adds_and_deactivates_floor_room_and_category(client, base_setup):
    client.force_login(base_setup["admin"])
    client.post(reverse("locations:building_add"), {"name": "Р“Р»Р°РІРЅС‹Р№ РєРѕСЂРїСѓСЃ", "sort_order": 1, "is_active": True})
    building = Building.objects.get(name="Р“Р»Р°РІРЅС‹Р№ РєРѕСЂРїСѓСЃ")
    client.post(
        reverse("locations:floor_add"),
        {"building": building.id, "name": "5 СЌС‚Р°Р¶", "sort_order": 5, "is_active": True},
    )
    floor5 = Floor.objects.get(name="5 СЌС‚Р°Р¶")
    client.post(
        reverse("locations:room_add"),
        {"floor": floor5.id, "name": "РљР°Р±РёРЅРµС‚ 505", "sort_order": 1, "is_active": True},
    )
    room505 = Location.objects.get(name="РљР°Р±РёРЅРµС‚ 505")
    assert room505.is_active is True

    client.post(
        reverse("tickets:admin_categories"),
        {"name": "РџР»РѕС‚С‚РµСЂ", "description": "РЁРёСЂРѕРєРѕС„РѕСЂРјР°С‚РЅС‹Р№", "sort_order": 80, "is_active": True},
    )
    plotter = EquipmentCategory.objects.get(name="РџР»РѕС‚С‚РµСЂ")
    assert plotter.is_active is True

    room505.is_active = False
    room505.save()
    public_form = PublicTicketForm()
    assert "location" not in public_form.fields
    assert {"employee_name", "custom_location", "short_description"}.issubset(public_form.fields)
    assert public_form.fields["custom_location"].required


def test_8_to_13_full_lifecycle_reopen_roles_and_deactivation(client, base_setup):
    ticket = create_public_ticket(
        employee_name="РРІР°РЅРѕРІ Р.",
        location=base_setup["room101"],
        custom_location="",
        short_description="РќРµ РїРµС‡Р°С‚Р°РµС‚",
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

    add_ticket_comment(ticket_number=ticket.ticket_number, author=base_setup["tech1"], body="РџСЂРѕРІРµСЂРµРЅ РєР°Р±РµР»СЊ USB")
    waiting = update_ticket_status(
        ticket_number=ticket.ticket_number,
        actor=base_setup["tech1"],
        new_status=Ticket.Status.WAITING,
        comment_text="РћР¶РёРґР°РµРј С‚РѕРЅРµСЂ-РєР°СЂС‚СЂРёРґР¶",
    )
    assert waiting.status == Ticket.Status.WAITING

    returned = return_ticket_to_queue(
        ticket_number=ticket.ticket_number,
        actor=base_setup["tech1"],
        reason="РџРµСЂРµРґР°РЅРѕ РґРµР¶СѓСЂРЅРѕР№ СЃРјРµРЅРµ",
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
        resolution_summary="Р—Р°РјРµРЅС‘РЅ РєР°СЂС‚СЂРёРґР¶ Рё СЂРѕР»РёРє Р·Р°С…РІР°С‚Р° Р±СѓРјР°РіРё",
    )
    assert completed.status == Ticket.Status.DONE
    assert completed.completed_at is not None

    reopened = admin_reopen_ticket(
        ticket_number=ticket.ticket_number,
        admin_user=base_setup["admin"],
        reason="РЎРЅРѕРІР° Р·Р°РјРёРЅР°РµС‚ Р±СѓРјР°РіСѓ",
        assignee=base_setup["tech2"],
    )
    assert reopened.status == Ticket.Status.IN_PROGRESS
    assert reopened.completed_at is None

    reopen_history = TicketHistory.objects.filter(
        ticket=ticket, action=TicketHistory.Action.REOPENED
    ).first()
    assert reopen_history is not None
    assert "Р—Р°РјРµРЅС‘РЅ РєР°СЂС‚СЂРёРґР¶ Рё СЂРѕР»РёРє Р·Р°С…РІР°С‚Р° Р±СѓРјР°РіРё" in reopen_history.note
    assert "if ticket.completed_at" not in reopen_history.note


def test_15_ui_filters_and_admin_views_render(client, base_setup):
    ticket = create_public_ticket(
        employee_name="РўРѕРєС‚РѕРіСѓР»РѕРІ Рђ.",
        location=base_setup["room101"],
        custom_location="",
        short_description="РќРµ СЂР°Р±РѕС‚Р°РµС‚ СЃРµС‚РµРІР°СЏ СЂРѕР·РµС‚РєР°",
        detailed_description="РњРёРіР°РµС‚ РёРЅРґРёРєР°С‚РѕСЂ РЅР° СЃРёСЃС‚РµРјРЅРѕРј Р±Р»РѕРєРµ",
        items_data=[{"category": base_setup["cat_pc"], "quantity": 2}],
    )
    client.force_login(base_setup["tech1"])
    queue_resp = client.get(reverse("tickets:tech_queue"), {"q": "РўРѕРєС‚РѕРіСѓР»РѕРІ", "status": "NEW"})
    assert queue_resp.status_code == 200
    assert ticket.ticket_number.encode() in queue_resp.content

    client.force_login(base_setup["admin"])
    admin_list_resp = client.get(reverse("tickets:admin_ticket_list"), {"filter": "unassigned", "status": "NEW"})
    assert admin_list_resp.status_code == 200
    assert ticket.ticket_number.encode() in admin_list_resp.content

    admin_detail_resp = client.get(reverse("tickets:admin_ticket_detail", args=[ticket.ticket_number]))
    assert admin_detail_resp.status_code == 200
    assert "РќРµ СЂР°Р±РѕС‚Р°РµС‚ СЃРµС‚РµРІР°СЏ СЂРѕР·РµС‚РєР°".encode() in admin_detail_resp.content
    assert "РњРёРіР°РµС‚ РёРЅРґРёРєР°С‚РѕСЂ РЅР° СЃРёСЃС‚РµРјРЅРѕРј Р±Р»РѕРєРµ".encode() in admin_detail_resp.content


def test_public_ticket_can_be_created_without_equipment(client, base_setup):
    response = client.post(
        reverse("tickets:public_create"),
        data={
            "employee_name": "Test Employee",
            "custom_location": "Office 101",
            "short_description": "Computer does not start",
            "website_honeypot": "",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
        },
    )

    assert response.status_code == 302, response.content.decode("utf-8")[:6000]
    ticket = Ticket.objects.get()
    assert ticket.employee_name == "Test Employee"
    assert ticket.custom_location == "Office 101"
    assert ticket.short_description == "Computer does not start"
    assert ticket.items.count() == 0

    success_response = client.get(response.url)
    assert success_response.status_code == 200
    assert ticket.ticket_number.encode() in success_response.content
