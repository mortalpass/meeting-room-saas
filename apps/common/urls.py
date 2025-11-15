# apps/common/urls.py
from django.urls import path
from . import views

app_name = 'common'

urlpatterns = [
    # 审计日志相关
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_log_list'),
    path('audit-logs/<int:pk>/', views.AuditLogDetailView.as_view(), name='audit_log_detail'),
    path('audit-logs/export/', views.AuditLogExportView.as_view(), name='audit_log_export'),
    path('audit-logs/statistics/', views.AuditLogStatisticsView.as_view(), name='audit_log_statistics'),

    # 系统通知管理（管理员）
    path('notifications/', views.SystemNotificationListView.as_view(), name='system_notification_list'),
    path('notifications/create/', views.SystemNotificationCreateView.as_view(), name='system_notification_create'),
    path('notifications/<int:pk>/', views.SystemNotificationDetailView.as_view(), name='system_notification_detail'),
    path('notifications/<int:pk>/delete/', views.SystemNotificationDeleteView.as_view(),
         name='system_notification_delete'),
    path('notifications/bulk-action/', views.SystemNotificationBulkActionView.as_view(),
         name='system_notification_bulk_action'),

    # 用户个人通知
    path('my-notifications/', views.UserNotificationListView.as_view(), name='user_notification_list'),
    path('my-notifications/<int:pk>/', views.UserNotificationDetailView.as_view(), name='user_notification_detail'),
    path('my-notifications/mark-all-read/', views.MarkAllNotificationsReadView.as_view(),
         name='mark_all_notifications_read'),
    path('my-notifications/<int:pk>/quick-delete/', views.quick_delete_notification, name='quick_delete_notification'),

    # 通知设置
    path('notification-settings/', views.NotificationSettingsView.as_view(), name='notification_settings'),

    # API接口
    path('api/notification-count/', views.NotificationCountAPIView.as_view(), name='notification_count_api'),
    path('api/notifications/<int:pk>/mark-read/', views.MarkNotificationReadAPIView.as_view(),
         name='mark_notification_read_api'),
]