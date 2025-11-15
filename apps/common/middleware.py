# apps/common/middleware.py
from django.utils.deprecation import MiddlewareMixin
from apps.accounts.models import UserProfile


class CompanyMiddleware(MiddlewareMixin):
    """公司中间件，用于处理多租户"""

    def process_request(self, request):
        if request.user.is_authenticated:
            try:
                user_profile = UserProfile.objects.get(user=request.user)
                request.company = user_profile.company
            except UserProfile.DoesNotExist:
                request.company = None
        else:
            request.company = None