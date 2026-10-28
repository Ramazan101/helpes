"""╨д╨╛╤А╨╝╤Л ╨┐╨╛╨┤╨░╤З╨╕ ╨╖╨░╤П╨▓╨║╨╕ ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨╛╨╝, ╨╛╨▒╤А╨░╨▒╨╛╤В╨║╨╕ ╤В╨╡╤Е╨╜╨╕╨║╨╛╨╝ ╨╕ ╤Г╨┐╤А╨░╨▓╨╗╨╡╨╜╨╕╤П ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨╛╨╝."""
from django import forms
from django.forms import BaseFormSet, formset_factory

from apps.accounts.models import User
from apps.locations.models import Location
from .models import EquipmentCategory, Ticket


class PublicTicketForm(forms.Form):
    employee_name = forms.CharField(
        label="Ваше имя и фамилия",
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "Например: Асанов Бакыт",
        }),
    )
    custom_location = forms.CharField(
        label="Где сломалось?",
        max_length=255,
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "Например: 3-й этаж, кабинет 12",
        }),
    )
    short_description = forms.CharField(
        label="Что случилось?",
        max_length=255,
        widget=forms.Textarea(attrs={
            "class": "form-control form-control-lg",
            "rows": 4,
            "placeholder": "Опишите неисправность",
        }),
    )
    website_honeypot = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    def clean_website_honeypot(self):
        value = self.cleaned_data.get("website_honeypot")
        if value:
            raise forms.ValidationError("Не удалось отправить заявку.")
        return value

