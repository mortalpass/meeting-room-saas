# common/middleware.py
from django.shortcuts import redirect
from django.contrib import messages
from apps.accounts.models import UserProfile
from apps.companies.models import Company


class UserProfileMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 跳过静态文件和管理员界面
        if (request.path.startswith('/static/') or
                request.path.startswith('/admin/') or
                request.path.startswith('/media/')):
            return self.get_response(request)

        if request.user.is_authenticated:
            try:
                # 检查是否有 profile
                request.user.profile
            except UserProfile.DoesNotExist:
                # 尝试自动创建 profile
                profile_created = self._create_user_profile(request.user)

                if not profile_created and request.path != '/profile-error/':
                    # 如果创建失败且不在错误页面，重定向到错误页面
                    return redirect('/profile-error/')

        response = self.get_response(request)
        return response

    def _create_user_profile(self, user):
        """尝试为用户创建 profile"""
        try:
            company = Company.objects.first()
            if not company:
                company = Company.objects.create(
                    name="默认公司",
                    admin=user if user.is_superuser else None
                )

            UserProfile.objects.create(
                user=user,
                company=company,
                role='admin' if user.is_superuser else 'user'
            )
            return True
        except Exception as e:
            print(f"为用户 {user.username} 创建 Profile 失败: {e}")
            return False