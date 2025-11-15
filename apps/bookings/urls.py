# apps/bookings/urls.py
from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    # 仪表板
    path('', views.dashboard, name='dashboard'),

    # 会议室管理
    path('meeting-rooms/', views.MeetingRoomListView.as_view(), name='meeting_room_list'),
    path('meeting-rooms/create/', views.MeetingRoomCreateView.as_view(), name='meeting_room_create'),
    path('meeting-rooms/<int:pk>/update/', views.MeetingRoomUpdateView.as_view(), name='meeting_room_update'),
    path('meeting-rooms/<int:pk>/delete/', views.MeetingRoomDeleteView.as_view(), name='meeting_room_delete'),
    path('meeting-rooms/<int:pk>/toggle-availability/', views.meeting_room_toggle_availability,
         name='meeting_room_toggle_availability'),

    # 预约管理
    path('reservations/', views.ReservationListView.as_view(), name='reservation_list'),
    path('reservations/create/', views.ReservationCreateView.as_view(), name='reservation_create'),
    path('reservations/<int:pk>/', views.ReservationDetailView.as_view(), name='reservation_detail'),
    path('reservations/<int:pk>/update/', views.ReservationUpdateView.as_view(), name='reservation_update'),
    path('reservations/<int:pk>/cancel/', views.reservation_cancel, name='reservation_cancel'),
    path('reservations/<int:pk>/update-status/', views.ReservationStatusUpdateView.as_view(),
         name='reservation_status_update'),

    # 快速预约
    path('quick-reservation/', views.quick_reservation, name='quick_reservation'),

    # 日历视图
    path('calendar/', views.reservation_calendar, name='reservation_calendar'),

    # 配置管理
    path('config/', views.reservation_config, name='reservation_config'),

    # API接口
    path('api/meeting-rooms/', views.api_meeting_rooms, name='api_meeting_rooms'),
    path('api/available-slots/', views.api_available_slots, name='api_available_slots'),
    path('api/reservation-stats/', views.api_reservation_stats, name='api_reservation_stats'),
    path('api/check-time-conflict/', views.api_check_time_conflict, name='api_check_time_conflict'),
]