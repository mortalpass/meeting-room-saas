# apps/common/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView,
    DeleteView, TemplateView, FormView, View
)
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from .models import AuditLog, SystemNotification
from .forms import (
    AuditLogSearchForm, AuditLogExportForm, AuditLogDetailForm,
    SystemNotificationForm, SystemNotificationCreateForm,
    SystemNotificationSearchForm, SystemNotificationBulkActionForm,
    NotificationSettingsForm, SystemNotificationFilterForm
)
from apps.companies.models import Company

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
class AuditLogListView(LoginRequiredMixin, CompanyAdminRequiredMixin, ListView):
    """审计日志列表视图"""
    model = AuditLog
    template_name = 'common/audit_log_list.html'
    context_object_name = 'audit_logs'
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset().select_related('user', 'company')

        # 处理搜索和筛选
        self.search_form = AuditLogSearchForm(
            self.request.GET or None,
            current_user=self.request.user
        )

        if self.search_form.is_valid():
            data = self.search_form.cleaned_data

            # 时间范围筛选
            date_range = data.get('date_range')
            start_date = data.get('start_date')
            end_date = data.get('end_date')

            if date_range:
                end_date = end_date or timezone.now().date()

                if date_range == 'today':
                    start_date = end_date
                elif date_range == 'last_7_days':
                    start_date = end_date - timezone.timedelta(days=7)
                elif date_range == 'last_30_days':
                    start_date = end_date - timezone.timedelta(days=30)
                elif date_range == 'last_90_days':
                    start_date = end_date - timezone.timedelta(days=90)

                if start_date:
                    queryset = queryset.filter(
                        timestamp__date__range=[start_date, end_date]
                    )

            # 其他筛选条件
            action = data.get('action')
            company = data.get('company')
            user = data.get('user')
            model_name = data.get('model_name')
            keyword = data.get('keyword')

            if action:
                queryset = queryset.filter(action=action)
            if company:
                queryset = queryset.filter(company=company)
            if user:
                queryset = queryset.filter(user=user)
            if model_name:
                queryset = queryset.filter(model_name__icontains=model_name)
            if keyword:
                queryset = queryset.filter(description__icontains=keyword)

        # 权限过滤 - 非超级用户只能看到自己公司的日志
        if not self.request.user.is_superuser:
            user_companies = Company.objects.filter(
                userprofile__user=self.request.user
            ).distinct()
            queryset = queryset.filter(company__in=user_companies)

        return queryset.order_by('-timestamp')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = self.search_form
        context['export_form'] = AuditLogExportForm()
        return context


class AuditLogDetailView(LoginRequiredMixin, CompanyAdminRequiredMixin, DetailView):
    """审计日志详情视图"""
    model = AuditLog
    template_name = 'common/audit_log_detail.html'
    context_object_name = 'audit_log'

    def get_queryset(self):
        queryset = super().get_queryset()
        # 权限过滤
        if not self.request.user.is_superuser:
            user_companies = Company.objects.filter(
                userprofile__user=self.request.user
            ).distinct()
            queryset = queryset.filter(company__in=user_companies)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['detail_form'] = AuditLogDetailForm(instance=self.object)
        return context


