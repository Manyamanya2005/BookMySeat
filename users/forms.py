from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class UserRegisterForm(UserCreationForm):

    email = forms.EmailField(
        required=True
    )


    class Meta:

        model = User

        fields = [
            'username',
            'email',
            'password1',
            'password2'
        ]


    def __init__(self, *args, **kwargs):

        super().__init__(
            *args,
            **kwargs
        )

        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': ''
        })

        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': ''
        })

        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': ''
        })

        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': ''
        })


class UserUpdateForm(forms.ModelForm):

    class Meta:

        model = User

        fields = [
            'username',
            'email'
        ]


    def __init__(self, *args, **kwargs):

        super().__init__(
            *args,
            **kwargs
        )

        self.fields['username'].widget.attrs.update({
            'class': 'form-control'
        })

        self.fields['email'].widget.attrs.update({
            'class': 'form-control'
        })