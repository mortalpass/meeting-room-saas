from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import UserProfile, Company


class UserRegistrationForm(UserCreationForm):
    """用户注册表单"""
    email = forms.EmailField(
        required=True,
        label="邮箱",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': '请输入邮箱地址'})
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        label="名字",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入名字'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        label="姓氏",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入姓氏'})
    )
    phone = forms.CharField(
        max_length=11,
        required=False,
        label="手机号码",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入手机号码'})
    )
    company_name = forms.CharField(
        max_length=100,
        required=False,
        label="公司名称",
        help_text="如果您是新公司，请填写公司名称。如果已有公司，请留空并在注册后联系管理员邀请。",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入公司名称（可选）'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
        labels = {
            'username': '用户名',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入用户名'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 为密码字段添加Bootstrap类
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': '请输入密码'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': '请确认密码'})

    def clean_email(self):
        """验证邮箱是否唯一"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('该邮箱已被注册')
        return email

    def clean_phone(self):
        """验证手机号码格式"""
        phone = self.cleaned_data.get('phone')
        if phone:
            from django.core.validators import RegexValidator
            phone_regex = RegexValidator(
                regex=r'^1[3-9]\d{9}$',
                message="请输入正确的手机号码格式"
            )
            try:
                phone_regex(phone)
            except ValidationError:
                raise ValidationError('请输入正确的手机号码格式')

            # 检查手机号是否已被使用
            if UserProfile.objects.filter(phone=phone).exists():
                raise ValidationError('该手机号码已被使用')
        return phone

    def save(self, commit=True):
        """保存用户并创建用户资料"""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')

        if commit:
            user.save()

            # 处理公司逻辑
            company_name = self.cleaned_data.get('company_name')
            if company_name:
                # 创建新公司，该用户作为管理员
                company = Company.objects.create(
                    name=company_name,
                    admin=user
                )
                # 创建用户资料，角色为管理员
                UserProfile.objects.create(
                    user=user,
                    company=company,
                    phone=self.cleaned_data.get('phone', ''),
                    role='admin'
                )
            else:
                # 如果没有提供公司名称，使用默认公司或第一个公司
                company = Company.objects.first()
                if not company:
                    company = Company.objects.create(
                        name=f"{user.username}的公司",
                        admin=user
                    )
                # 创建用户资料，角色为普通用户
                UserProfile.objects.create(
                    user=user,
                    company=company,
                    phone=self.cleaned_data.get('phone', ''),
                    role='user'
                )

        return user


class UserUpdateForm(forms.ModelForm):
    """用户基本信息更新表单"""
    email = forms.EmailField(
        required=True,
        label="邮箱",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        labels = {
            'username': '用户名',
            'first_name': '名字',
            'last_name': '姓氏',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        """验证邮箱唯一性，排除当前用户"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('该邮箱已被其他用户使用')
        return email


class UserProfileForm(forms.ModelForm):
    """用户资料表单"""

    class Meta:
        model = UserProfile
        fields = ['phone', 'department']
        labels = {
            'phone': '手机号码',
            'department': '部门',
        }
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入手机号码'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入部门'}),
        }

    def clean_phone(self):
        """验证手机号码格式和唯一性"""
        phone = self.cleaned_data.get('phone')
        if phone:
            from django.core.validators import RegexValidator
            phone_regex = RegexValidator(
                regex=r'^1[3-9]\d{9}$',
                message="请输入正确的手机号码格式"
            )
            try:
                phone_regex(phone)
            except ValidationError:
                raise ValidationError('请输入正确的手机号码格式')

            # 检查手机号是否已被其他用户使用
            if UserProfile.objects.filter(phone=phone).exclude(pk=self.instance.pk).exists():
                raise ValidationError('该手机号码已被其他用户使用')
        return phone


