# apps/companies/urls.py
from django.urls import path
from . import views

app_name = 'companies'

urlpatterns = [
    # 公司列表和搜索
    path('', views.CompanyListView.as_view(), name='company_list'),

    # 公司创建、更新、删除
    path('create/', views.CompanyCreateView.as_view(), name='company_create'),
    path('<int:pk>/update/', views.CompanyUpdateView.as_view(), name='company_update'),
    path('<int:pk>/delete/', views.CompanyDeleteView.as_view(), name='company_delete'),
    path('<int:pk>/', views.CompanyDetailView.as_view(), name='company_detail'),

    # 公司状态管理
    path('<int:pk>/activate/', views.CompanyActivateView.as_view(), name='company_activate'),
    path('<int:pk>/deactivate/', views.CompanyDeactivateView.as_view(), name='company_deactivate'),

    # 批量操作
    path('bulk-action/', views.CompanyBulkActionView.as_view(), name='company_bulk_action'),

    # 用户管理
    path('<int:pk>/users/', views.CompanyUsersView.as_view(), name='company_users'),
    path('<int:pk>/invite-user/', views.CompanyInviteUserView.as_view(), name='company_invite_user'),

    # 统计和报表
    path('statistics/', views.CompanyStatisticsView.as_view(), name='company_statistics'),

    # 公司选择和切换
    path('selection/', views.CompanySelectionView.as_view(), name='company_selection'),

    # 仪表板
    path('dashboard/', views.CompanyDashboardView.as_view(), name='company_dashboard'),

    # API接口
    path('api/', views.CompanyAPIView.as_view(), name='company_api'),
]