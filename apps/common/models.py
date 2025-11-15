from django.db import models
from django.contrib.auth.models import User
from apps.companies.models import Company


class AuditLog(models.Model):
    """审计日志模型"""
    ACTION_CHOICES = (
        ('create', '创建'),
        ('update', '更新'),
        ('delete', '删除'),
        ('login', '登录'),
        ('logout', '登出'),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="公司",
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="操作用户"
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name="操作类型"
    )
    model_name = models.CharField(
        max_length=100,
        verbose_name="模型名称"
    )
    object_id = models.CharField(
        max_length=100,
        verbose_name="对象ID"
    )
    description = models.TextField(
        verbose_name="操作描述"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP地址"
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name="用户代理"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="操作时间"
    )

    class Meta:
        verbose_name = "审计日志"
        verbose_name_plural = verbose_name
        db_table = 'common_audit_log'
        indexes = [
            models.Index(fields=['company', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"


class SystemNotification(models.Model):
    """系统通知模型"""
    NOTIFICATION_TYPES = (
        ('reservation_created', '预约创建'),
        ('reservation_approved', '预约批准'),
        ('reservation_rejected', '预约拒绝'),
        ('reservation_cancelled', '预约取消'),
        ('reservation_reminder', '预约提醒'),
        ('system', '系统通知'),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="公司"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="接收用户"
    )
    type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        verbose_name="通知类型"
    )
    title = models.CharField(
        max_length=200,
        verbose_name="通知标题"
    )
    message = models.TextField(
        verbose_name="通知内容"
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name="是否已读"
    )
    related_object_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="关联对象ID"
    )
    related_content_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="关联内容类型"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )

    class Meta:
        verbose_name = "系统通知"
        verbose_name_plural = verbose_name
        db_table = 'common_system_notification'
        indexes = [
            models.Index(fields=['company', 'user', 'is_read']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"