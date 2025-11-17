# apps/bookings/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta, date
import json

from apps.accounts.models import UserProfile
from . import models
from .models import MeetingRoom, Reservation, ReservationConfig
from .forms import (
    MeetingRoomForm, ReservationForm, ReservationSearchForm,
    ReservationConfigForm, ReservationStatusUpdateForm, QuickReservationForm,
    get_available_time_slots
)


# ==================== 会议室管理视图 ====================

@method_decorator(login_required, name='dispatch')
class MeetingRoomListView(ListView):
    """会议室列表视图"""
    model = MeetingRoom
    template_name = 'bookings/meeting_room_list.html'
    context_object_name = 'meeting_rooms'
    paginate_by = 20

    def get_queryset(self):
        """只返回当前公司的会议室"""
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        queryset = MeetingRoom.objects.filter(company=user_profile.company)

        # 搜索功能
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(location__icontains=search_query) |
                Q(remarks__icontains=search_query)
            )

        # 筛选可用状态
        availability_filter = self.request.GET.get('availability', '')
        if availability_filter == 'available':
            queryset = queryset.filter(is_available=True)
        elif availability_filter == 'unavailable':
            queryset = queryset.filter(is_available=False)

        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        context['search_query'] = self.request.GET.get('search', '')
        context['availability_filter'] = self.request.GET.get('availability', '')
        context['is_company_admin'] = user_profile.is_company_admin
        return context


@method_decorator(login_required, name='dispatch')
class MeetingRoomCreateView(CreateView):
    """创建会议室视图"""
    model = MeetingRoom
    form_class = MeetingRoomForm
    template_name = 'bookings/meeting_room_form.html'
    success_url = reverse_lazy('bookings:meeting_room_list')

    def dispatch(self, request, *args, **kwargs):
        """检查权限 - 只有公司管理员可以创建会议室"""
        user_profile = get_object_or_404(UserProfile, user=request.user)
        if not user_profile.is_company_admin:
            raise PermissionDenied("您没有权限创建会议室")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """传递当前用户公司给表单"""
        kwargs = super().get_form_kwargs()
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        kwargs['company'] = user_profile.company
        return kwargs

    def form_valid(self, form):
        """设置成功消息"""
        response = super().form_valid(form)
        messages.success(self.request, f'会议室 "{form.instance.name}" 创建成功！')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '创建会议室'
        return context


