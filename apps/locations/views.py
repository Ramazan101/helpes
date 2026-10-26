"""Управление зданиями, этажами и кабинетами в панели администратора."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.permissions import admin_required
from .forms import BuildingForm, FloorForm, LocationForm
from .models import Building, Floor, Location


@admin_required
def admin_locations(request):
    buildings = Building.objects.all()
    floors = Floor.objects.select_related("building").all()
    locations = Location.objects.select_related("floor", "floor__building").all()
    return render(
        request,
        "manage/location_list.html",
        {
            "buildings": buildings,
            "floors": floors,
            "locations": locations,
            "building_form": BuildingForm(),
            "floor_form": FloorForm(),
            "location_form": LocationForm(),
        },
    )


@admin_required
def building_add(request):
    if request.method == "POST":
        form = BuildingForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"Здание «{obj.name}» добавлено.")
        else:
            messages.error(request, "Ошибка при добавлении здания. Проверьте уникальность названия.")
    return redirect("locations:admin_locations")


@admin_required
def building_edit(request, pk: int):
    building = get_object_or_404(Building, pk=pk)
    if request.method == "POST":
        form = BuildingForm(request.POST, instance=building)
        if form.is_valid():
            form.save()
            messages.success(request, f"Здание «{building.name}» обновлено.")
            return redirect("locations:admin_locations")
    else:
        form = BuildingForm(instance=building)
    return render(request, "manage/location_edit.html", {"form": form, "title": f"Редактирование здания: {building.name}"})


@admin_required
def floor_add(request):
    if request.method == "POST":
        form = FloorForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"Этаж «{obj.full_name}» добавлен.")
        else:
            messages.error(request, "Не удалось добавить этаж. Проверьте введённые поля.")
    return redirect("locations:admin_locations")


@admin_required
def floor_edit(request, pk: int):
    floor = get_object_or_404(Floor, pk=pk)
    if request.method == "POST":
        form = FloorForm(request.POST, instance=floor)
        if form.is_valid():
            form.save()
            messages.success(request, f"Этаж «{floor.full_name}» обновлён.")
            return redirect("locations:admin_locations")
    else:
        form = FloorForm(instance=floor)
    return render(request, "manage/location_edit.html", {"form": form, "title": f"Редактирование этажа: {floor.full_name}"})


@admin_required
def room_add(request):
    if request.method == "POST":
        form = LocationForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"Кабинет «{obj.full_title}» добавлен и доступен в форме заявки.")
        else:
            messages.error(request, "Не удалось добавить кабинет. Проверьте выбранный этаж и название.")
    return redirect("locations:admin_locations")


@admin_required
def room_edit(request, pk: int):
    room = get_object_or_404(Location, pk=pk)
    if request.method == "POST":
        form = LocationForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, f"Кабинет «{room.full_title}» обновлён.")
            return redirect("locations:admin_locations")
    else:
        form = LocationForm(instance=room)
    return render(request, "manage/location_edit.html", {"form": form, "title": f"Редактирование кабинета: {room.full_title}"})
