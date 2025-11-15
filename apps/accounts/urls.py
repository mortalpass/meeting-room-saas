from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),

    # 用户认证
    path('register/', views.register, name='register'),

    # 个人资料
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.UserProfileUpdateView.as_view(), name='profile_update'),
    path('change-password/', views.change_password, name='change_password'),

    # 公司用户管理（管理员功能）
    path('company-users/', views.CompanyUserListView.as_view(), name='company_users'),
    path('company-users/create/', views.CompanyUserCreateView.as_view(), name='company_user_create'),
    path('company-users/<int:pk>/update/', views.CompanyUserUpdateView.as_view(), name='company_user_update'),
    path('company-users/<int:pk>/toggle-active/', views.company_user_toggle_active, name='company_user_toggle_active'),

    # 公司切换
    path('switch-company/', views.switch_company, name='switch_company'),

    # 统计信息
    path('user-stats/', views.user_stats, name='user_stats'),

    # API 接口
    path('api/profile/', views.api_user_profile, name='api_profile'),
    path('api/company-users/', views.api_company_users, name='api_company_users'),
]