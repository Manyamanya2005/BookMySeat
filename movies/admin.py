from django.contrib import admin
from .models import (
    Movie,
    MoviePoster,
    Genre,
    Language,
    CastMember,
    Theater,
    Seat,
    Booking,
    Event,
    Premiere,
    MusicStudio,
    Review,
)


# =========================
# MOVIE POSTERS
# =========================

class MoviePosterInline(admin.TabularInline):
    model = MoviePoster
    extra = 1


# =========================
# MOVIE ADMIN
# =========================

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'rating',
        'genre',
        'language',
        'certification',
        'duration',
        'release_date',
        'cast',
    )

    list_filter = (
        'genre',
        'language',
        'certification',
        'release_date',
    )

    search_fields = (
        'name',
        'cast',
        'genre',
        'language',
    )

    filter_horizontal = (
        'genres',
        'languages',
        'cast_members',
    )

    inlines = [
        MoviePosterInline,
    ]


# =========================
# GENRE
# =========================

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):

    list_display = (
        'name',
    )

    search_fields = (
        'name',
    )


# =========================
# LANGUAGE
# =========================

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):

    list_display = (
        'name',
    )

    search_fields = (
        'name',
    )


# =========================
# CAST MEMBER
# =========================

@admin.register(CastMember)
class CastMemberAdmin(admin.ModelAdmin):

    list_display = (
        'name',
    )

    search_fields = (
        'name',
    )


# =========================
# THEATER
# =========================

@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'movie',
        'location',
        'date',
        'time',
    )

    list_filter = (
        'movie',
        'date',
    )

    search_fields = (
        'name',
        'location',
        'movie__name',
    )


# =========================
# SEAT
# =========================

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):

    list_display = (
        'seat_number',
        'theater',
        'is_booked',
    )

    list_filter = (
        'is_booked',
        'theater',
    )

    search_fields = (
        'seat_number',
        'theater__name',
    )


# =========================
# BOOKING
# =========================

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):

    list_display = (
        'user',
        'movie',
        'theater',
        'seat',
        'watched',
        'booked_at',
    )

    list_filter = (
        'watched',
        'movie',
        'theater',
    )

    search_fields = (
        'user__username',
        'movie__name',
        'theater__name',
        'seat__seat_number',
    )


# =========================
# REVIEW
# =========================

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):

    list_display = (
        'user',
        'movie',
        'rating',
        'is_reported',
        'created_at',
        'updated_at',
    )

    list_filter = (
        'rating',
        'is_reported',
        'created_at',
    )

    search_fields = (
        'user__username',
        'movie__name',
        'comment',
    )


# =========================
# OTHER EXISTING MODELS
# =========================

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):

    list_display = (
        'title',
    )

    search_fields = (
        'title',
    )


@admin.register(Premiere)
class PremiereAdmin(admin.ModelAdmin):

    list_display = (
        'title',
    )

    search_fields = (
        'title',
    )


@admin.register(MusicStudio)
class MusicStudioAdmin(admin.ModelAdmin):

    list_display = (
        'title',
    )

    search_fields = (
        'title',
    )