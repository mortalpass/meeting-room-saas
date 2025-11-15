# apps/bookings/forms.py
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import MeetingRoom, Reservation, ReservationConfig


class MeetingRoomForm(forms.ModelForm):
    """会议室表单"""

    class Meta:
        model = MeetingRoom
        fields = ['name', 'location', 'capacity', 'is_available', 'remarks']
        labels = {
            'name': '会议室名称',
            'location': '位置',
            'capacity': '容量',
            'is_available': '是否可用',
            'remarks': '备注信息',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入会议室名称'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例如：3楼301室'
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': '最多容纳人数'
            }),
            'is_available': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '请输入备注信息（可选）'
            }),
        }
        help_texts = {
            'capacity': '最多容纳人数，必须大于0',
            'location': '详细位置信息，如楼层和房间号',
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        """验证会议室名称在公司内唯一"""
        name = self.cleaned_data.get('name')
        if self.company and name:
            queryset = MeetingRoom.objects.filter(
                company=self.company, name=name
            )
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise ValidationError('同一公司内会议室名称不能重复')
        return name

    def clean_capacity(self):
        """验证容量必须大于0"""
        capacity = self.cleaned_data.get('capacity')
        if capacity and capacity <= 0:
            raise ValidationError('容量必须大于0')
        return capacity

    def save(self, commit=True):
        """保存时设置公司"""
        meeting_room = super().save(commit=False)
        if self.company:
            meeting_room.company = self.company

        if commit:
            meeting_room.save()
        return meeting_room


class ReservationForm(forms.ModelForm):
    """预约表单"""
    # 添加参与者字段（多选）
    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="参会人员",
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'data-placeholder': '选择参会人员（可选）'
        })
    )

    class Meta:
        model = Reservation
        fields = [
            'meeting_room', 'title', 'description', 'start_time',
            'end_time', 'participant_count', 'participants', 'remarks'
        ]
        labels = {
            'meeting_room': '会议室',
            'title': '会议主题',
            'description': '会议描述',
            'start_time': '开始时间',
            'end_time': '结束时间',
            'participant_count': '参与人数',
            'remarks': '备注',
        }
        widgets = {
            'meeting_room': forms.Select(attrs={
                'class': 'form-control'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入会议主题'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '请输入会议描述（可选）'
            }),
            'start_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'participant_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': '预计参与人数'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': '请输入备注（可选）'
            }),
        }
        help_texts = {
            'participant_count': '预计参与会议的人数',
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # 限制会议室选择范围为当前公司
        if self.company:
            self.fields['meeting_room'].queryset = MeetingRoom.objects.filter(
                company=self.company, is_available=True
            )

            # 限制参与者选择范围为当前公司用户
            self.fields['participants'].queryset = User.objects.filter(
                profile__company=self.company
            ).exclude(pk=self.user.pk if self.user else None)

        # 如果是编辑已有预约，设置初始值
        if self.instance and self.instance.pk:
            self.fields['participants'].initial = self.instance.participants.all()

    def clean(self):
        """自定义验证"""
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        meeting_room = cleaned_data.get('meeting_room')
        participant_count = cleaned_data.get('participant_count')

        # 检查时间逻辑
        if start_time and end_time:
            if start_time >= end_time:
                raise ValidationError({'end_time': '结束时间必须晚于开始时间'})

            # 检查是否预约过去的时间
            if start_time < timezone.now():
                raise ValidationError({'start_time': '不能预约过去的时间'})

            # 检查预约时长
            duration = end_time - start_time
            if duration.total_seconds() < 900:  # 15分钟
                raise ValidationError({'end_time': '预约时长至少15分钟'})
            if duration.total_seconds() > 28800:  # 8小时
                raise ValidationError({'end_time': '单次预约时长不能超过8小时'})

            # 检查时间冲突
            if meeting_room:
                conflicting_statuses = [
                    Reservation.STATUS_PENDING,
                    Reservation.STATUS_CONFIRMED,
                    Reservation.STATUS_IN_USE
                ]

                if self.instance and self.instance.pk:
                    conflicting = Reservation.objects.filter(
                        meeting_room=meeting_room,
                        status__in=conflicting_statuses,
                        start_time__lt=end_time,
                        end_time__gt=start_time
                    ).exclude(pk=self.instance.pk)
                else:
                    conflicting = Reservation.objects.filter(
                        meeting_room=meeting_room,
                        status__in=conflicting_statuses,
                        start_time__lt=end_time,
                        end_time__gt=start_time
                    )

                if conflicting.exists():
                    raise ValidationError('该时间段已被预约，请选择其他时间')

        # 检查参与人数是否超过会议室容量
        if meeting_room and participant_count:
            if participant_count > meeting_room.capacity:
                raise ValidationError({
                    'participant_count': f'参与人数不能超过会议室容量（{meeting_room.capacity}人）'
                })

        return cleaned_data

    def save(self, commit=True):
        """保存预约并处理参与者"""
        reservation = super().save(commit=False)

        # 设置公司和用户
        if self.company:
            reservation.company = self.company
        if self.user:
            reservation.user = self.user

        if commit:
            reservation.save()
            # 保存多对多关系（参与者）
            self.save_m2m()

            # 处理参与者关系
            if 'participants' in self.cleaned_data:
                reservation.participants.set(self.cleaned_data['participants'])

        return reservation


class ReservationSearchForm(forms.Form):
    """预约搜索表单"""
    DATE_RANGE_CHOICES = (
        ('today', '今天'),
        ('tomorrow', '明天'),
        ('this_week', '本周'),
        ('next_week', '下周'),
        ('this_month', '本月'),
        ('custom', '自定义'),
    )

    STATUS_CHOICES = (
        ('', '所有状态'),
        ('pending', '待确认'),
        ('confirmed', '已确认'),
        ('in_use', '使用中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    )

    date_range = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        required=False,
        initial='this_week',
        label="时间范围",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'date_range_select'
        })
    )

    start_date = forms.DateField(
        required=False,
        label="开始日期",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'id': 'start_date_input'
        })
    )

    end_date = forms.DateField(
        required=False,
        label="结束日期",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'id': 'end_date_input'
        })
    )

    meeting_room = forms.ModelChoiceField(
        queryset=MeetingRoom.objects.none(),
        required=False,
        label="会议室",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        label="状态",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    search = forms.CharField(
        required=False,
        label="搜索",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '搜索会议主题、描述...'
        })
    )

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

        # 限制会议室选择范围为当前公司
        if self.company:
            self.fields['meeting_room'].queryset = MeetingRoom.objects.filter(
                company=self.company
            )

    def clean(self):
        """验证日期范围"""
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if date_range == 'custom':
            if not start_date or not end_date:
                raise ValidationError('选择自定义范围时，必须指定开始日期和结束日期')
            if start_date > end_date:
                raise ValidationError('开始日期不能晚于结束日期')

        return cleaned_data