class CompanyUserCreateForm(forms.ModelForm):
    """公司管理员创建用户表单"""
    username = forms.CharField(
        max_length=150,
        label="用户名",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入用户名'})
    )
    email = forms.EmailField(
        label="邮箱",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': '请输入邮箱地址'})
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        label="名字",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入名字'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        label="姓氏",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入姓氏'})
    )
    password1 = forms.CharField(
        label="密码",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '请输入密码'})
    )
    password2 = forms.CharField(
        label="确认密码",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '请确认密码'})
    )

    class Meta:
        model = UserProfile
        fields = ['phone', 'department', 'role']
        labels = {
            'phone': '手机号码',
            'department': '部门',
            'role': '用户角色',
        }
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入手机号码'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入部门'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

    def clean_username(self):
        """验证用户名唯一性"""
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError('该用户名已被使用')
        return username

    def clean_email(self):
        """验证邮箱唯一性"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('该邮箱已被注册')
        return email

    def clean_phone(self):
        """验证手机号码格式和唯一性"""
        phone = self.cleaned_data.get('phone')
        if phone:
            from django.core.validators import RegexValidator
            phone_regex = RegexValidator(
                regex=r'^1[3-9]\d{9}$',
                message="请输入正确的手机号码格式"
            )
            try:
                phone_regex(phone)
            except ValidationError:
                raise ValidationError('请输入正确的手机号码格式')

            if UserProfile.objects.filter(phone=phone).exists():
                raise ValidationError('该手机号码已被使用')
        return phone

    def clean_password2(self):
        """验证两次密码是否一致"""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError('两次输入的密码不一致')
        return password2

    def save(self, commit=True):
        """创建用户和用户资料"""
        # 创建User对象
        user = User(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data.get('first_name', ''),
            last_name=self.cleaned_data.get('last_name', ''),
        )
        user.set_password(self.cleaned_data['password1'])

        if commit:
            user.save()

            # 创建UserProfile对象
            user_profile = super().save(commit=False)
            user_profile.user = user
            user_profile.company = self.company

            if commit:
                user_profile.save()

        return user_profile


class CompanyUserUpdateForm(forms.ModelForm):
    """公司管理员更新用户表单"""
    email = forms.EmailField(
        label="邮箱",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        label="名字",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        label="姓氏",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = UserProfile
        fields = ['phone', 'department', 'role']
        labels = {
            'phone': '手机号码',
            'department': '部门',
            'role': '用户角色',
        }
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初始化用户基本信息
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name

    def clean_email(self):
        """验证邮箱唯一性，排除当前用户"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.user.pk).exists():
            raise ValidationError('该邮箱已被其他用户使用')
        return email

    def clean_phone(self):
        """验证手机号码格式和唯一性"""
        phone = self.cleaned_data.get('phone')
        if phone:
            from django.core.validators import RegexValidator
            phone_regex = RegexValidator(
                regex=r'^1[3-9]\d{9}$',
                message="请输入正确的手机号码格式"
            )
            try:
                phone_regex(phone)
            except ValidationError:
                raise ValidationError('请输入正确的手机号码格式')

            if UserProfile.objects.filter(phone=phone).exclude(pk=self.instance.pk).exists():
                raise ValidationError('该手机号码已被其他用户使用')
        return phone

    def save(self, commit=True):
        """同时更新User和UserProfile"""
        user_profile = super().save(commit=False)

        # 更新User对象
        user = user_profile.user
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')

        if commit:
            user.save()
            user_profile.save()

        return user_profile


class UserInvitationForm(forms.Form):
    """用户邀请表单（可选功能）"""
    email = forms.EmailField(
        label="邮箱地址",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': '请输入要邀请的邮箱地址'})
    )
    role = forms.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        initial='user',
        label="用户角色",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    department = forms.CharField(
        max_length=50,
        required=False,
        label="部门",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入部门（可选）'})
    )

    def clean_email(self):
        """验证邮箱是否已被注册"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('该邮箱已被注册')
        return email