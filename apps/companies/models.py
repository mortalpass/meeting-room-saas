from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
from django.utils import timezone


class Company(models.Model):
    """公司/租户模型"""
    name = models.CharField(
        max_length=100,
        verbose_name="公司名称",
        validators=[MinLengthValidator(2)]
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )
    admin = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="管理员",
        related_name="managed_companies"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="是否激活"
    )

    class Meta:
        verbose_name = "公司"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        db_table = 'companies'  # 明确指定表名

    def __str__(self):
        return self.name

    @property
    def user_count(self):
        """获取公司用户数量"""
        return self.userprofile_set.count()

    @property
    def room_count(self):
        """获取公司会议室数量"""
        return self.meetingroom_set.count()