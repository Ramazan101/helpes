from django import forms
from .models import Building, Floor, Location


class BuildingForm(forms.ModelForm):
    class Meta:
        model = Building
        fields = ["name", "sort_order", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Например: Главный корпус"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class FloorForm(forms.ModelForm):
    class Meta:
        model = Floor
        fields = ["building", "name", "sort_order", "is_active"]
        widgets = {
            "building": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Например: 5 этаж"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["floor", "name", "sort_order", "is_active"]
        widgets = {
            "floor": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Например: Кабинет 501"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