class AuditLogExportView(LoginRequiredMixin, CompanyAdminRequiredMixin, FormView):
    """审计日志导出视图"""
    template_name = 'common/audit_log_export.html'
    form_class = AuditLogExportForm

    def form_valid(self, form):
        import csv
        import xlwt
        from io import BytesIO

        data = form.cleaned_data
        format_type = data.get('format')
        include_columns = data.get('include_columns')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        # 获取审计日志数据
        queryset = AuditLog.objects.filter(
            timestamp__date__range=[start_date, end_date]
        ).select_related('user', 'company')

        # 权限过滤
        if not self.request.user.is_superuser:
            user_companies = Company.objects.filter(
                userprofile__user=self.request.user
            ).distinct()
            queryset = queryset.filter(company__in=user_companies)

        # 列映射
        column_mapping = {
            'timestamp': '操作时间',
            'user': '操作用户',
            'action': '操作类型',
            'model_name': '模型名称',
            'object_id': '对象ID',
            'description': '操作描述',
            'ip_address': 'IP地址',
            'company': '公司',
        }

        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="audit_logs_{start_date}_to_{end_date}.csv"'

            writer = csv.writer(response)
            # 写入标题
            headers = [column_mapping[col] for col in include_columns]
            writer.writerow(headers)

            # 写入数据
            for log in queryset:
                row = []
                for col in include_columns:
                    if col == 'user':
                        value = str(log.user) if log.user else ''
                    elif col == 'company':
                        value = str(log.company) if log.company else ''
                    else:
                        value = getattr(log, col)
                    row.append(str(value) if value else '')
                writer.writerow(row)

            return response

        elif format_type == 'excel':
            response = HttpResponse(content_type='application/ms-excel')
            response['Content-Disposition'] = f'attachment; filename="audit_logs_{start_date}_to_{end_date}.xls"'

            wb = xlwt.Workbook(encoding='utf-8')
            ws = wb.add_sheet('审计日志')

            # 设置样式
            header_style = xlwt.XFStyle()
            header_style.font.bold = True

            # 写入标题
            for col_idx, col in enumerate(include_columns):
                ws.write(0, col_idx, column_mapping[col], header_style)

            # 写入数据
            for row_idx, log in enumerate(queryset, 1):
                for col_idx, col in enumerate(include_columns):
                    if col == 'user':
                        value = str(log.user) if log.user else ''
                    elif col == 'company':
                        value = str(log.company) if log.company else ''
                    else:
                        value = getattr(log, col)
                    ws.write(row_idx, col_idx, str(value) if value else '')

            wb.save(response)
            return response

        else:
            messages.error(self.request, '暂不支持该导出格式')
            return redirect('common:audit_log_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '导出审计日志'
        return context


class SystemNotificationListView(LoginRequiredMixin, CompanyAdminRequiredMixin, ListView):
    """系统通知列表视图"""
    model = SystemNotification
    template_name = 'common/system_notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related('user', 'company')

        # 处理搜索和筛选
        self.search_form = SystemNotificationSearchForm(
            self.request.GET or None,
            current_user=self.request.user
        )

        if self.search_form.is_valid():
            data = self.search_form.cleaned_data

            # 时间范围筛选
            date_range = data.get('date_range')
            start_date = data.get('start_date')
            end_date = data.get('end_date')

            if date_range:
                end_date = end_date or timezone.now().date()

                if date_range == 'today':
                    start_date = end_date
                elif date_range == 'last_7_days':
                    start_date = end_date - timezone.timedelta(days=7)
                elif date_range == 'last_30_days':
                    start_date = end_date - timezone.timedelta(days=30)

                if start_date:
                    queryset = queryset.filter(
                        created_at__date__range=[start_date, end_date]
                    )

            # 其他筛选条件
            notification_type = data.get('notification_type')
            status = data.get('status')
            company = data.get('company')
            keyword = data.get('keyword')

            if notification_type:
                queryset = queryset.filter(type=notification_type)
            if status == 'read':
                queryset = queryset.filter(is_read=True)
            elif status == 'unread':
                queryset = queryset.filter(is_read=False)
            if company:
                queryset = queryset.filter(company=company)
            if keyword:
                queryset = queryset.filter(
                    Q(title__icontains=keyword) | Q(message__icontains=keyword)
                )

        # 权限过滤
        if not self.request.user.is_superuser:
            user_companies = Company.objects.filter(
                userprofile__user=self.request.user
            ).distinct()
            queryset = queryset.filter(company__in=user_companies)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = self.search_form
        context['bulk_action_form'] = SystemNotificationBulkActionForm(
            current_user=self.request.user
        )
        return context


class SystemNotificationCreateView(LoginRequiredMixin, CompanyAdminRequiredMixin, CreateView):
    """系统通知创建视图"""
    model = SystemNotification
    form_class = SystemNotificationCreateForm
    template_name = 'common/system_notification_form.html'
    success_url = reverse_lazy('common:system_notification_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        users = form.cleaned_data.get('users', [])

        if users:
            # 批量发送给多个用户
            with transaction.atomic():
                for user in users:
                    notification = SystemNotification(
                        company=form.cleaned_data['company'],
                        user=user,
                        type=form.cleaned_data['type'],
                        title=form.cleaned_data['title'],
                        message=form.cleaned_data['message'],
                        related_object_id=form.cleaned_data.get('related_object_id', ''),
                        related_content_type=form.cleaned_data.get('related_content_type', ''),
                    )
                    notification.save()

            messages.success(self.request, f'已成功向 {len(users)} 个用户发送通知')
        else:
            # 单个用户发送
            response = super().form_valid(form)
            messages.success(self.request, f'通知 "{form.instance.title}" 发送成功！')
            return response

        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '发送系统通知'
        context['submit_text'] = '发送通知'
        return context


class SystemNotificationDetailView(LoginRequiredMixin, CompanyAdminRequiredMixin, DetailView):
    """系统通知详情视图"""
    model = SystemNotification
    template_name = 'common/system_notification_detail.html'
    context_object_name = 'notification'

    def get_queryset(self):
        queryset = super().get_queryset()
        # 权限过滤
        if not self.request.user.is_superuser:
            user_companies = Company.objects.filter(
                userprofile__user=self.request.user
            ).distinct()
            queryset = queryset.filter(company__in=user_companies)
        return queryset

    def get(self, request, *args, **kwargs):
        # 标记为已读
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save()
        return super().get(request, *args, **kwargs)


class SystemNotificationDeleteView(LoginRequiredMixin, CompanyAdminRequiredMixin, DeleteView):
    """系统通知删除视图"""
    model = SystemNotification
    template_name = 'common/system_notification_confirm_delete.html'
    success_url = reverse_lazy('common:system_notification_list')

    def get_queryset(self):
        queryset = super().get_queryset()
        # 权限过滤
        if not self.request.user.is_superuser:
            user_companies = Company.objects.filter(
                userprofile__user=self.request.user
            ).distinct()
            queryset = queryset.filter(company__in=user_companies)
        return queryset

    def delete(self, request, *args, **kwargs):
        notification = self.get_object()
        notification_title = notification.title
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'通知 "{notification_title}" 已成功删除！')
        return response


class SystemNotificationBulkActionView(LoginRequiredMixin, CompanyAdminRequiredMixin, View):
    """系统通知批量操作视图"""

    def post(self, request):
        form = SystemNotificationBulkActionForm(
            request.POST,
            current_user=request.user
        )

        if form.is_valid():
            action = form.cleaned_data['action']
            notifications = form.cleaned_data['notifications']

            success_count = 0
            error_messages = []

            with transaction.atomic():
                for notification in notifications:
                    try:
                        if action == 'mark_read':
                            notification.is_read = True
                            notification.save()
                            success_count += 1
                        elif action == 'mark_unread':
                            notification.is_read = False
                            notification.save()
                            success_count += 1
                        elif action == 'delete':
                            notification.delete()
                            success_count += 1
                    except Exception as e:
                        error_messages.append(f'通知 "{notification.title}" 操作失败: {str(e)}')

            if success_count > 0:
                action_text = {
                    'mark_read': '标记为已读',
                    'mark_unread': '标记为未读',
                    'delete': '删除'
                }.get(action, '操作')
                messages.success(request, f'成功对 {success_count} 条通知执行了{action_text}操作')

            if error_messages:
                for error in error_messages:
                    messages.error(request, error)
        else:
            messages.error(request, '表单数据无效，请检查输入')

        return redirect('common:system_notification_list')


class UserNotificationListView(LoginRequiredMixin, ListView):
    """用户个人通知列表视图"""
    model = SystemNotification
    template_name = 'common/user_notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 15

    def get_queryset(self):
        queryset = SystemNotification.objects.filter(user=self.request.user)

        # 处理筛选
        self.filter_form = SystemNotificationFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data

            notification_type = data.get('notification_type')
            is_read = data.get('is_read')

            if notification_type:
                queryset = queryset.filter(type=notification_type)
            if is_read == 'true':
                queryset = queryset.filter(is_read=True)
            elif is_read == 'false':
                queryset = queryset.filter(is_read=False)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        context['unread_count'] = SystemNotification.objects.filter(
            user=self.request.user, is_read=False
        ).count()
        return context


class UserNotificationDetailView(LoginRequiredMixin, DetailView):
    """用户个人通知详情视图"""
    model = SystemNotification
    template_name = 'common/user_notification_detail.html'
    context_object_name = 'notification'

    def get_queryset(self):
        return SystemNotification.objects.filter(user=self.request.user)

    def get(self, request, *args, **kwargs):
        # 标记为已读
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save()
        return super().get(request, *args, **kwargs)


class NotificationSettingsView(LoginRequiredMixin, FormView):
    """通知设置视图"""
    template_name = 'common/notification_settings.html'
    form_class = NotificationSettingsForm
    success_url = reverse_lazy('common:notification_settings')

    def get_initial(self):
        # 这里可以从用户配置中加载保存的设置
        # 暂时返回默认值
        return {
            'reservation_created': True,
            'reservation_approved': True,
            'reservation_rejected': True,
            'reservation_cancelled': True,
            'reservation_reminder': True,
            'system_notifications': True,
            'email_notifications': False,
            'push_notifications': True,
            'reminder_time': '30',
        }

    def form_valid(self, form):
        # 这里可以保存用户的通知设置到用户配置中
        messages.success(self.request, '通知设置已保存！')
        return super().form_valid(form)


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    """标记所有通知为已读视图"""

    def post(self, request):
        updated_count = SystemNotification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True)

        messages.success(request, f'已标记 {updated_count} 条通知为已读')
        return redirect('common:user_notification_list')


