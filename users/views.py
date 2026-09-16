from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib import messages

from movies.models import (
    Event,
    Premiere,
    MusicStudio,
    Booking
)

from .forms import UserRegisterForm, UserUpdateForm


def home(request):

    events = Event.objects.all()
    premieres = Premiere.objects.all()
    music_studio = MusicStudio.objects.all()

    return render(
        request,
        'users/home.html',
        {
            'events': events,
            'premieres': premieres,
            'music_studio': music_studio,
        }
    )


def register(request):

    if request.method == 'POST':

        form = UserRegisterForm(request.POST)

        if form.is_valid():

            form.save()

            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')

            user = authenticate(
                username=username,
                password=password
            )

            if user is not None:
                login(request, user)

            return redirect('home')

    else:

        form = UserRegisterForm()

    return render(
        request,
        'users/register.html',
        {
            'form': form
        }
    )


def login_view(request):

    if request.method == 'POST':

        form = AuthenticationForm(
            request,
            data=request.POST
        )

        if form.is_valid():

            user = form.get_user()

            login(request, user)

            return redirect('home')

    else:

        form = AuthenticationForm()

    return render(
        request,
        'users/login.html',
        {
            'form': form
        }
    )


@login_required(login_url='/login/')
def profile(request):

    bookings = Booking.objects.filter(
        user=request.user
    ).select_related(
        'movie',
        'theater',
        'seat'
    ).order_by(
        '-booked_at'
    )

    if request.method == 'POST':

        u_form = UserUpdateForm(
            request.POST,
            instance=request.user
        )

        if u_form.is_valid():

            u_form.save()

            messages.success(
                request,
                'Your profile has been updated successfully.'
            )

            return redirect('profile')

    else:

        u_form = UserUpdateForm(
            instance=request.user
        )

    return render(
        request,
        'users/profile.html',
        {
            'u_form': u_form,
            'bookings': bookings
        }
    )


@login_required(login_url='/login/')
def reset_password(request):

    if request.method == 'POST':

        form = PasswordChangeForm(
            user=request.user,
            data=request.POST
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                'Your password has been changed successfully. Please login again.'
            )

            logout(request)

            return redirect('login')

    else:

        form = PasswordChangeForm(
            user=request.user
        )

    return render(
        request,
        'users/reset_password.html',
        {
            'form': form
        }
    )


def password_reset(request):

    return render(
        request,
        'users/password_reset.html'
    )


def logout_view(request):

    logout(request)

    return render(
        request,
        'users/logout.html'
    )

def reset_password(request):

    if request.method == "POST":

        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if new_password != confirm_password:
            return render(
                request,
                "users/password_reset_confirm.html",
                {
                    "error": "Passwords do not match."
                }
            )

        if not new_password:
            return render(
                request,
                "users/password_reset_confirm.html",
                {
                    "error": "Please enter a password."
                }
            )

        # Change this if you want to identify the user differently
        user = request.user

        if not user.is_authenticated:
            return render(
                request,
                "users/password_reset_confirm.html",
                {
                    "error": "Please login before resetting your password."
                }
            )

        user.set_password(new_password)
        user.save()

        return render(
            request,
            "users/password_reset_confirm.html",
            {
                "success": True
            }
        )

    return render(
        request,
        "users/password_reset_confirm.html"
    )