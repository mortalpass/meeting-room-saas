from django.contrib import admin

from apps.bookings.models import MeetingRoom, Reservation, ReservationConfig

admin.site.register(MeetingRoom)
admin.site.register(Reservation)
admin.site.register(ReservationConfig)
