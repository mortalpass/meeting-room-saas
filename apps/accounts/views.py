from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, update_session_auth_hash, authenticate
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.generic import ListView, UpdateView, CreateView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from . import models
from .models import UserProfile
from .forms import (
    UserRegistrationForm,
    UserProfileForm,
    UserUpdateForm,
    CompanyUserCreateForm,
    CompanyUserUpdateForm
)
from apps.companies.models import Company


def register(request):
    """用户注册视图"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()  # 这里会创建User和UserProfile

            # 自动登录
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)

            return redirect('dashboard')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def dashboard(request):
    """用户仪表板"""
    return render(request, 'accounts/dashboard.html')


@login_required
def profile(request):
    """用户个人资料页面"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, instance=user_profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, '个人资料更新成功！')
            return redirect('accounts:profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = UserProfileForm(instance=user_profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def change_password(request):
    """修改密码视图"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # 保持用户登录状态
            messages.success(request, '密码修改成功！')
            return redirect('accounts:profile')
        else:
            messages.error(request, '请修正以下错误。')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'accounts/change_password.html', {'form': form})


@method_decorator(login_required, name='dispatch')
class UserProfileUpdateView(UpdateView):
    """用户资料更新视图（类视图版本）"""
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'accounts/profile_update.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        """确保用户只能编辑自己的资料"""
        return get_object_or_404(UserProfile, user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_form'] = UserUpdateForm(instance=self.request.user)
        return context


    def form_valid(self, form):
        """同时保存用户基本信息"""
        user_form = UserUpdateForm(self.request.POST, instance=self.request.user)
        if user_form.is_valid():
            user_form.save()
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class CompanyUserListView(ListView):
    """公司用户列表视图（公司管理员使用）"""
    model = UserProfile
    template_name = 'accounts/company_users.html'
    context_object_name = 'user_profiles'
    paginate_by = 20

    def get_queryset(self):
        """只返回当前公司用户，支持搜索"""
        user_profile = get_object_or_404(UserProfile, user=self.request.user)

        if not user_profile.is_company_admin:
            raise PermissionDenied("您没有权限查看此页面")

        queryset = UserProfile.objects.filter(company=user_profile.company)

        # 搜索功能
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(user__username__icontains=search_query) |
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query) |
                Q(user__email__icontains=search_query) |
                Q(department__icontains=search_query) |
                Q(phone__icontains=search_query)
            )

        return queryset.select_related('user').order_by('user__username')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


@method_decorator(login_required, name='dispatch')
class CompanyUserCreateView(CreateView):
    """创建公司用户视图（公司管理员使用）"""
    model = UserProfile
    form_class = CompanyUserCreateForm
    template_name = 'accounts/company_user_create.html'
    success_url = reverse_lazy('accounts:company_users')

    def dispatch(self, request, *args, **kwargs):
        """检查权限"""
        user_profile = get_object_or_404(UserProfile, user=request.user)
        if not user_profile.is_company_admin:
            raise PermissionDenied("您没有权限执行此操作")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """传递当前用户公司给表单"""
        kwargs = super().get_form_kwargs()
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        kwargs['company'] = user_profile.company
        return kwargs

    def form_valid(self, form):
        """设置公司并显示成功消息"""
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        form.instance.company = user_profile.company

        response = super().form_valid(form)
        messages.success(self.request, f'用户 {form.instance.user.username} 创建成功！')
        return response


@method_decorator(login_required, name='dispatch')
class CompanyUserUpdateView(UpdateView):
    """编辑公司用户视图（公司管理员使用）"""
    model = UserProfile
    form_class = CompanyUserUpdateForm
    template_name = 'accounts/company_user_update.html'
    context_object_name = 'user_profile'

    def dispatch(self, request, *args, **kwargs):
        """检查权限和公司归属"""
        user_profile = get_object_or_404(UserProfile, user=request.user)
        target_profile = self.get_object()

        if not user_profile.is_company_admin or target_profile.company != user_profile.company:
            raise PermissionDenied("您没有权限执行此操作")

        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """成功后返回用户列表"""
        messages.success(self.request, f'用户 {self.object.user.username} 更新成功！')
        return reverse_lazy('accounts:company_users')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_form'] = UserUpdateForm(instance=self.object.user)
        return context

    def form_valid(self, form):
        """同时保存用户基本信息"""
        user_form = UserUpdateForm(self.request.POST, instance=self.object.user)
        if user_form.is_valid():
            user_form.save()
        return super().form_valid(form)


@login_required
def company_user_toggle_active(request, pk):
    """启用/禁用公司用户（公司管理员使用）"""
    if request.method == 'POST':
        user_profile = get_object_or_404(UserProfile, user=request.user)
        target_profile = get_object_or_404(UserProfile, pk=pk)

        # 检查权限和公司归属
        if not user_profile.is_company_admin or target_profile.company != user_profile.company:
            raise PermissionDenied("您没有权限执行此操作")

        # 不能禁用自己
        if target_profile.user == request.user:
            messages.error(request, '不能禁用您自己的账户！')
            return redirect('accounts:company_users')

        # 切换用户活跃状态
        target_profile.user.is_active = not target_profile.user.is_active
        target_profile.user.save()

        status = "启用" if target_profile.user.is_active else "禁用"
        messages.success(request, f'用户 {target_profile.user.username} 已{status}！')

    return redirect('accounts:company_users')


@login_required
def switch_company(request):
    """切换公司视图（如果用户属于多个公司）"""
    # 注意：根据您的模型，一个用户通常属于一个公司
    # 这里预留接口，如果将来支持多公司
    user_profile = get_object_or_404(UserProfile, user=request.user)

    if request.method == 'POST':
        company_id = request.POST.get('company_id')
        try:
            new_company = Company.objects.get(pk=company_id)
            # 检查用户是否有权限访问该公司
            if UserProfile.objects.filter(user=request.user, company=new_company).exists():
                user_profile.company = new_company
                user_profile.save()
                messages.success(request, f'已切换到公司: {new_company.name}')
            else:
                messages.error(request, '您没有权限访问该公司')
        except Company.DoesNotExist:
            messages.error(request, '公司不存在')

    # 获取用户有权限的所有公司
    user_companies = Company.objects.filter(
        userprofile__user=request.user
    ).distinct()

    return render(request, 'accounts/switch_company.html', {
        'user_companies': user_companies,
        'current_company': user_profile.company
    })


@login_required
def user_stats(request):
    """用户统计信息（公司管理员使用）"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    if not user_profile.is_company_admin:
        raise PermissionDenied("您没有权限查看此页面")

    # 获取公司用户统计
    company_users = UserProfile.objects.filter(company=user_profile.company)
    total_users = company_users.count()
    active_users = company_users.filter(user__is_active=True).count()
    admin_users = company_users.filter(role='admin').count()

    # 按部门统计
    department_stats = company_users.values('department').annotate(
        count=models.Count('id')
    ).order_by('-count')

    context = {
        'total_users': total_users,
        'active_users': active_users,
        'admin_users': admin_users,
        'department_stats': department_stats,
    }

    return render(request, 'accounts/user_stats.html', context)


# API 视图
@login_required
def api_user_profile(request):
    """API: 获取当前用户资料（JSON格式）"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    data = {
        'username': request.user.username,
        'email': request.user.email,
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'phone': user_profile.phone,
        'role': user_profile.role,
        'department': user_profile.department,
        'company': user_profile.company.name,
        'is_company_admin': user_profile.is_company_admin,
    }

    return JsonResponse(data)


@login_required
def api_company_users(request):
    """API: 获取公司用户列表（JSON格式，用于AJAX）"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    if not user_profile.is_company_admin:
        return JsonResponse({'error': '无权访问'}, status=403)

    users = UserProfile.objects.filter(company=user_profile.company).select_related('user')

    user_list = []
    for profile in users:
        user_list.append({
            'id': profile.id,
            'username': profile.user.username,
            'email': profile.user.email,
            'first_name': profile.user.first_name,
            'last_name': profile.user.last_name,
            'phone': profile.phone,
            'role': profile.role,
            'department': profile.department,
            'is_active': profile.user.is_active,
            'last_login': profile.user.last_login.isoformat() if profile.user.last_login else None,
        })

    return JsonResponse({'users': user_list})