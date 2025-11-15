from django.contrib import admin

from apps.common.models import AuditLog, SystemNotification

admin.site.register(AuditLog)
admin.site.register(SystemNotification)