class AuditLogStatisticsView(LoginRequiredMixin, CompanyAdminRequiredMixin, TemplateView):
    """审计日志统计视图"""
    template_name = 'common/audit_log_statistics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 获取基础查询集
        queryset = AuditLog.objects.all()

        # 权限过滤
        if not self.request.user.is_superuser:
            user_companies = Company.objects.filter(
                userprofile__user=self.request.user
            ).distinct()
            queryset = queryset.filter(company__in=user_companies)

        # 最近30天的数据
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_logs = queryset.filter(timestamp__gte=thirty_days_ago)

        # 操作类型统计
        action_stats = (
            recent_logs.values('action')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # 用户活动统计
        user_stats = (
            recent_logs.filter(user__isnull=False)
            .values('user__username')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # 公司活动统计
        company_stats = (
            recent_logs.filter(company__isnull=False)
            .values('company__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # 每日活动趋势
        from django.db.models.functions import TruncDate
        daily_trend = (
            recent_logs.annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

        context.update({
            'action_stats': list(action_stats),
            'user_stats': list(user_stats),
            'company_stats': list(company_stats),
            'daily_trend': list(daily_trend),
            'total_actions': recent_logs.count(),
            'unique_users': recent_logs.values('user').distinct().count(),
            'unique_companies': recent_logs.values('company').distinct().count(),
        })

        return context


# API 视图
class NotificationCountAPIView(LoginRequiredMixin, View):
    """获取未读通知数量API"""

    def get(self, request):
        unread_count = SystemNotification.objects.filter(
            user=request.user, is_read=False
        ).count()

        return JsonResponse({
            'success': True,
            'unread_count': unread_count
        })


class MarkNotificationReadAPIView(LoginRequiredMixin, View):
    """标记通知为已读API"""

    def post(self, request, pk):
        try:
            notification = SystemNotification.objects.get(
                pk=pk, user=request.user
            )
            notification.is_read = True
            notification.save()

            return JsonResponse({
                'success': True,
                'message': '通知已标记为已读'
            })
        except SystemNotification.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '通知不存在'
            }, status=404)


# 工具函数
@login_required
def create_audit_log(request, action, model_name, object_id, description, company=None):
    """创建审计日志记录的工具函数"""
    audit_log = AuditLog(
        company=company,
        user=request.user if request.user.is_authenticated else None,
        action=action,
        model_name=model_name,
        object_id=str(object_id),
        description=description,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    audit_log.save()
    return audit_log


def get_client_ip(request):
    """获取客户端IP地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@login_required
@require_http_methods(["POST"])
def quick_delete_notification(request, pk):
    """快速删除通知"""
    try:
        notification = SystemNotification.objects.get(pk=pk, user=request.user)
        notification_title = notification.title
        notification.delete()
        messages.success(request, f'通知 "{notification_title}" 已删除')
    except SystemNotification.DoesNotExist:
        messages.error(request, '通知不存在或无权访问')

    return redirect('common:user_notification_list')