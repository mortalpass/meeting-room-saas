# apps/companies/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView,
    DeleteView, TemplateView, FormView
)
from django.views import View

from .models import Company
from .forms import (
    CompanyForm, CompanyCreateForm, CompanyUpdateForm,
    CompanySearchForm, CompanyBulkActionForm, CompanyInviteUserForm,
    CompanyStatisticsForm, CompanySelectionForm
)
from apps.accounts.models import UserProfile


class SuperuserRequiredMixin(UserPassesTestMixin):
    """要求用户是超级用户"""

    def test_func(self):
        return self.request.user.is_superuser


class CompanyAdminRequiredMixin(UserPassesTestMixin):
    """要求用户是公司管理员或超级用户"""

    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        # 检查用户是否是某个公司的管理员
        return hasattr(user, 'profile') and user.profile.is_company_admin


class CompanyListView(LoginRequiredMixin, CompanyAdminRequiredMixin, ListView):
    """公司列表视图"""
    model = Company
    template_name = 'companies/company_list.html'
    context_object_name = 'companies'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()

        # 处理搜索和筛选
        self.search_form = CompanySearchForm(self.request.GET or None)
        if self.search_form.is_valid():
            data = self.search_form.cleaned_data

            # 搜索条件
            search_by = data.get('search_by')
            keyword = data.get('keyword')
            status = data.get('status')
            created_after = data.get('created_after')
            created_before = data.get('created_before')

            if keyword:
                if search_by == 'name':
                    queryset = queryset.filter(name__icontains=keyword)
                elif search_by == 'admin':
                    queryset = queryset.filter(
                        Q(admin__username__icontains=keyword) |
                        Q(admin__first_name__icontains=keyword) |
                        Q(admin__last_name__icontains=keyword)
                    )

                    # 状态筛选
            if status == 'active':
                queryset = queryset.filter(is_active=True)
            elif status == 'inactive':
                queryset = queryset.filter(is_active=False)

            # 创建时间筛选
            if created_after:
                queryset = queryset.filter(created_at__date__gte=created_after)
            if created_before:
                queryset = queryset.filter(created_at__date__lte=created_before)

        # 排序
        queryset = queryset.select_related('admin').annotate(
            user_count=Count('userprofile'),
            room_count=Count('meetingroom')
        ).order_by('-created_at')

        return queryset


def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['search_form'] = self.search_form
    context['bulk_action_form'] = CompanyBulkActionForm()
    return context


