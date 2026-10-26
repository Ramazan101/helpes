"""Формы входа, управления пользователями и безопасной деактивации техников."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User


class HelpesLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Логин",
        widget=forms.TextInput(attrs={"class": "form-control form-control-lg", "autofocus": True}),
    )
    password = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control form-control-lg"}),
    )


class StaffUserCreateForm(forms.ModelForm):
    password = forms.CharField(
        label="Пароль",
        min_length=6,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ["username", "full_name", "role", "is_active"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class StaffUserUpdateForm(forms.ModelForm):
    new_password = forms.CharField(
        label="Новый пароль (оставьте пустым, чтобы не менять)",
        required=False,
        min_length=6,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ["full_name", "role", "is_active"]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get("new_password")
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
        return user


class DeactivateUserForm(forms.Form):
    ACTION_RETURN = "return_to_queue"
    ACTION_REASSIGN = "reassign"

    action_mode = forms.ChoiceField(
        label="Что сделать с незавершёнными заявками специалиста?",
        choices=[
            (ACTION_RETURN, "Вернуть все открытые заявки в общую очередь (статус «Новая»)"),
            (ACTION_REASSIGN, "Переназначить все открытые заявки другому активному специалисту"),
        ],
        initial=ACTION_RETURN,
        widget=forms.RadioSelect,
    )
    target_tech = forms.ModelChoiceField(
        label="Новый исполнитель (при переназначении)",
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, user_to_deactivate=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(is_active=True, role__in=[User.Role.TECH, User.Role.ADMIN])
        if user_to_deactivate is not None:
            qs = qs.exclude(pk=user_to_deactivate.pk)
        self.fields["target_tech"].queryset = qs

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("action_mode") == self.ACTION_REASSIGN and not cleaned.get("target_tech"):
            self.add_error("target_tech", "Выберите активного специалиста для передачи открытых заявок.")
        return cleaned