@method_decorator(login_required, name='dispatch')
class MeetingRoomUpdateView(UpdateView):
    """编辑会议室视图"""
    model = MeetingRoom
    form_class = MeetingRoomForm
    template_name = 'bookings/meeting_room_form.html'
    context_object_name = 'meeting_room'

    def dispatch(self, request, *args, **kwargs):
        """检查权限和公司归属"""
        user_profile = get_object_or_404(UserProfile, user=request.user)
        meeting_room = self.get_object()

        if not user_profile.is_company_admin or meeting_room.company != user_profile.company:
            raise PermissionDenied("您没有权限编辑此会议室")

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """传递当前用户公司给表单"""
        kwargs = super().get_form_kwargs()
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        kwargs['company'] = user_profile.company
        return kwargs

    def get_success_url(self):
        """成功后返回会议室列表"""
        messages.success(self.request, f'会议室 "{self.object.name}" 更新成功！')
        return reverse_lazy('bookings:meeting_room_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '编辑会议室'
        return context


@login_required
def meeting_room_toggle_availability(request, pk):
    """启用/禁用会议室"""
    if request.method == 'POST':
        user_profile = get_object_or_404(UserProfile, user=request.user)
        meeting_room = get_object_or_404(MeetingRoom, pk=pk)

        # 检查权限和公司归属
        if not user_profile.is_company_admin or meeting_room.company != user_profile.company:
            raise PermissionDenied("您没有权限执行此操作")

        # 切换可用状态
        meeting_room.is_available = not meeting_room.is_available
        meeting_room.save()

        status = "启用" if meeting_room.is_available else "禁用"
        messages.success(request, f'会议室 "{meeting_room.name}" 已{status}！')

    return redirect('bookings:meeting_room_list')


@method_decorator(login_required, name='dispatch')
class MeetingRoomDeleteView(DeleteView):
    """删除会议室视图"""
    model = MeetingRoom
    template_name = 'bookings/meeting_room_confirm_delete.html'
    success_url = reverse_lazy('bookings:meeting_room_list')
    context_object_name = 'meeting_room'

    def dispatch(self, request, *args, **kwargs):
        """检查权限和公司归属"""
        user_profile = get_object_or_404(UserProfile, user=request.user)
        meeting_room = self.get_object()

        if not user_profile.is_company_admin or meeting_room.company != user_profile.company:
            raise PermissionDenied("您没有权限删除此会议室")

        # 检查是否有关联的预约
        active_reservations = Reservation.objects.filter(
            meeting_room=meeting_room,
            status__in=[Reservation.STATUS_PENDING, Reservation.STATUS_CONFIRMED, Reservation.STATUS_IN_USE]
        ).exists()

        if active_reservations:
            messages.error(request, '无法删除该会议室，因为存在关联的活跃预约')
            return redirect('bookings:meeting_room_list')

        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """删除成功消息"""
        meeting_room = self.get_object()
        messages.success(request, f'会议室 "{meeting_room.name}" 删除成功！')
        return super().delete(request, *args, **kwargs)


# ==================== 预约管理视图 ====================

@method_decorator(login_required, name='dispatch')
class ReservationListView(ListView):
    """预约列表视图"""
    model = Reservation
    template_name = 'bookings/reservation_list.html'
    context_object_name = 'reservations'
    paginate_by = 20

    def get_queryset(self):
        """根据用户角色返回相应的预约"""
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        queryset = Reservation.objects.filter(company=user_profile.company)

        # 如果不是管理员，只显示自己的预约
        if not user_profile.is_company_admin:
            queryset = queryset.filter(user=self.request.user)

        # 应用搜索过滤器
        search_form = ReservationSearchForm(self.request.GET, company=user_profile.company)
        if search_form.is_valid():
            queryset = self.apply_search_filters(queryset, search_form.cleaned_data)

        return queryset.select_related('meeting_room', 'user').prefetch_related('participants').order_by('-start_time')

    def apply_search_filters(self, queryset, cleaned_data):
        """应用搜索过滤器"""
        date_range = cleaned_data.get('date_range')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        meeting_room = cleaned_data.get('meeting_room')
        status = cleaned_data.get('status')
        search = cleaned_data.get('search')

        # 日期范围过滤
        if date_range:
            today = timezone.now().date()
            if date_range == 'today':
                queryset = queryset.filter(start_time__date=today)
            elif date_range == 'tomorrow':
                tomorrow = today + timedelta(days=1)
                queryset = queryset.filter(start_time__date=tomorrow)
            elif date_range == 'this_week':
                start_of_week = today - timedelta(days=today.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                queryset = queryset.filter(start_time__date__range=[start_of_week, end_of_week])
            elif date_range == 'next_week':
                start_of_week = today - timedelta(days=today.weekday()) + timedelta(days=7)
                end_of_week = start_of_week + timedelta(days=6)
                queryset = queryset.filter(start_time__date__range=[start_of_week, end_of_week])
            elif date_range == 'this_month':
                start_of_month = today.replace(day=1)
                next_month = start_of_month.replace(day=28) + timedelta(days=4)
                end_of_month = next_month - timedelta(days=next_month.day)
                queryset = queryset.filter(start_time__date__range=[start_of_month, end_of_month])
            elif date_range == 'custom' and start_date and end_date:
                queryset = queryset.filter(start_time__date__range=[start_date, end_date])

        # 其他过滤器
        if meeting_room:
            queryset = queryset.filter(meeting_room=meeting_room)

        if status:
            queryset = queryset.filter(status=status)

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(remarks__icontains=search) |
                Q(meeting_room__name__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_profile = get_object_or_404(UserProfile, user=self.request.user)

        # 搜索表单
        search_form = ReservationSearchForm(self.request.GET, company=user_profile.company)
        context['search_form'] = search_form
        context['is_company_admin'] = user_profile.is_company_admin

        # 统计信息
        if user_profile.is_company_admin:
            total_reservations = Reservation.objects.filter(company=user_profile.company).count()
            pending_reservations = Reservation.objects.filter(
                company=user_profile.company, status=Reservation.STATUS_PENDING
            ).count()
            context['total_reservations'] = total_reservations
            context['pending_reservations'] = pending_reservations

        return context


@method_decorator(login_required, name='dispatch')
class ReservationCreateView(CreateView):
    """创建预约视图"""
    model = Reservation
    form_class = ReservationForm
    template_name = 'bookings/reservation_form.html'

    def get_success_url(self):
        """成功后返回预约列表"""
        messages.success(self.request, '预约创建成功！')
        return reverse_lazy('bookings:reservation_list')

    def dispatch(self, request, *args, **kwargs):
        """检查用户是否有权限创建预约"""
        # 所有登录用户都可以创建预约
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """传递当前用户和公司给表单"""
        kwargs = super().get_form_kwargs()
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        kwargs['company'] = user_profile.company
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '创建预约'
        return context


@method_decorator(login_required, name='dispatch')
class ReservationUpdateView(UpdateView):
    """编辑预约视图"""
    model = Reservation
    form_class = ReservationForm
    template_name = 'bookings/reservation_form.html'
    context_object_name = 'reservation'

    def dispatch(self, request, *args, **kwargs):
        """检查权限 - 用户只能编辑自己的预约，管理员可以编辑所有"""
        user_profile = get_object_or_404(UserProfile, user=request.user)
        reservation = self.get_object()

        if not user_profile.is_company_admin and reservation.user != request.user:
            raise PermissionDenied("您只能编辑自己的预约")

        # 检查预约是否可以编辑
        if not reservation.can_be_cancelled():
            messages.error(request, '该预约无法编辑，可能已经开始或已完成')
            return redirect('bookings:reservation_list')

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """传递当前用户和公司给表单"""
        kwargs = super().get_form_kwargs()
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        kwargs['company'] = user_profile.company
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        """成功后返回预约列表"""
        messages.success(self.request, '预约更新成功！')
        return reverse_lazy('bookings:reservation_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '编辑预约'
        return context


@method_decorator(login_required, name='dispatch')
class ReservationDetailView(DetailView):
    """预约详情视图"""
    model = Reservation
    template_name = 'bookings/reservation_detail.html'
    context_object_name = 'reservation'

    def dispatch(self, request, *args, **kwargs):
        """检查权限 - 用户只能查看自己的预约，管理员可以查看所有"""
        user_profile = get_object_or_404(UserProfile, user=request.user)
        reservation = self.get_object()

        if not user_profile.is_company_admin and reservation.user != request.user:
            raise PermissionDenied("您没有权限查看此预约")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        context['is_company_admin'] = user_profile.is_company_admin
        context['can_edit'] = self.object.can_be_cancelled() and (
                user_profile.is_company_admin or self.object.user == self.request.user
        )
        return context


@login_required
def reservation_cancel(request, pk):
    """取消预约"""
    if request.method == 'POST':
        user_profile = get_object_or_404(UserProfile, user=request.user)
        reservation = get_object_or_404(Reservation, pk=pk)

        # 检查权限
        if not user_profile.is_company_admin and reservation.user != request.user:
            raise PermissionDenied("您只能取消自己的预约")

        # 检查是否可以取消
        if not reservation.can_be_cancelled():
            messages.error(request, '该预约无法取消，可能已经开始或已完成')
            return redirect('bookings:reservation_list')

        # 取消预约
        reservation.status = Reservation.STATUS_CANCELLED
        reservation.save()

        messages.success(request, '预约已取消！')

    return redirect('bookings:reservation_list')


@method_decorator(login_required, name='dispatch')
class ReservationStatusUpdateView(UpdateView):
    """更新预约状态视图（管理员使用）"""
    model = Reservation
    form_class = ReservationStatusUpdateForm
    template_name = 'bookings/reservation_status_update.html'
    context_object_name = 'reservation'

    def dispatch(self, request, *args, **kwargs):
        """检查权限 - 只有管理员可以更新状态"""
        user_profile = get_object_or_404(UserProfile, user=request.user)
        if not user_profile.is_company_admin:
            raise PermissionDenied("您没有权限更新预约状态")

        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """成功后返回预约详情"""
        messages.success(self.request, f'预约状态已更新为 {self.object.get_status_display()}！')
        return reverse_lazy('bookings:reservation_detail', kwargs={'pk': self.object.pk})


# ==================== 快速预约视图 ====================

@login_required
def quick_reservation(request):
    """快速预约视图"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    if request.method == 'POST':
        form = QuickReservationForm(request.POST, company=user_profile.company)
        if form.is_valid():
            # 创建预约
            reservation = Reservation(
                company=user_profile.company,
                user=request.user,
                meeting_room=form.cleaned_data['meeting_room'],
                title=form.cleaned_data['title'],
                start_time=form.cleaned_data['start_time'],
                end_time=form.cleaned_data['end_time'],
                status=Reservation.STATUS_PENDING  # 或者根据配置自动确认
            )

            # 根据公司配置决定状态
            try:
                meeting_room = ReservationConfig.objects.get(company=user_profile.company)
                if not meeting_room.require_approval or meeting_room.auto_approval:
                    reservation.status = Reservation.STATUS_CONFIRMED
            except ReservationConfig.DoesNotExist:
                pass  # 使用默认状态

            reservation.save()

            messages.success(request, '快速预约创建成功！')
            return redirect('bookings:reservation_list')
    else:
        form = QuickReservationForm(company=user_profile.company)

    return render(request, 'bookings/quick_reservation.html', {'form': form})


# ==================== 预约配置视图 ====================

@login_required
def reservation_config(request):
    """预约配置视图"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    if not user_profile.is_company_admin:
        raise PermissionDenied("您没有权限管理预约配置")

    try:
        meeting_room = ReservationConfig.objects.get(company=user_profile.company)
    except ReservationConfig.DoesNotExist:
        meeting_room = ReservationConfig(company=user_profile.company)
        meeting_room.save()

    if request.method == 'POST':
        form = ReservationConfigForm(request.POST, instance=meeting_room)
        if form.is_valid():
            form.save()
            messages.success(request, '预约配置更新成功！')
            return redirect('bookings:reservation_meeting_room')
    else:
        form = ReservationConfigForm(instance=meeting_room)

    return render(request, 'bookings/reservation_meeting_room.html', {'form': form, 'meeting_room': meeting_room})


# ==================== 日历视图 ====================

@login_required
def reservation_calendar(request):
    """预约日历视图"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    # 获取当前日期或指定日期
    year = request.GET.get('year')
    month = request.GET.get('month')

    if year and month:
        try:
            current_date = date(int(year), int(month), 1)
        except (ValueError, TypeError):
            current_date = timezone.now().date().replace(day=1)
    else:
        current_date = timezone.now().date().replace(day=1)

    # 计算日历范围
    first_day = current_date.replace(day=1)
    last_day = (first_day + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    # 获取预约数据
    reservations = Reservation.objects.filter(
        company=user_profile.company,
        start_time__date__range=[first_day, last_day]
    ).select_related('meeting_room', 'user')

    # 如果不是管理员，只显示自己的预约
    if not user_profile.is_company_admin:
        reservations = reservations.filter(user=request.user)

    # 组织日历数据
    calendar_data = []
    current_day = first_day
    while current_day <= last_day:
        day_reservations = [
            r for r in reservations
            if r.start_time.date() <= current_day <= r.end_time.date()
        ]

        calendar_data.append({
            'date': current_day,
            'reservations': day_reservations,
            'is_today': current_day == timezone.now().date(),
            'is_weekend': current_day.weekday() >= 5
        })

        current_day += timedelta(days=1)

    # 导航日期
    prev_month = first_day - timedelta(days=1)
    next_month = (first_day + timedelta(days=32)).replace(day=1)

    context = {
        'calendar_data': calendar_data,
        'current_date': current_date,
        'prev_month': prev_month,
        'next_month': next_month,
        'is_company_admin': user_profile.is_company_admin,
    }

    return render(request, 'bookings/reservation_calendar.html', context)


# ==================== API 视图 ====================

@login_required
def api_meeting_rooms(request):
    """API: 获取会议室列表（JSON格式）"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    meeting_rooms = MeetingRoom.objects.filter(company=user_profile.company, is_available=True)

    room_list = []
    for room in meeting_rooms:
        room_list.append({
            'id': room.id,
            'name': room.name,
            'location': room.location,
            'capacity': room.capacity,
        })

    return JsonResponse({'meeting_rooms': room_list})


@login_required
def api_available_slots(request):
    """API: 获取可用时间段"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    meeting_room_id = request.GET.get('meeting_room')
    date_str = request.GET.get('date')
    duration = int(request.GET.get('duration', 60))

    try:
        meeting_room = MeetingRoom.objects.get(
            id=meeting_room_id,
            company=user_profile.company,
            is_available=True
        )
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        available_slots = get_available_time_slots(meeting_room, target_date, duration)

        # 格式化时间段
        formatted_slots = []
        for slot in available_slots:
            formatted_slots.append({
                'start': slot['start'].strftime('%Y-%m-%dT%H:%M'),
                'end': slot['end'].strftime('%Y-%m-%dT%H:%M'),
                'duration': slot['duration']
            })

        return JsonResponse({'available_slots': formatted_slots})

    except (MeetingRoom.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'available_slots': []})


@login_required
def api_reservation_stats(request):
    """API: 获取预约统计（管理员使用）"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    if not user_profile.is_company_admin:
        return JsonResponse({'error': '无权访问'}, status=403)

    # 获取统计日期范围（最近30天）
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)

    # 预约状态统计
    status_stats = Reservation.objects.filter(
        company=user_profile.company,
        created_at__date__range=[start_date, end_date]
    ).values('status').annotate(count=models.Count('id'))

    # 会议室使用统计
    room_stats = Reservation.objects.filter(
        company=user_profile.company,
        created_at__date__range=[start_date, end_date]
    ).values('meeting_room__name').annotate(count=models.Count('id')).order_by('-count')[:10]

    # 每日预约数量
    daily_stats = Reservation.objects.filter(
        company=user_profile.company,
        created_at__date__range=[start_date, end_date]
    ).extra({'date': "date(created_at)"}).values('date').annotate(count=models.Count('id')).order_by('date')

    data = {
        'status_stats': list(status_stats),
        'room_stats': list(room_stats),
        'daily_stats': list(daily_stats),
    }

    return JsonResponse(data)


@login_required
def api_check_time_conflict(request):
    """API: 检查时间冲突"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    meeting_room_id = request.GET.get('meeting_room')
    start_time_str = request.GET.get('start_time')
    end_time_str = request.GET.get('end_time')
    reservation_id = request.GET.get('reservation_id')  # 编辑预约时排除自身

    try:
        meeting_room = MeetingRoom.objects.get(
            id=meeting_room_id,
            company=user_profile.company
        )
        start_time = timezone.make_aware(datetime.fromisoformat(start_time_str))
        end_time = timezone.make_aware(datetime.fromisoformat(end_time_str))

        # 检查时间冲突
        conflicting_statuses = [
            Reservation.STATUS_PENDING,
            Reservation.STATUS_CONFIRMED,
            Reservation.STATUS_IN_USE
        ]

        conflicting = Reservation.objects.filter(
            meeting_room=meeting_room,
            status__in=conflicting_statuses,
            start_time__lt=end_time,
            end_time__gt=start_time
        )

        if reservation_id:
            conflicting = conflicting.exclude(pk=reservation_id)

        is_conflicting = conflicting.exists()

        return JsonResponse({
            'is_conflicting': is_conflicting,
            'conflicting_count': conflicting.count()
        })

    except (MeetingRoom.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'error': '参数错误'}, status=400)


# ==================== 仪表板视图 ====================

@login_required
def dashboard(request):
    """预约系统仪表板"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    # 今日预约
    today = timezone.now().date()
    today_reservations = Reservation.objects.filter(
        company=user_profile.company,
        start_time__date=today
    ).select_related('meeting_room', 'user')

    # 如果不是管理员，只显示自己的预约
    if not user_profile.is_company_admin:
        today_reservations = today_reservations.filter(user=request.user)

    # 即将开始的预约（今天和明天）
    tomorrow = today + timedelta(days=1)
    upcoming_reservations = Reservation.objects.filter(
        company=user_profile.company,
        start_time__date__range=[today, tomorrow],
        status__in=[Reservation.STATUS_PENDING, Reservation.STATUS_CONFIRMED]
    ).select_related('comeeting_roomnfig', 'user').order_by('start_time')

    if not user_profile.is_company_admin:
        upcoming_reservations = upcoming_reservations.filter(user=request.user)

    # 待处理的预约（管理员专用）
    pending_reservations = None
    if user_profile.is_company_admin:
        pending_reservations = Reservation.objects.filter(
            company=user_profile.company,
            status=Reservation.STATUS_PENDING
        ).select_related('meeting_room', 'user').order_by('start_time')

    context = {
        'today_reservations': today_reservations,
        'upcoming_reservations': upcoming_reservations,
        'pending_reservations': pending_reservations,
        'is_company_admin': user_profile.is_company_admin,
        'today': today,
    }

    return render(request, 'bookings/dashboard.html', context)