class CompanyCreateView(LoginRequiredMixin, CompanyAdminRequiredMixin, CreateView):
    """创建公司视图"""
    model = Company
    form_class = CompanyCreateForm
    template_name = 'companies/company_form.html'
    success_url = reverse_lazy('companies:company_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'公司 "{form.instance.name}" 创建成功！')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '创建公司'
        context['submit_text'] = '创建公司'
        return context


class CompanyUpdateView(LoginRequiredMixin, CompanyAdminRequiredMixin, UpdateView):
    """更新公司视图"""
    model = Company
    form_class = CompanyUpdateForm
    template_name = 'companies/company_form.html'
    success_url = reverse_lazy('companies:company_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'公司 "{form.instance.name}" 更新成功！')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '更新公司信息'
        context['submit_text'] = '更新公司'
        return context


class CompanyDetailView(LoginRequiredMixin, CompanyAdminRequiredMixin, DetailView):
    """公司详情视图"""
    model = Company
    template_name = 'companies/company_detail.html'
    context_object_name = 'company'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.object

        # 获取公司相关统计信息
        context['user_count'] = company.userprofile_set.count()
        context['room_count'] = company.meetingroom_set.count()

        # 获取最近的活动（这里需要根据其他app的模型来完善）
        # context['recent_activities'] = ...

        return context


class CompanyDeleteView(LoginRequiredMixin, CompanyAdminRequiredMixin, DeleteView):
    """删除公司视图"""
    model = Company
    template_name = 'companies/company_confirm_delete.html'
    success_url = reverse_lazy('companies:company_list')

    def delete(self, request, *args, **kwargs):
        company = self.get_object()
        company_name = company.name
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'公司 "{company_name}" 已成功删除！')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = self.get_object()
        return context


class CompanyBulkActionView(LoginRequiredMixin, CompanyAdminRequiredMixin, View):
    """公司批量操作视图"""

    def post(self, request):
        form = CompanyBulkActionForm(request.POST)

        if form.is_valid():
            action = form.cleaned_data['action']
            companies = form.cleaned_data['companies']

            success_count = 0
            error_messages = []

            with transaction.atomic():
                for company in companies:
                    try:
                        if action == 'activate':
                            company.is_active = True
                            company.save()
                            success_count += 1
                        elif action == 'deactivate':
                            company.is_active = False
                            company.save()
                            success_count += 1
                    except Exception as e:
                        error_messages.append(f'公司 "{company.name}" 操作失败: {str(e)}')

            if success_count > 0:
                action_text = '激活' if action == 'activate' else '禁用'
                messages.success(request, f'成功{action_text}了 {success_count} 家公司')

            if error_messages:
                for error in error_messages:
                    messages.error(request, error)
        else:
            messages.error(request, '表单数据无效，请检查输入')

        return redirect('companies:company_list')


class CompanyInviteUserView(LoginRequiredMixin, CompanyAdminRequiredMixin, FormView):
    """邀请用户加入公司视图"""
    template_name = 'companies/company_invite_user.html'
    form_class = CompanyInviteUserForm
    success_url = reverse_lazy('companies:company_list')

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # 可以在这里添加额外的表单参数
        return kwargs

    def form_valid(self, form):
        email = form.cleaned_data['email']
        role = form.cleaned_data['role']
        message = form.cleaned_data['message']

        try:
            # 这里实现邀请逻辑
            # 1. 检查邮箱是否已注册
            # 2. 发送邀请邮件
            # 3. 创建邀请记录

            # 模拟邀请成功
            messages.success(
                self.request,
                f'已向 {email} 发送邀请，角色: {"管理员" if role == "admin" else "普通用户"}'
            )

        except Exception as e:
            messages.error(self.request, f'邀请发送失败: {str(e)}')
            return self.form_invalid(form)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = self.company
        return context


class CompanyStatisticsView(LoginRequiredMixin, CompanyAdminRequiredMixin, FormView):
    """公司统计视图"""
    template_name = 'companies/company_statistics.html'
    form_class = CompanyStatisticsForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = self.request.GET
        return kwargs

    def form_valid(self, form):
        # 处理表单数据并显示统计结果
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context['form']

        if form.is_valid():
            data = form.cleaned_data
            date_range = data.get('date_range')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            include_inactive = data.get('include_inactive')

            # 计算日期范围
            end_date = end_date or timezone.now().date()

            if date_range == 'last_7_days':
                start_date = end_date - timezone.timedelta(days=7)
            elif date_range == 'last_30_days':
                start_date = end_date - timezone.timedelta(days=30)
            elif date_range == 'last_90_days':
                start_date = end_date - timezone.timedelta(days=90)
            elif date_range == 'this_year':
                start_date = timezone.datetime(end_date.year, 1, 1).date()
            elif date_range == 'last_year':
                start_date = timezone.datetime(end_date.year - 1, 1, 1).date()
                end_date = timezone.datetime(end_date.year - 1, 12, 31).date()

            # 获取基础查询集
            queryset = Company.objects.all()
            if not include_inactive:
                queryset = queryset.filter(is_active=True)

            # 按创建时间筛选
            queryset = queryset.filter(
                created_at__date__range=[start_date, end_date]
            )

            # 计算统计信息
            total_companies = queryset.count()
            active_companies = queryset.filter(is_active=True).count()
            inactive_companies = total_companies - active_companies

            # 公司创建趋势（按月份）
            from django.db.models.functions import TruncMonth
            creation_trend = (
                queryset
                .annotate(month=TruncMonth('created_at'))
                .values('month')
                .annotate(count=Count('id'))
                .order_by('month')
            )

            context.update({
                'start_date': start_date,
                'end_date': end_date,
                'total_companies': total_companies,
                'active_companies': active_companies,
                'inactive_companies': inactive_companies,
                'creation_trend': list(creation_trend),
                'show_results': True,
            })

        return context


class CompanySelectionView(LoginRequiredMixin, View):
    """公司选择视图（用于用户切换公司）"""

    def get(self, request):
        form = CompanySelectionForm(user=request.user)
        return render(request, 'companies/company_selection.html', {'form': form})

    def post(self, request):
        form = CompanySelectionForm(request.POST, user=request.user)

        if form.is_valid():
            company_id = form.cleaned_data['company']

            if company_id:
                company = get_object_or_404(Company, id=company_id)

                # 更新用户当前公司（假设UserProfile有current_company字段）
                try:
                    user_profile = UserProfile.objects.get(user=request.user)
                    user_profile.current_company = company
                    user_profile.save()

                    messages.success(request, f'已切换到公司: {company.name}')

                    # 重定向到之前的页面或默认页面
                    next_url = request.GET.get('next') or reverse_lazy('dashboard')
                    return redirect(next_url)

                except UserProfile.DoesNotExist:
                    messages.error(request, '用户配置不存在')
            else:
                messages.error(request, '请选择公司')

        return render(request, 'companies/company_selection.html', {'form': form})


class CompanyDashboardView(LoginRequiredMixin, TemplateView):
    """公司仪表板视图"""
    template_name = 'companies/company_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # 获取用户相关的公司信息
        if user.is_superuser:
            # 超级用户可以看到所有公司的统计
            companies = Company.objects.all()
            total_companies = companies.count()
            active_companies = companies.filter(is_active=True).count()
        else:
            # 普通用户只能看到自己公司的信息
            user_profile = get_object_or_404(UserProfile, user=user)
            current_company = user_profile.current_company

            context['current_company'] = current_company
            context['user_count'] = current_company.userprofile_set.count()
            context['room_count'] = current_company.meetingroom_set.count()

        # 最近的活动（需要根据其他app的模型完善）
        # context['recent_activities'] = ...

        return context


class CompanyActivateView(LoginRequiredMixin, CompanyAdminRequiredMixin, View):
    """激活公司视图"""

    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        company.is_active = True
        company.save()

        messages.success(request, f'公司 "{company.name}" 已激活')
        return redirect('companies:company_list')


class CompanyDeactivateView(LoginRequiredMixin, CompanyAdminRequiredMixin, View):
    """禁用公司视图"""

    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        company.is_active = False
        company.save()

        messages.warning(request, f'公司 "{company.name}" 已禁用')
        return redirect('companies:company_list')


class CompanyUsersView(LoginRequiredMixin, CompanyAdminRequiredMixin, DetailView):
    """公司用户管理视图"""
    model = Company
    template_name = 'companies/company_users.html'
    context_object_name = 'company'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.object

        # 获取公司所有用户
        users = UserProfile.objects.filter(company=company).select_related('user')
        context['users'] = users

        return context


class CompanyAPIView(LoginRequiredMixin, View):
    """公司相关API接口"""

    def get(self, request):
        """获取公司数据（用于AJAX请求）"""
        action = request.GET.get('action')

        if action == 'user_count':
            company_id = request.GET.get('company_id')
            company = get_object_or_404(Company, id=company_id)
            user_count = company.userprofile_set.count()

            return JsonResponse({
                'success': True,
                'user_count': user_count
            })

        return JsonResponse({'success': False, 'error': '未知操作'})


# 工具函数
def get_user_companies(user):
    """获取用户可访问的公司列表"""
    if user.is_superuser:
        return Company.objects.all()
    else:
        return Company.objects.filter(
            Q(admin=user) | Q(userprofile__user=user)
        ).distinct()


def can_manage_company(user, company):
    """检查用户是否有权限管理指定公司"""
    if user.is_superuser:
        return True
    return company.admin == user or company.userprofile_set.filter(user=user, is_admin=True).exists()