class ReservationConfigForm(forms.ModelForm):
    """预约配置表单"""

    class Meta:
        model = ReservationConfig
        fields = [
            'max_advance_days', 'min_duration_minutes', 'max_duration_hours',
            'allow_weekend_booking', 'work_start_time', 'work_end_time',
            'require_approval', 'auto_approval'
        ]
        labels = {
            'max_advance_days': '最大提前预约天数',
            'min_duration_minutes': '最短预约时长(分钟)',
            'max_duration_hours': '最长预约时长(小时)',
            'allow_weekend_booking': '允许周末预约',
            'work_start_time': '工作开始时间',
            'work_end_time': '工作结束时间',
            'require_approval': '需要审批',
            'auto_approval': '自动审批',
        }
        widgets = {
            'max_advance_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 365
            }),
            'min_duration_minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 15,
                'step': 15
            }),
            'max_duration_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 24
            }),
            'allow_weekend_booking': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'work_start_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'work_end_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'require_approval': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'auto_approval': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        help_texts = {
            'max_advance_days': '用户可以提前多少天进行预约',
            'min_duration_minutes': '单次预约的最短时长',
            'max_duration_hours': '单次预约的最长时长',
            'allow_weekend_booking': '是否允许在周末预约会议室',
            'work_start_time': '工作日可预约的开始时间',
            'work_end_time': '工作日可预约的结束时间',
            'require_approval': '预约是否需要管理员审批',
            'auto_approval': '是否自动批准预约（如果不需要审批，此设置无效）',
        }

    def clean(self):
        """验证配置合理性"""
        cleaned_data = super().clean()
        min_duration_minutes = cleaned_data.get('min_duration_minutes')
        max_duration_hours = cleaned_data.get('max_duration_hours')
        work_start_time = cleaned_data.get('work_start_time')
        work_end_time = cleaned_data.get('work_end_time')
        require_approval = cleaned_data.get('require_approval')
        auto_approval = cleaned_data.get('auto_approval')

        # 验证时长设置
        if min_duration_minutes and max_duration_hours:
            min_hours = min_duration_minutes / 60
            if min_hours > max_duration_hours:
                raise ValidationError('最短预约时长不能超过最长预约时长')

        # 验证工作时间
        if work_start_time and work_end_time:
            if work_start_time >= work_end_time:
                raise ValidationError('工作结束时间必须晚于工作开始时间')

        # 验证审批设置
        if auto_approval and not require_approval:
            raise ValidationError('只有在需要审批时才能启用自动审批')

        return cleaned_data


