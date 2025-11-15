# apps/common/forms.py
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import AuditLog, SystemNotification
from apps.companies.models import Company


class AuditLogSearchForm(forms.Form):
    """审计日志搜索表单"""
    ACTION_CHOICES = (
        ('', '所有操作'),
        ('create', '创建'),
        ('update', '更新'),
        ('delete', '删除'),
        ('login', '登录'),
        ('logout', '登出'),
    )

    DATE_RANGE_CHOICES = (
        ('today', '今天'),
        ('last_7_days', '最近7天'),
        ('last_30_days', '最近30天'),
        ('last_90_days', '最近90天'),
        ('custom', '自定义范围'),
    )

    date_range = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        initial='last_7_days',
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

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=False,
        label="操作类型",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        required=False,
        label="公司",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="操作用户",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    model_name = forms.CharField(
        required=False,
        label="模型名称",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '输入模型名称...'
        })
    )

    keyword = forms.CharField(
        required=False,
        label="关键词搜索",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '搜索操作描述...'
        })
    )

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        # 如果是普通用户，限制公司选择范围
        if self.current_user and not self.current_user.is_superuser:
            # 只显示用户有权限的公司
            user_companies = Company.objects.filter(
                userprofile__user=self.current_user
            ).distinct()
            self.fields['company'].queryset = user_companies

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


