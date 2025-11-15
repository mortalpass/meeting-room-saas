from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.companies.models import Company


class MeetingRoom(models.Model):
    """会议室模型"""
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="所属公司"
    )
    name = models.CharField(
        max_length=100,
        verbose_name="房间名称"
    )
    location = models.CharField(
        max_length=200,
        verbose_name="位置",
        help_text="例如：3楼301室"
    )
    capacity = models.IntegerField(
        verbose_name="容量",
        help_text="最多容纳人数"
    )
    is_available = models.BooleanField(
        default=True,
        verbose_name="是否可用"
    )
    remarks = models.TextField(
        blank=True,
        verbose_name="备注信息"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )

    class Meta:
        verbose_name = "会议室"
        verbose_name_plural = verbose_name
        unique_together = ['company', 'name']
        ordering = ['company', 'name']
        db_table = 'bookings_meeting_room'
        indexes = [
            models.Index(fields=['company', 'is_available']),
        ]

    def __str__(self):
        return f"{self.name} - {self.company.name}"

    def clean(self):
        """数据验证"""
        if self.capacity <= 0:
            raise ValidationError(_('容量必须大于0'))

        # 检查同一公司内是否存在同名会议室
        if MeetingRoom.objects.filter(
                company=self.company,
                name=self.name
        ).exclude(pk=self.pk).exists():
            raise ValidationError(_('同一公司内会议室名称不能重复'))


class Reservation(models.Model):
    """预约模型"""
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_COMPLETED = 'completed'
    STATUS_IN_USE = 'in_use'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = (
        (STATUS_PENDING, '待确认'),
        (STATUS_CONFIRMED, '已确认'),
        (STATUS_CANCELLED, '已取消'),
        (STATUS_COMPLETED, '已完成'),
        (STATUS_IN_USE, '使用中'),
        (STATUS_REJECTED, '已拒绝'),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="预约公司"
    )
    meeting_room = models.ForeignKey(
        MeetingRoom,
        on_delete=models.CASCADE,
        verbose_name="会议室"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="预约人"
    )
    title = models.CharField(
        max_length=200,
        verbose_name="预约主题"
    )
    description = models.TextField(
        blank=True,
        verbose_name="会议描述"
    )
    start_time = models.DateTimeField(
        verbose_name="开始时间"
    )
    end_time = models.DateTimeField(
        verbose_name="结束时间"
    )
    participant_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="参与人数",
        help_text="预计参与会议的人数"
    )
    participants = models.ManyToManyField(
        User,
        related_name='participating_meetings',
        blank=True,
        verbose_name="参会人员"
    )
    remarks = models.TextField(
        blank=True,
        verbose_name="备注"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="状态"
    )

    class Meta:
        verbose_name = "预约"
        verbose_name_plural = verbose_name
        db_table = 'bookings_reservation'
        indexes = [
            models.Index(fields=['company', 'start_time', 'end_time']), 
            models.Index(fields=['meeting_room', 'start_time', 'end_time']),
            models.Index(fields=['user', 'start_time']),
            models.Index(fields=['status', 'start_time']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.meeting_room.name}"

    def clean(self):
        """验证预约数据的合理性"""
        super().clean()

        # 检查时间逻辑
        if self.start_time >= self.end_time:
            raise ValidationError(_('结束时间必须晚于开始时间'))

        # 检查是否预约过去的时间
        if self.start_time < timezone.now():
            raise ValidationError(_('不能预约过去的时间'))

        # 检查预约时长（至少15分钟，最多8小时）
        duration = self.end_time - self.start_time
        if duration.total_seconds() < 900:  # 15分钟
            raise ValidationError(_('预约时长至少15分钟'))
        if duration.total_seconds() > 28800:  # 8小时
            raise ValidationError(_('单次预约时长不能超过8小时'))

        # 检查时间冲突（排除自身和已取消的预约）
        conflicting_statuses = [self.STATUS_PENDING, self.STATUS_CONFIRMED, self.STATUS_IN_USE]

        if self.pk is None:  # 新建预约
            conflicting = Reservation.objects.filter(
                meeting_room=self.meeting_room,
                status__in=conflicting_statuses,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time
            )
        else:  # 更新预约
            conflicting = Reservation.objects.filter(
                meeting_room=self.meeting_room,
                status__in=conflicting_statuses,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time
            ).exclude(pk=self.pk)

        if conflicting.exists():
            raise ValidationError(_('该时间段已被预约，请选择其他时间'))

        # 检查参与人数是否超过会议室容量
        if (self.participant_count and
                self.participant_count > self.meeting_room.capacity):
            raise ValidationError(
                _('参与人数不能超过会议室容量（%(capacity)s人）') % {
                    'capacity': self.meeting_room.capacity
                }
            )

    def save(self, *args, **kwargs):
        """保存前进行数据验证"""
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def duration(self):
        """计算预约时长（小时）"""
        if self.start_time and self.end_time:
            return round((self.end_time - self.start_time).total_seconds() / 3600, 2)
        return 0

    def is_currently_in_use(self):
        """检查预约是否正在进行中"""
        now = timezone.now()
        return (self.start_time <= now <= self.end_time and
                self.status in [self.STATUS_CONFIRMED, self.STATUS_IN_USE])

    def can_be_cancelled(self):
        """检查预约是否可以取消"""
        return (self.status in [self.STATUS_PENDING, self.STATUS_CONFIRMED] and
                self.start_time > timezone.now())


class ReservationConfig(models.Model):
    """预约配置模型"""
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        verbose_name="公司",
        related_name='reservation_config'
    )
    max_advance_days = models.IntegerField(
        default=30,
        verbose_name="最大提前预约天数"
    )
    min_duration_minutes = models.IntegerField(
        default=15,
        verbose_name="最短预约时长(分钟)"
    )
    max_duration_hours = models.IntegerField(
        default=8,
        verbose_name="最长预约时长(小时)"
    )
    allow_weekend_booking = models.BooleanField(
        default=False,
        verbose_name="允许周末预约"
    )
    work_start_time = models.TimeField(
        default='09:00',
        verbose_name="工作开始时间"
    )
    work_end_time = models.TimeField(
        default='18:00',
        verbose_name="工作结束时间"
    )
    require_approval = models.BooleanField(
        default=False,
        verbose_name="需要审批"
    )
    auto_approval = models.BooleanField(
        default=False,
        verbose_name="自动审批"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )

    class Meta:
        verbose_name = "预约配置"
        verbose_name_plural = verbose_name
        db_table = 'bookings_reservation_config'

    def __str__(self):
        return f"{self.company.name} 预约配置"