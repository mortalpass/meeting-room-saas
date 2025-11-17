# debug_user.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.accounts.models import UserProfile
from apps.companies.models import Company

User = get_user_model()


def check_current_user():
    """检查当前活跃用户的状态"""
    users = User.objects.all()
    print("=== 所有用户 ===")
    for user in users:
        has_profile = UserProfile.objects.filter(user=user).exists()
        profile_status = "有 Profile" if has_profile else "无 Profile"
        print(f"ID: {user.id}, 用户名: {user.username}, 邮箱: {user.email}, 状态: {profile_status}")

    print("\n=== 公司信息 ===")
    companies = Company.objects.all()
    for company in companies:
        print(f"公司ID: {company.id}, 名称: {company.name}, 管理员: {company.admin.username if company.admin else '无'}")


if __name__ == "__main__":
    check_current_user()