# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from apps.accounts import views as accounts_views  # 添加这行

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', accounts_views.dashboard, name='dashboard'),  # 根路径指向 dashboard
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('bookings/', include('apps.bookings.urls', namespace='bookings')),
    path('companies/', include('apps.companies.urls', namespace='companies')),
    path('common/', include('apps.common.urls', namespace='common')),

    # 认证URL
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]

# 开发环境下的媒体文件服务
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)