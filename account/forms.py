from django.contrib.auth.forms import UserCreationForm
from django import forms

from .models import User


class SignupForm(UserCreationForm):
    phone = forms.CharField(max_length=13, help_text='Required')
    class Meta:
        model = User
        fields = ('email', 'phone', 'name', 'password1', 'password2')


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('email', 'name', 'avatar',)