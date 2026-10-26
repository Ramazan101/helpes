"""Формы подачи заявки сотрудником, обработки техником и управления администратором."""
from django import forms
from django.forms import BaseFormSet, formset_factory

from apps.accounts.models import User
from apps.locations.models import Location
from .models import EquipmentCategory, Ticket


class PublicTicketForm(forms.Form):
    employee_name = forms.CharField(
        label="Ваше имя и фамилия (или должность)",
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "form-control form-control-lg", "placeholder": "Например: Асанов Бакыт"}
        ),
    )
    location = forms.ModelChoiceField(
        label="Этаж и кабинет",
        queryset=Location.objects.none(),
        required=False,
        empty_label="— Выберите кабинет из списка —",
        widget=forms.Select(attrs={"class": "form-select form-select-lg"}),
    )
    custom_location = forms.CharField(
        label="Или укажите местоположение текстом (если кабинета нет в списке)",
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Например: 3 этаж, переговорная у лифта",
            }
        ),
    )
    short_description = forms.CharField(
        label="Краткое описание неисправности (что именно не работает)",
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "Например: Не печатает сетевой принтер и не включается монитор",
            }
        ),
    )
    detailed_description = forms.CharField(
        label="Подробности (необязательно)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Как проявляется проблема и при каких обстоятельствах возникла",
            }
        ),
    )
    website_honeypot = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].queryset = (
            Location.objects.filter(is_active=True, floor__is_active=True)
            .exclude(floor__building__is_active=False)
            .select_related("floor", "floor__building")
        )
        self.fields["location"].label_from_instance = lambda obj: obj.full_title

    def clean_website_honeypot(self):
        val = self.cleaned_data.get("website_honeypot")
        if val:
            raise forms.ValidationError("Обнаружена автоматическая отправка формы.")
        return val

    def clean(self):
        cleaned = super().clean()
        loc = cleaned.get("location")
        custom_loc = (cleaned.get("custom_location") or "").strip()
        if not loc and not custom_loc:
            self.add_error(
                "location",
                "Пожалуйста, выберите кабинет из списка или укажите местоположение вручную в поле ниже.",
            )
        return cleaned


class TicketItemRowForm(forms.Form):
    category = forms.ModelChoiceField(
        label="Тип оборудования / неисправности",
        queryset=EquipmentCategory.objects.none(),
        empty_label="— Выберите тип оборудования —",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    quantity = forms.IntegerField(
        label="Количество",
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = EquipmentCategory.objects.filter(is_active=True)


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
                    raise forms.ValidationError("Количество устройств должно быть не меньше 1.")
                valid_rows += 1
        if valid_rows == 0:
            raise forms.ValidationError("Добавьте хотя бы одну позицию оборудования с количеством не меньше 1.")


TicketItemFormSet = formset_factory(
    TicketItemRowForm,
    formset=RequiredTicketItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class TechStatusUpdateForm(forms.Form):
    status = forms.ChoiceField(
        label="Новый статус",
        choices=[
            (Ticket.Status.IN_PROGRESS, "В работе"),
            (Ticket.Status.WAITING, "Ожидает (требуется уточнение / запчасти)"),
            (Ticket.Status.DONE, "Выполнена"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    resolution_summary = forms.CharField(
        label="Выполненные действия и результат ремонта (обязательно для статуса «Выполнена»)",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    comment_text = forms.CharField(
        label="Комментарий о ходе диагностики (обязательно для статуса «Ожидает»)",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class TicketCommentForm(forms.Form):
    body = forms.CharField(
        label="Комментарий о ходе диагностики",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Опишите ход проверки или уточнения..."}),
    )


class ReturnToQueueForm(forms.Form):
    reason = forms.CharField(
        label="Причина возврата в общую очередь",
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Например: Требуется выезд сетевого администратора"}),
    )


class AdminAssignTicketForm(forms.Form):
    assigned_to = forms.ModelChoiceField(
        label="Назначить специалиста (оставьте пустым для возврата в очередь)",
        queryset=User.objects.none(),
        required=False,
        empty_label="— Без исполнителя (вернуть в общую очередь) —",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    note = forms.CharField(
        label="Примечание к назначению (необязательно)",
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
        label="Причина повторного открытия заявки",
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Проблема проявилась повторно"}),
    )
    assigned_to = forms.ModelChoiceField(
        label="Исполнитель (необязательно)",
        queryset=User.objects.none(),
        required=False,
        empty_label="— В общую очередь —",
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
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Например: МФУ или плоттер"}),
            "description": forms.TextInput(attrs={"class": "form-control", "placeholder": "Пояснение для сотрудников"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