class TicketItemRowForm(forms.Form):
    category = forms.ModelChoiceField(
        label="╨в╨╕╨┐ ╨╛╨▒╨╛╤А╤Г╨┤╨╛╨▓╨░╨╜╨╕╤П / ╨╜╨╡╨╕╤Б╨┐╤А╨░╨▓╨╜╨╛╤Б╤В╨╕",
        queryset=EquipmentCategory.objects.none(),
        empty_label="тАФ ╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╤В╨╕╨┐ ╨╛╨▒╨╛╤А╤Г╨┤╨╛╨▓╨░╨╜╨╕╤П тАФ",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    quantity = forms.IntegerField(
        label="╨Ъ╨╛╨╗╨╕╤З╨╡╤Б╤В╨▓╨╛",
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = EquipmentCategory.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        quantity = cleaned_data.get("quantity")

        category_raw = self.data.get(self.add_prefix("category"), "").strip()
        quantity_raw = self.data.get(self.add_prefix("quantity"), "").strip()

        if not category_raw and not quantity_raw:
            self._errors.pop("category", None)
            self._errors.pop("quantity", None)
            cleaned_data["category"] = None
            cleaned_data["quantity"] = None
            self.cleaned_data = cleaned_data
            return cleaned_data

        if not category:
            self.add_error("category", "???????? ??? ????????????.")

        if quantity is None:
            self.add_error("quantity", "??????? ??????????.")

        return self.cleaned_data


class RequiredTicketItemFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        valid_rows = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            category = form.cleaned_data.get("category")
            quantity = form.cleaned_data.get("quantity")
            if category and quantity is not None:
                if quantity < 1:
                    raise forms.ValidationError("╨Ъ╨╛╨╗╨╕╤З╨╡╤Б╤В╨▓╨╛ ╤Г╤Б╤В╤А╨╛╨╣╤Б╤В╨▓ ╨┤╨╛╨╗╨╢╨╜╨╛ ╨▒╤Л╤В╤М ╨╜╨╡ ╨╝╨╡╨╜╤М╤И╨╡ 1.")
                valid_rows += 1


TicketItemFormSet = formset_factory(
    TicketItemRowForm,
    formset=RequiredTicketItemFormSet,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class TechStatusUpdateForm(forms.Form):
    status = forms.ChoiceField(
        label="╨Э╨╛╨▓╤Л╨╣ ╤Б╤В╨░╤В╤Г╤Б",
        choices=[
            (Ticket.Status.IN_PROGRESS, "╨Т ╤А╨░╨▒╨╛╤В╨╡"),
            (Ticket.Status.WAITING, "╨Ю╨╢╨╕╨┤╨░╨╡╤В (╤В╤А╨╡╨▒╤Г╨╡╤В╤Б╤П ╤Г╤В╨╛╤З╨╜╨╡╨╜╨╕╨╡ / ╨╖╨░╨┐╤З╨░╤Б╤В╨╕)"),
            (Ticket.Status.DONE, "╨Т╤Л╨┐╨╛╨╗╨╜╨╡╨╜╨░"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    resolution_summary = forms.CharField(
        label="╨Т╤Л╨┐╨╛╨╗╨╜╨╡╨╜╨╜╤Л╨╡ ╨┤╨╡╨╣╤Б╤В╨▓╨╕╤П ╨╕ ╤А╨╡╨╖╤Г╨╗╤М╤В╨░╤В ╤А╨╡╨╝╨╛╨╜╤В╨░ (╨╛╨▒╤П╨╖╨░╤В╨╡╨╗╤М╨╜╨╛ ╨┤╨╗╤П ╤Б╤В╨░╤В╤Г╤Б╨░ ┬л╨Т╤Л╨┐╨╛╨╗╨╜╨╡╨╜╨░┬╗)",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    comment_text = forms.CharField(
        label="╨Ъ╨╛╨╝╨╝╨╡╨╜╤В╨░╤А╨╕╨╣ ╨╛ ╤Е╨╛╨┤╨╡ ╨┤╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨╕ (╨╛╨▒╤П╨╖╨░╤В╨╡╨╗╤М╨╜╨╛ ╨┤╨╗╤П ╤Б╤В╨░╤В╤Г╤Б╨░ ┬л╨Ю╨╢╨╕╨┤╨░╨╡╤В┬╗)",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class TicketCommentForm(forms.Form):
    body = forms.CharField(
        label="╨Ъ╨╛╨╝╨╝╨╡╨╜╤В╨░╤А╨╕╨╣ ╨╛ ╤Е╨╛╨┤╨╡ ╨┤╨╕╨░╨│╨╜╨╛╤Б╤В╨╕╨║╨╕",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "╨Ю╨┐╨╕╤И╨╕╤В╨╡ ╤Е╨╛╨┤ ╨┐╤А╨╛╨▓╨╡╤А╨║╨╕ ╨╕╨╗╨╕ ╤Г╤В╨╛╤З╨╜╨╡╨╜╨╕╤П..."}),
    )


class ReturnToQueueForm(forms.Form):
    reason = forms.CharField(
        label="╨Я╤А╨╕╤З╨╕╨╜╨░ ╨▓╨╛╨╖╨▓╤А╨░╤В╨░ ╨▓ ╨╛╨▒╤Й╤Г╤О ╨╛╤З╨╡╤А╨╡╨┤╤М",
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "╨Э╨░╨┐╤А╨╕╨╝╨╡╤А: ╨в╤А╨╡╨▒╤Г╨╡╤В╤Б╤П ╨▓╤Л╨╡╨╖╨┤ ╤Б╨╡╤В╨╡╨▓╨╛╨│╨╛ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨░"}),
    )


class AdminAssignTicketForm(forms.Form):
    assigned_to = forms.ModelChoiceField(
        label="╨Э╨░╨╖╨╜╨░╤З╨╕╤В╤М ╤Б╨┐╨╡╤Ж╨╕╨░╨╗╨╕╤Б╤В╨░ (╨╛╤Б╤В╨░╨▓╤М╤В╨╡ ╨┐╤Г╤Б╤В╤Л╨╝ ╨┤╨╗╤П ╨▓╨╛╨╖╨▓╤А╨░╤В╨░ ╨▓ ╨╛╤З╨╡╤А╨╡╨┤╤М)",
        queryset=User.objects.none(),
        required=False,
        empty_label="тАФ ╨С╨╡╨╖ ╨╕╤Б╨┐╨╛╨╗╨╜╨╕╤В╨╡╨╗╤П (╨▓╨╡╤А╨╜╤Г╤В╤М ╨▓ ╨╛╨▒╤Й╤Г╤О ╨╛╤З╨╡╤А╨╡╨┤╤М) тАФ",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    note = forms.CharField(
        label="╨Я╤А╨╕╨╝╨╡╤З╨░╨╜╨╕╨╡ ╨║ ╨╜╨░╨╖╨╜╨░╤З╨╡╨╜╨╕╤О (╨╜╨╡╨╛╨▒╤П╨╖╨░╤В╨╡╨╗╤М╨╜╨╛)",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_active=True, role__in=[User.Role.TECH, User.Role.ADMIN]
        )


class AdminReopenTicketForm(forms.Form):
    reason = forms.CharField(
        label="╨Я╤А╨╕╤З╨╕╨╜╨░ ╨┐╨╛╨▓╤В╨╛╤А╨╜╨╛╨│╨╛ ╨╛╤В╨║╤А╤Л╤В╨╕╤П ╨╖╨░╤П╨▓╨║╨╕",
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "╨Я╤А╨╛╨▒╨╗╨╡╨╝╨░ ╨┐╤А╨╛╤П╨▓╨╕╨╗╨░╤Б╤М ╨┐╨╛╨▓╤В╨╛╤А╨╜╨╛"}),
    )
    assigned_to = forms.ModelChoiceField(
        label="╨Ш╤Б╨┐╨╛╨╗╨╜╨╕╤В╨╡╨╗╤М (╨╜╨╡╨╛╨▒╤П╨╖╨░╤В╨╡╨╗╤М╨╜╨╛)",
        queryset=User.objects.none(),
        required=False,
        empty_label="тАФ ╨Т ╨╛╨▒╤Й╤Г╤О ╨╛╤З╨╡╤А╨╡╨┤╤М тАФ",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_active=True, role__in=[User.Role.TECH, User.Role.ADMIN]
        )


class EquipmentCategoryForm(forms.ModelForm):
    class Meta:
        model = EquipmentCategory
        fields = ["name", "description", "sort_order", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "╨Э╨░╨┐╤А╨╕╨╝╨╡╤А: ╨Ь╨д╨г ╨╕╨╗╨╕ ╨┐╨╗╨╛╤В╤В╨╡╤А"}),
            "description": forms.TextInput(attrs={"class": "form-control", "placeholder": "╨Я╨╛╤П╤Б╨╜╨╡╨╜╨╕╨╡ ╨┤╨╗╤П ╤Б╨╛╤В╤А╤Г╨┤╨╜╨╕╨║╨╛╨▓"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
