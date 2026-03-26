# volunteers/admin.py
from django.contrib import admin
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Count, Q
from datetime import datetime, timedelta
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import (
    UserProfile, VerificationLog, EmailVerificationCode, 
    DataAccessLog, Announcement, Guide, Feedback, 
    VolunteerActivity, ActivityApplication, SystemSettingManager
)

def is_admin(user):
    """检查用户是否是管理员"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_published', 'created_at']
    list_filter = ['is_published', 'created_at']
    search_fields = ['title', 'content']

@admin.register(Guide)
class GuideAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'order', 'is_published']
    list_filter = ['category', 'is_published']
    search_fields = ['title', 'content']

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['content', 'user__username']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'real_name', 'phone_number', 'role', 'verification_status', 'submitted_at']
    list_filter = ['verification_status', 'role', 'organization_type']
    search_fields = ['real_name', 'id_card_number', 'phone_number', 'organization_name']
    list_per_page = 20
    readonly_fields = ['user', 'submitted_at']
    actions = ['approve_selected', 'reject_selected', 'request_update']
    
    fieldsets = (
        ('用户信息', {
            'fields': ('user', 'role', 'verification_status')
        }),
        ('个人信息', {
            'fields': ('real_name', 'phone_number', 'id_card_number', 'current_address')
        }),
        ('紧急联系人', {
            'fields': ('emergency_contact', 'emergency_phone')
        }),
        ('志愿者信息', {
            'fields': ('volunteer_experience', 'skills', 'available_time'),
            'classes': ('collapse',)
        }),
        ('组织信息', {
            'fields': ('organization_name', 'organization_type', 'organization_description', 'organization_certificate'),
            'classes': ('collapse',)
        }),
        ('证明文件', {
            'fields': ('identity_document', 'additional_documents'),
            'classes': ('collapse',)
        }),
        ('审核信息', {
            'fields': ('submitted_at', 'reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('隐私设置', {
            'fields': ('data_consent', 'last_data_access'),
            'classes': ('collapse',)
        }),
    )
    
    def approve_selected(self, request, queryset):
        for profile in queryset:
            profile.verification_status = 'approved'
            profile.reviewed_by = request.user
            profile.reviewed_at = timezone.now()
            profile.save()
            
            VerificationLog.objects.create(
                profile=profile,
                action='approve',
                performed_by=request.user,
                notes=f'管理员批量审核通过 - {profile.review_notes if profile.review_notes else "无备注"}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
        self.message_user(request, f"已批准 {queryset.count()} 个认证申请")
    
    def reject_selected(self, request, queryset):
        for profile in queryset:
            profile.verification_status = 'rejected'
            profile.reviewed_by = request.user
            profile.reviewed_at = timezone.now()
            profile.save()
            
            VerificationLog.objects.create(
                profile=profile,
                action='reject',
                performed_by=request.user,
                notes=f'管理员批量审核拒绝 - {profile.review_notes if profile.review_notes else "无备注"}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
        self.message_user(request, f"已拒绝 {queryset.count()} 个认证申请")
    
    def request_update(self, request, queryset):
        for profile in queryset:
            profile.verification_status = 'needs_review'
            profile.reviewed_by = request.user
            profile.reviewed_at = timezone.now()
            profile.save()
            
            VerificationLog.objects.create(
                profile=profile,
                action='request_update',
                performed_by=request.user,
                notes=f'需要补充资料 - {profile.review_notes if profile.review_notes else "请补充完整信息"}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
        self.message_user(request, f"已标记 {queryset.count()} 个申请需要补充资料")
    
    approve_selected.short_description = "✅ 通过选中的认证"
    reject_selected.short_description = "❌ 拒绝选中的认证"
    request_update.short_description = "📝 要求补充资料"

@admin.register(VerificationLog)
class VerificationLogAdmin(admin.ModelAdmin):
    list_display = ['profile', 'action', 'performed_by', 'performed_at']
    list_filter = ['action', 'performed_at']
    search_fields = ['profile__real_name', 'notes']
    readonly_fields = ['performed_at']
    date_hierarchy = 'performed_at'

@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ['email', 'code', 'purpose', 'created_at', 'is_used']
    list_filter = ['purpose', 'is_used']
    search_fields = ['email']
    readonly_fields = ['created_at']

@admin.register(DataAccessLog)
class DataAccessLogAdmin(admin.ModelAdmin):
    list_display = ['admin_user', 'accessed_profile', 'access_type', 'accessed_at']
    list_filter = ['access_type', 'accessed_at']
    search_fields = ['admin_user__username', 'accessed_profile__real_name']
    readonly_fields = ['accessed_at']

# ==================== 活动管理功能 ====================

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def admin_activities(request):
    """活动管理页面 - 查看所有活动"""
    # 获取筛选参数
    status = request.GET.get('status', 'all')
    search = request.GET.get('search', '')
    organizer_id = request.GET.get('organizer', '')
    
    # 基础查询
    activities = VolunteerActivity.objects.all().order_by('-created_at')
    
    # 状态筛选
    if status != 'all':
        activities = activities.filter(status=status)
    
    # 搜索筛选
    if search:
        activities = activities.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(location__icontains=search)
        )
    
    # 组织者筛选
    if organizer_id and organizer_id.isdigit():
        activities = activities.filter(organizer_id=organizer_id)
    
    # 获取所有组织者用于筛选下拉框
    organizers = UserProfile.objects.filter(role='organizer')
    
    # 分页
    paginator = Paginator(activities, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'volunteers/admin/activities.html', {
        'page_obj': page_obj,
        'status': status,
        'search': search,
        'organizer_id': organizer_id,
        'organizers': organizers,
        'status_choices': VolunteerActivity.STATUS_CHOICES,
        'total_count': activities.count(),
    })

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def admin_activity_detail(request, activity_id):
    """活动详情和编辑页面"""
    activity = get_object_or_404(VolunteerActivity, id=activity_id)
    
    # 获取报名列表
    applications = ActivityApplication.objects.filter(
        activity=activity
    ).select_related('volunteer__user')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_status':
            # 更新活动状态
            new_status = request.POST.get('status')
            if new_status in dict(VolunteerActivity.STATUS_CHOICES):
                old_status = activity.status
                activity.status = new_status
                
                # 如果设置为已发布且未批准，则自动批准
                if new_status == 'published' and not activity.is_approved:
                    activity.is_approved = True
                    activity.approved_by = request.user
                    activity.approved_at = timezone.now()
                
                activity.save()
                
                # 记录状态变更日志
                VerificationLog.objects.create(
                    profile=activity.organizer,
                    action='activity_status_change',
                    performed_by=request.user,
                    notes=f'活动状态从 {old_status} 更改为 {new_status}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"活动状态已更新为 {new_status}")
        
        elif action == 'approve_application':
            # 批准报名申请
            application_id = request.POST.get('application_id')
            try:
                application = ActivityApplication.objects.get(
                    id=application_id, 
                    activity=activity
                )
                application.status = 'approved'
                application.reviewed_by = request.user
                application.reviewed_at = timezone.now()
                application.save()
                
                messages.success(request, "报名申请已批准")
            except ActivityApplication.DoesNotExist:
                messages.error(request, "报名申请不存在")
        
        elif action == 'update_activity':
            # 更新活动信息
            form = ActivityForm(request.POST, instance=activity)
            if form.is_valid():
                form.save()
                messages.success(request, "活动信息已更新")
        return redirect('admin_activity_detail', activity_id=activity_id)
    
    # 获取活动表单用于编辑
    from .forms import ActivityForm
    form = ActivityForm(instance=activity)
    
    return render(request, 'volunteers/admin/activity_detail.html', {
        'activity': activity,
        'form': form,
        'applications': applications,
        'status_choices': VolunteerActivity.STATUS_CHOICES,
    })

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def batch_action_activities(request):
    """批量操作活动"""
    if request.method == 'POST':
        action = request.POST.get('action')
        activity_ids = request.POST.getlist('activity_ids')
        
        if not activity_ids:
            messages.error(request, "请选择要操作的活动")
            return redirect('admin_activities')
        
        activities = VolunteerActivity.objects.filter(id__in=activity_ids)
        count = 0
        
        if action == 'publish':
            # 批量发布活动
            for activity in activities:
                if activity.status != 'published':
                    activity.status = 'published'
                    activity.is_approved = True
                    activity.approved_by = request.user
                    activity.approved_at = timezone.now()
                    activity.save()
                    count += 1
            messages.success(request, f"已发布 {count} 个活动")
            
        elif action == 'cancel':
            # 批量取消活动
            for activity in activities:
                if activity.status != 'cancelled':
                    activity.status = 'cancelled'
                    activity.save()
                    count += 1
            messages.success(request, f"已取消 {count} 个活动")
            
        elif action == 'delete':
            # 批量删除活动
            count = activities.count()
            activities.delete()
            messages.success(request, f"已删除 {count} 个活动")
    
    return redirect('admin_activities')

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def activity_analytics(request):
    """活动数据分析"""
    # 时间范围设置
    time_range = request.GET.get('time_range', '30days')
    
    if time_range == '7days':
        days = 7
    elif time_range == '30days':
        days = 30
    elif time_range == '90days':
        days = 90
    else:
        days = 30
    
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # 活动创建趋势
    daily_activities = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        count = VolunteerActivity.objects.filter(
            created_at__date=date
        ).count()
        daily_activities.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    # 活动状态分布
    status_distribution = VolunteerActivity.objects.values('status').annotate(
        count=Count('id')
    )
    
    # 最受欢迎的活动类型
    popular_types = VolunteerActivity.objects.values('activity_type').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # 最活跃的组织者
    active_organizers = VolunteerActivity.objects.values(
        'organizer__user__username', 
        'organizer__real_name'
    ).annotate(
        activity_count=Count('id'),
        avg_participants=Avg('current_participants')
    ).order_by('-activity_count')[:10]
    
    # 参与度统计
    participation_stats = {
        'total_applications': ActivityApplication.objects.count(),
        'approved_applications': ActivityApplication.objects.filter(status='approved').count(),
        'avg_participants_per_activity': VolunteerActivity.objects.aggregate(
            avg=Avg('current_participants')
        )['avg'] or 0,
    }
    
    return render(request, 'volunteers/admin/activity_analytics.html', {
        'daily_activities': daily_activities,
        'status_distribution': status_distribution,
        'popular_types': popular_types,
        'active_organizers': active_organizers,
        'participation_stats': participation_stats,
        'time_range': time_range,
        'days': days,
        'start_date': start_date,
        'end_date': end_date,
    })

# ==================== 用户管理功能增强 ====================

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def update_user_status(request, user_id):
    """更新用户状态（启用/禁用）"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'toggle_active':
            user.is_active = not user.is_active
            user.save()
            
            status = "启用" if user.is_active else "禁用"
            messages.success(request, f"用户账户已{status}")
            
        elif action == 'change_role':
            new_role = request.POST.get('role')
            try:
                profile = user.profile
                old_role = profile.role
                profile.role = new_role
                profile.save()
                
                # 记录角色变更
                VerificationLog.objects.create(
                    profile=profile,
                    action='role_change',
                    performed_by=request.user,
                    notes=f"角色从 {old_role} 变更为 {new_role}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"用户角色已变更为 {new_role}")
            except UserProfile.DoesNotExist:
                messages.error(request, "用户资料不存在")
        
        return redirect('user_detail', user_id=user_id)
    
    return redirect('user_management')

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def export_users(request):
    """导出用户数据为CSV"""
    import csv
    from django.http import HttpResponse
    
    # 创建HTTP响应
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
    
    writer = csv.writer(response)
    
    # 写入标题行
    writer.writerow([
        '用户名', '邮箱', '真实姓名', '手机号', '角色', 
        '认证状态', '注册时间', '最后登录'
    ])
    
    # 获取用户数据
    users = User.objects.all().select_related('profile')
    
    for user in users:
        profile = getattr(user, 'profile', None)
        writer.writerow([
            user.username,
            user.email,
            profile.real_name if profile else '',
            profile.phone_number if profile else '',
            profile.role if profile else '',
            profile.verification_status if profile else '',
            user.date_joined.strftime('%Y-%m-%d %H:%M'),
            user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else ''
        ])
    
    return response

# ==================== 系统设置功能完善 ====================

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def system_settings(request):
    """系统设置页面"""
    # 获取所有系统设置
    settings = SystemSettingManager.get_all_settings()
    
    if request.method == 'POST':
        # 处理设置更新
        for key, value in request.POST.items():
            if key.startswith('setting_'):
                setting_key = key.replace('setting_', '')
                
                # 处理复选框值
                if value == 'on':
                    value = True
                elif value == '':
                    value = None
                
                # 更新设置
                SystemSettingManager.set_setting(setting_key, value)
        
        messages.success(request, "系统设置已更新")
        return redirect('system_settings')
    
    return render(request, 'volunteers/admin/system_settings.html', {
        'settings': settings,
        'categories': {
            'website': '网站设置',
            'registration': '注册设置',
            'verification': '认证设置',
            'activity': '活动设置',
            'security': '安全设置',
        }
    })

# ==================== 数据管理功能 ====================

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def data_management(request):
    """数据管理页面"""
    return render(request, 'volunteers/admin/data_management.html')

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def cleanup_data(request):
    """清理过期数据"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'cleanup_verification_codes':
            # 清理过期验证码
            expired_codes = EmailVerificationCode.objects.filter(
                created_at__lt=timezone.now() - timedelta(hours=24)
            )
            count = expired_codes.count()
            expired_codes.delete()
            messages.success(request, f"已清理 {count} 个过期验证码")
            
        elif action == 'cleanup_old_logs':
            # 清理旧日志
            old_logs = VerificationLog.objects.filter(
                performed_at__lt=timezone.now() - timedelta(days=90)
            )
            count = old_logs.count()
            old_logs.delete()
            messages.success(request, f"已清理 {count} 条旧日志")
            
        elif action == 'cleanup_old_activities':
            # 清理已结束的旧活动
            old_activities = VolunteerActivity.objects.filter(
                status='completed',
                end_date__lt=timezone.now() - timedelta(days=365)
            )
            count = old_activities.count()
            old_activities.delete()
            messages.success(request, f"已清理 {count} 个旧活动")
    
    return redirect('data_management')