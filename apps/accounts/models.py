from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import RegexValidator
from apps.companies.models import Company


class UserProfile(models.Model):
    """用户扩展模型"""
    ROLE_CHOICES = (
        ('admin', '管理员'),
        ('user', '普通用户'),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        verbose_name="用户",
        related_name="profile"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="所属公司"
    )
    phone_regex = RegexValidator(
        regex=r'^1[3-9]\d{9}$',
        message="请输入正确的手机号码格式"
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=11,
        blank=True,
        verbose_name="手机号码"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='user',
        verbose_name="用户角色"
    )
    department = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="部门"
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
        verbose_name = "用户资料"
        verbose_name_plural = verbose_name
        db_table = 'accounts_user_profile'
        indexes = [
            models.Index(fields=['company', 'role']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.company.name}"

    @property
    def is_company_admin(self):
        """检查是否是公司管理员"""
        return self.role == 'admin' or self.company.admin == self.user


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """创建用户时自动创建用户资料"""
    if created:
        # 检查是否已经存在 profile
        if not hasattr(instance, 'profile') and not UserProfile.objects.filter(user=instance).exists():
            # 获取或创建公司
            company = Company.objects.first()
            if not company:
                company = Company.objects.create(
                    name=f"{instance.username}的公司",
                    admin=instance
                )

            # 创建用户资料
            UserProfile.objects.create(user=instance, company=company)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """保存用户时保存用户资料"""
    if hasattr(instance, 'profile'):
        instance.profile.save()