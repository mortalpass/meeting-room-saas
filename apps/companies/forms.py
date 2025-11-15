# apps/companies/forms.py
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Company


class CompanyForm(forms.ModelForm):
    """公司表单"""
    # 管理员选择字段 - 只显示活跃用户
    admin = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        label="管理员",
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text="选择将成为公司管理员的用户"
    )

    class Meta:
        model = Company
        fields = ['name', 'admin', 'is_active']
        labels = {
            'name': '公司名称',
            'is_active': '是否激活',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入公司名称'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        help_texts = {
            'name': '公司名称必须唯一，且至少2个字符',
            'is_active': '如果禁用，该公司所有用户将无法登录系统',
        }

    def __init__(self, *args, **kwargs):
        # 可以传递当前用户来限制管理员选择
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        # 如果是编辑模式，确保当前管理员在选项中
        if self.instance and self.instance.pk:
            current_admin = self.instance.admin
            if current_admin not in self.fields['admin'].queryset:
                self.fields['admin'].queryset = self.fields['admin'].queryset | User.objects.filter(pk=current_admin.pk)

    def clean_name(self):
        """验证公司名称唯一性"""
        name = self.cleaned_data.get('name')
        if name:
            # 检查名称是否已存在（排除当前实例）
            queryset = Company.objects.filter(name=name)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise ValidationError('公司名称已存在，请使用其他名称')
        return name

    def clean_admin(self):
        """验证管理员用户"""
        admin = self.cleaned_data.get('admin')
        if admin and not admin.is_active:
            raise ValidationError('选择的管理员用户必须处于活跃状态')
        return admin


class CompanyCreateForm(CompanyForm):
    """公司创建表单（扩展版本，可用于用户注册时创建公司）"""

    def __init__(self, *args, **kwargs):
        # 创建公司时通常不需要选择管理员，因为创建者自动成为管理员
        super().__init__(*args, **kwargs)

        # 如果是创建表单且指定了当前用户，隐藏管理员字段并设置为当前用户
        if self.current_user and not self.instance.pk:
            self.fields['admin'].widget = forms.HiddenInput()
            self.fields['admin'].initial = self.current_user
            self.fields['admin'].required = False

    def clean_admin(self):
        """在创建时，如果指定了当前用户，使用当前用户作为管理员"""
        admin = self.cleaned_data.get('admin')
        if not admin and self.current_user:
            return self.current_user
        return admin


class CompanyUpdateForm(CompanyForm):
    """公司更新表单（限制某些字段的修改）"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 在更新时，可以添加额外的限制或提示
        if self.instance and self.instance.pk:
            self.fields['name'].help_text = f'当前公司名称: {self.instance.name}'

            # 如果公司有用户，显示用户数量信息
            user_count = self.instance.user_count
            if user_count > 0:
                self.fields['is_active'].help_text = f'该公司有 {user_count} 名用户，禁用将影响所有用户'


class CompanySearchForm(forms.Form):
    """公司搜索表单"""
    SEARCH_BY_CHOICES = (
        ('name', '公司名称'),
        ('admin', '管理员'),
    )

    STATUS_CHOICES = (
        ('', '所有状态'),
        ('active', '活跃'),
        ('inactive', '已禁用'),
    )

    search_by = forms.ChoiceField(
        choices=SEARCH_BY_CHOICES,
        initial='name',
        label="搜索方式",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    keyword = forms.CharField(
        required=False,
        label="关键词",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入搜索关键词'
        })
    )

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        label="状态筛选",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    created_after = forms.DateField(
        required=False,
        label="创建时间 - 从",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    created_before = forms.DateField(
        required=False,
        label="创建时间 - 到",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    def clean(self):
        """验证日期范围"""
        cleaned_data = super().clean()
        created_after = cleaned_data.get('created_after')
        created_before = cleaned_data.get('created_before')

        if created_after and created_before:
            if created_after > created_before:
                raise ValidationError('开始日期不能晚于结束日期')

        return cleaned_data


class CompanyBulkActionForm(forms.Form):
    """公司批量操作表单"""
    ACTION_CHOICES = (
        ('activate', '激活选中公司'),
        ('deactivate', '禁用选中公司'),
    )

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        label="批量操作",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.all(),
        label="选择公司",
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'size': '10'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 可以在这里限制公司选择范围，比如只显示特定状态的公司


class CompanyInviteUserForm(forms.Form):
    """公司邀请用户表单"""
    email = forms.EmailField(
        label="邮箱地址",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入要邀请的邮箱地址'
        })
    )

    role = forms.ChoiceField(
        choices=(
            ('user', '普通用户'),
            ('admin', '管理员'),
        ),
        initial='user',
        label="用户角色",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    message = forms.CharField(
        required=False,
        label="邀请消息",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': '可选的邀请消息（可选）'
        })
    )

    def clean_email(self):
        """验证邮箱是否已被注册"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            # 检查该用户是否已经是公司成员
            # 这里需要根据具体业务逻辑实现
            raise ValidationError('该邮箱已被注册')
        return email


class CompanyStatisticsForm(forms.Form):
    """公司统计筛选表单"""
    DATE_RANGE_CHOICES = (
        ('last_7_days', '最近7天'),
        ('last_30_days', '最近30天'),
        ('last_90_days', '最近90天'),
        ('this_year', '今年'),
        ('last_year', '去年'),
        ('custom', '自定义范围'),
    )

    date_range = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        initial='last_30_days',
        label="统计时间范围",
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

    include_inactive = forms.BooleanField(
        required=False,
        initial=False,
        label="包含已禁用公司",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
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


# 工具函数和验证器
def validate_company_name_unique(value):
    """验证公司名称唯一性（独立验证器）"""
    if Company.objects.filter(name=value).exists():
        raise ValidationError(
            _('公司名称 "%(value)s" 已存在'),
            params={'value': value},
        )


def get_company_choices(include_empty=True):
    """获取公司选择列表（用于其他表单）"""
    companies = Company.objects.filter(is_active=True).order_by('name')
    choices = []

    if include_empty:
        choices.append(('', '--- 选择公司 ---'))

    for company in companies:
        choices.append((company.id, f"{company.name}"))

    return choices


class CompanySelectionForm(forms.Form):
    """公司选择表单（用于用户切换公司等场景）"""
    company = forms.ChoiceField(
        choices=[],
        label="选择公司",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # 根据用户权限动态设置公司选择
        if self.user:
            if self.user.is_superuser:
                # 超级用户可以看到所有公司
                companies = Company.objects.all()
            else:
                # 普通用户只能看到他们所属的公司
                from apps.accounts.models import UserProfile
                companies = Company.objects.filter(
                    userprofile__user=self.user
                ).distinct()

            choices = [('', '--- 选择公司 ---')]
            for company in companies:
                choices.append((company.id, f"{company.name}"))

            self.fields['company'].choices = choices