class SystemNotificationForm(forms.ModelForm):
    """系统通知表单"""

    class Meta:
        model = SystemNotification
        fields = ['company', 'user', 'type', 'title', 'message', 'related_object_id', 'related_content_type']
        labels = {
            'company': '公司',
            'user': '接收用户',
            'type': '通知类型',
            'title': '通知标题',
            'message': '通知内容',
            'related_object_id': '关联对象ID',
            'related_content_type': '关联内容类型',
        }
        widgets = {
            'company': forms.Select(attrs={
                'class': 'form-control'
            }),
            'user': forms.Select(attrs={
                'class': 'form-control'
            }),
            'type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入通知标题'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': '请输入通知内容...'
            }),
            'related_object_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '关联对象ID（可选）'
            }),
            'related_content_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '关联内容类型（可选）'
            }),
        }
        help_texts = {
            'title': '通知标题应简洁明了',
            'message': '详细描述通知内容',
            'related_object_id': '如关联预约，可填写预约ID',
            'related_content_type': '如关联预约，可填写"booking"',
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        # 限制公司和用户选择范围
        if self.current_user:
            if not self.current_user.is_superuser:
                # 普通用户只能选择自己公司的用户
                user_companies = Company.objects.filter(
                    userprofile__user=self.current_user
                ).distinct()
                self.fields['company'].queryset = user_companies

                # 用户只能选择同一公司的用户
                if user_companies:
                    self.fields['user'].queryset = User.objects.filter(
                        userprofile__company__in=user_companies
                    ).distinct()


class SystemNotificationCreateForm(SystemNotificationForm):
    """系统通知创建表单"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 创建时可以批量选择用户
        self.fields['users'] = forms.ModelMultipleChoiceField(
            queryset=User.objects.none(),
            required=False,
            label="批量发送给用户",
            widget=forms.SelectMultiple(attrs={
                'class': 'form-control',
                'size': 5
            }),
            help_text="可以选择多个用户批量发送通知（按住Ctrl多选）"
        )

        if self.current_user:
            if not self.current_user.is_superuser:
                user_companies = Company.objects.filter(
                    userprofile__user=self.current_user
                ).distinct()
                if user_companies:
                    self.fields['users'].queryset = User.objects.filter(
                        userprofile__company__in=user_companies
                    ).distinct()
            else:
                self.fields['users'].queryset = User.objects.all()


class SystemNotificationSearchForm(forms.Form):
    """系统通知搜索表单"""
    NOTIFICATION_TYPE_CHOICES = (
        ('', '所有类型'),
        ('reservation_created', '预约创建'),
        ('reservation_approved', '预约批准'),
        ('reservation_rejected', '预约拒绝'),
        ('reservation_cancelled', '预约取消'),
        ('reservation_reminder', '预约提醒'),
        ('system', '系统通知'),
    )

    STATUS_CHOICES = (
        ('', '所有状态'),
        ('read', '已读'),
        ('unread', '未读'),
    )

    DATE_RANGE_CHOICES = (
        ('today', '今天'),
        ('last_7_days', '最近7天'),
        ('last_30_days', '最近30天'),
        ('custom', '自定义范围'),
    )

    date_range = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        initial='last_7_days',
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

    notification_type = forms.ChoiceField(
        choices=NOTIFICATION_TYPE_CHOICES,
        required=False,
        label="通知类型",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        label="阅读状态",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        required=False,
        label="公司",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    keyword = forms.CharField(
        required=False,
        label="关键词搜索",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '搜索标题或内容...'
        })
    )

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        # 限制公司选择范围
        if self.current_user and not self.current_user.is_superuser:
            user_companies = Company.objects.filter(
                userprofile__user=self.current_user
            ).distinct()
            self.fields['company'].queryset = user_companies

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


class SystemNotificationBulkActionForm(forms.Form):
    """系统通知批量操作表单"""
    ACTION_CHOICES = (
        ('mark_read', '标记为已读'),
        ('mark_unread', '标记为未读'),
        ('delete', '删除通知'),
    )

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        label="批量操作",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    notifications = forms.ModelMultipleChoiceField(
        queryset=SystemNotification.objects.all(),
        label="选择通知",
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'size': '10'
        })
    )

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        # 限制通知选择范围
        if self.current_user:
            if not self.current_user.is_superuser:
                user_companies = Company.objects.filter(
                    userprofile__user=self.current_user
                ).distinct()
                if user_companies:
                    self.fields['notifications'].queryset = SystemNotification.objects.filter(
                        company__in=user_companies
                    )


class NotificationSettingsForm(forms.Form):
    """通知设置表单"""
    # 预约相关通知
    reservation_created = forms.BooleanField(
        required=False,
        initial=True,
        label="预约创建通知",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    reservation_approved = forms.BooleanField(
        required=False,
        initial=True,
        label="预约批准通知",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    reservation_rejected = forms.BooleanField(
        required=False,
        initial=True,
        label="预约拒绝通知",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    reservation_cancelled = forms.BooleanField(
        required=False,
        initial=True,
        label="预约取消通知",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    reservation_reminder = forms.BooleanField(
        required=False,
        initial=True,
        label="预约提醒通知",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    # 系统通知
    system_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label="系统通知",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    # 通知方式
    email_notifications = forms.BooleanField(
        required=False,
        initial=False,
        label="邮件通知",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    push_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label="推送通知",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    # 提醒时间
    reminder_time = forms.ChoiceField(
        choices=(
            ('15', '15分钟前'),
            ('30', '30分钟前'),
            ('60', '1小时前'),
            ('120', '2小时前'),
            ('1440', '1天前'),
        ),
        initial='30',
        label="预约提醒时间",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )


class AuditLogExportForm(forms.Form):
    """审计日志导出表单"""
    FORMAT_CHOICES = (
        ('csv', 'CSV格式'),
        ('excel', 'Excel格式'),
        ('pdf', 'PDF格式'),
    )

    format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        initial='csv',
        label="导出格式",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    include_columns = forms.MultipleChoiceField(
        choices=(
            ('timestamp', '操作时间'),
            ('user', '操作用户'),
            ('action', '操作类型'),
            ('model_name', '模型名称'),
            ('object_id', '对象ID'),
            ('description', '操作描述'),
            ('ip_address', 'IP地址'),
            ('company', '公司'),
        ),
        initial=['timestamp', 'user', 'action', 'model_name', 'description'],
        label="包含列",
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )

    start_date = forms.DateField(
        required=True,
        label="开始日期",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    end_date = forms.DateField(
        required=True,
        label="结束日期",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    def clean(self):
        """验证日期范围"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError('开始日期不能晚于结束日期')

            # 限制导出时间范围不超过90天
            if (end_date - start_date).days > 90:
                raise ValidationError('导出时间范围不能超过90天')

        return cleaned_data


class SystemNotificationFilterForm(forms.Form):
    """系统通知筛选表单（用于用户查看自己的通知）"""
    NOTIFICATION_TYPE_CHOICES = (
        ('', '所有类型'),
        ('reservation_created', '预约创建'),
        ('reservation_approved', '预约批准'),
        ('reservation_rejected', '预约拒绝'),
        ('reservation_cancelled', '预约取消'),
        ('reservation_reminder', '预约提醒'),
        ('system', '系统通知'),
    )

    notification_type = forms.ChoiceField(
        choices=NOTIFICATION_TYPE_CHOICES,
        required=False,
        label="通知类型",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    is_read = forms.ChoiceField(
        choices=(
            ('', '所有状态'),
            ('true', '已读'),
            ('false', '未读'),
        ),
        required=False,
        label="阅读状态",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# 工具函数
def get_notification_type_choices():
    """获取通知类型选择"""
    return SystemNotification.NOTIFICATION_TYPES


def get_audit_action_choices():
    """获取审计操作类型选择"""
    return AuditLog.ACTION_CHOICES


class AuditLogDetailForm(forms.ModelForm):
    """审计日志详情表单（只读，用于显示）"""

    class Meta:
        model = AuditLog
        fields = ['company', 'user', 'action', 'model_name', 'object_id',
                  'description', 'ip_address', 'user_agent']
        labels = {
            'company': '公司',
            'user': '操作用户',
            'action': '操作类型',
            'model_name': '模型名称',
            'object_id': '对象ID',
            'description': '操作描述',
            'ip_address': 'IP地址',
            'user_agent': '用户代理',
        }
        widgets = {
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': True
            }),
            'user': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': True
            }),
            'action': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': True
            }),
            'model_name': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': True
            }),
            'object_id': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'readonly': True
            }),
            'ip_address': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': True
            }),
            'user_agent': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'readonly': True
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 将所有字段设置为不可编辑
        for field in self.fields:
            self.fields[field].disabled = True