class ReservationStatusUpdateForm(forms.ModelForm):
    """预约状态更新表单（管理员使用）"""

    class Meta:
        model = Reservation
        fields = ['status']
        labels = {
            'status': '状态',
        }
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-control'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 根据当前状态限制可用的状态选项
        if self.instance:
            current_status = self.instance.status
            status_choices = []

            for status_value, status_label in Reservation.STATUS_CHOICES:
                # 根据业务逻辑限制状态转换
                if current_status == Reservation.STATUS_PENDING:
                    if status_value in [Reservation.STATUS_CONFIRMED, Reservation.STATUS_REJECTED,
                                        Reservation.STATUS_CANCELLED]:
                        status_choices.append((status_value, status_label))
                elif current_status == Reservation.STATUS_CONFIRMED:
                    if status_value in [Reservation.STATUS_IN_USE, Reservation.STATUS_CANCELLED]:
                        status_choices.append((status_value, status_label))
                elif current_status == Reservation.STATUS_IN_USE:
                    if status_value == Reservation.STATUS_COMPLETED:
                        status_choices.append((status_value, status_label))
                else:
                    # 已完成、已取消、已拒绝的状态不能更改
                    status_choices = [(current_status, self.instance.get_status_display())]

            self.fields['status'].choices = status_choices


class QuickReservationForm(forms.Form):
    """快速预约表单（简化版）"""
    meeting_room = forms.ModelChoiceField(
        queryset=MeetingRoom.objects.none(),
        label="会议室",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    title = forms.CharField(
        max_length=200,
        label="会议主题",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '简要描述会议内容'
        })
    )

    start_time = forms.DateTimeField(
        label="开始时间",
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )

    duration = forms.IntegerField(
        min_value=15,
        max_value=480,
        label="时长（分钟）",
        initial=60,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 15,
            'max': 480,
            'step': 15
        })
    )

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

        if self.company:
            self.fields['meeting_room'].queryset = MeetingRoom.objects.filter(
                company=self.company, is_available=True
            )

    def clean(self):
        """验证快速预约"""
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        duration = cleaned_data.get('duration')
        meeting_room = cleaned_data.get('meeting_room')

        if start_time and duration and meeting_room:
            end_time = start_time + timezone.timedelta(minutes=duration)

            # 检查时间冲突
            conflicting_statuses = [
                Reservation.STATUS_PENDING,
                Reservation.STATUS_CONFIRMED,
                Reservation.STATUS_IN_USE
            ]

            conflicting = Reservation.objects.filter(
                meeting_room=meeting_room,
                status__in=conflicting_statuses,
                start_time__lt=end_time,
                end_time__gt=start_time
            )

            if conflicting.exists():
                raise ValidationError('该时间段已被预约，请选择其他时间')

            # 将计算出的结束时间添加到cleaned_data中
            cleaned_data['end_time'] = end_time

        return cleaned_data


# 工具函数
def get_available_time_slots(meeting_room, date, duration_minutes=60):
    """
    获取指定日期和会议室的可用时间段
    """
    if not meeting_room or not date:
        return []

    # 获取当天的所有预约
    start_of_day = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.min.time()))
    end_of_day = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.max.time()))

    reservations = Reservation.objects.filter(
        meeting_room=meeting_room,
        start_time__lt=end_of_day,
        end_time__gt=start_of_day,
        status__in=[Reservation.STATUS_PENDING, Reservation.STATUS_CONFIRMED, Reservation.STATUS_IN_USE]
    ).order_by('start_time')

    # 生成时间段（假设工作时间为9:00-18:00）
    work_start = timezone.make_aware(timezone.datetime.combine(date, timezone.time(9, 0)))
    work_end = timezone.make_aware(timezone.datetime.combine(date, timezone.time(18, 0)))

    # 计算可用时间段
    available_slots = []
    current_time = work_start

    for reservation in reservations:
        # 当前时间到预约开始时间之间的空闲时段
        if current_time < reservation.start_time:
            slot_duration = (reservation.start_time - current_time).total_seconds() / 60
            if slot_duration >= duration_minutes:
                available_slots.append({
                    'start': current_time,
                    'end': reservation.start_time,
                    'duration': slot_duration
                })

        # 更新当前时间为预约结束时间
        current_time = max(current_time, reservation.end_time)

    # 最后一个预约之后的时间段
    if current_time < work_end:
        slot_duration = (work_end - current_time).total_seconds() / 60
        if slot_duration >= duration_minutes:
            available_slots.append({
                'start': current_time,
                'end': work_end,
                'duration': slot_duration
            })

    return available_slots