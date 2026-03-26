# -*- coding: utf-8 -*-
# volunteers/admin_views.py
# ==================== 完整修正版（包含积分管理功能）====================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
import csv
from datetime import datetime, timedelta
from .models import (
    VolunteerActivity, ActivityApplication, Feedback, ActivityReviewLog,
    DataAccessLog, Announcement, Guide, EmailVerificationCode,
    UserProfile, VerificationLog, Notification, SystemSettingManager,
    UserPoints, PointsTransaction, StarLevelConfig, PointsOrder
)
from .forms import VolunteerVerificationForm, OrganizerVerificationForm
from .utils import (
    send_verification_status_email, send_application_status_email,
    add_points_transaction
)

# ==================== 辅助函数 ====================
def is_admin(user):
    if user.is_superuser or user.is_staff:
        return True
    try:
        return hasattr(user, 'profile') and user.profile.role == 'admin'
    except:
        return False

# ==================== 管理员登录/登出 ====================
def admin_login(request):
    if request.user.is_authenticated and is_admin(request.user):
        return redirect('admin_dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if is_admin(user):
                login(request, user)
                messages.success(request, "管理员登录成功")
                return redirect('admin_dashboard')
            else:
                messages.error(request, "您没有管理员权限")
        else:
            messages.error(request, "用户名或密码错误")
    return render(request, 'volunteers/admin/login.html')

def admin_logout(request):
    logout(request)
    messages.success(request, "已安全退出管理员系统")
    return redirect('admin_login')

# ==================== 管理员仪表盘 ====================
@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def admin_dashboard(request):
    pending_profiles = UserProfile.objects.filter(
        verification_status='pending'
    ).select_related('user').order_by('-submitted_at')
    approved_profiles = UserProfile.objects.filter(
        verification_status='approved'
    ).select_related('user')[:10]
    today = timezone.now().date()
    today_submissions = UserProfile.objects.filter(submitted_at__date=today).count()
    total_users = User.objects.count()
    pending_volunteers = pending_profiles.filter(role='volunteer').count()
    pending_organizers = pending_profiles.filter(role='organizer').count()
    week_start = today - timedelta(days=today.weekday())
    week_submissions = UserProfile.objects.filter(submitted_at__date__gte=week_start).count()
    role_distribution = UserProfile.objects.values('role').annotate(count=Count('id'))
    recent_logs = VerificationLog.objects.select_related('profile', 'performed_by').order_by('-performed_at')[:10]
    return render(request, 'volunteers/admin/dashboard.html', {
        'pending_profiles': pending_profiles,
        'approved_profiles': approved_profiles,
        'total_pending': pending_profiles.count(),
        'today_submissions': today_submissions,
        'total_users': total_users,
        'pending_volunteers': pending_volunteers,
        'pending_organizers': pending_organizers,
        'week_submissions': week_submissions,
        'role_distribution': role_distribution,
        'recent_logs': recent_logs,
    })

# ==================== 用户审核相关 ====================
@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def review_profile(request, profile_id):
    profile = get_object_or_404(UserProfile, id=profile_id)
    FormClass = VolunteerVerificationForm if profile.role == 'volunteer' else OrganizerVerificationForm
    if request.method == 'POST':
        action = request.POST.get('action')
        review_notes = request.POST.get('review_notes', '')
        if action in ['approve', 'reject', 'needs_review']:
            if action == 'approve':
                profile.verification_status = 'approved'
            elif action == 'reject':
                profile.verification_status = 'rejected'
            else:
                profile.verification_status = 'needs_review'
            profile.reviewed_by = request.user
            profile.reviewed_at = timezone.now()
            profile.review_notes = review_notes
            profile.save()
            VerificationLog.objects.create(
                profile=profile,
                action=action,
                performed_by=request.user,
                notes=review_notes,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            send_verification_status_email(profile)
            messages.success(request, f"已成功处理用户认证申请")
            return redirect('admin_dashboard')
    form = FormClass(instance=profile)
    return render(request, 'volunteers/admin/review_profile.html', {
        'profile': profile,
        'form': form,
    })

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def batch_approve(request):
    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_profiles')
        action = request.POST.get('batch_action')
        if selected_ids and action in ['approve', 'reject', 'needs_review']:
            profiles = UserProfile.objects.filter(id__in=selected_ids, verification_status='pending')
            count = 0
            for profile in profiles:
                if action == 'approve':
                    profile.verification_status = 'approved'
                elif action == 'reject':
                    profile.verification_status = 'rejected'
                else:
                    profile.verification_status = 'needs_review'
                profile.reviewed_by = request.user
                profile.reviewed_at = timezone.now()
                profile.review_notes = '批量审核操作'
                profile.save()
                VerificationLog.objects.create(
                    profile=profile,
                    action=action,
                    performed_by=request.user,
                    notes='批量审核操作',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                try:
                    send_verification_status_email(profile)
                except Exception as e:
                    print(f"发送邮件失败: {e}")
                count += 1
            action_msg = {
                'approve': '通过',
                'reject': '拒绝',
                'needs_review': '要求补充资料'
            }.get(action, '处理')
            messages.success(request, f"已批量{action_msg} {count} 个认证申请")
        else:
            messages.error(request, "请选择要操作的用户或操作类型无效")
    return redirect('admin_dashboard')

# ==================== 活动管理 ====================
@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def admin_activities(request):
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    organizer_filter = request.GET.get('organizer', '')
    activities = VolunteerActivity.objects.all().select_related('organizer__user')
    if search_query:
        activities = activities.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))
    if status_filter:
        activities = activities.filter(status=status_filter)
    if organizer_filter:
        activities = activities.filter(organizer__id=organizer_filter)
    paginator = Paginator(activities, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    organizers = UserProfile.objects.filter(role='organizer', verification_status='approved')
    return render(request, 'volunteers/admin/activities.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'organizer_filter': organizer_filter,
        'organizers': organizers,
        'total_count': activities.count(),
    })

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def admin_activity_detail(request, activity_id):
    activity = get_object_or_404(VolunteerActivity, id=activity_id)
    applications = ActivityApplication.objects.filter(activity=activity).select_related('volunteer__user')
    status_choices = VolunteerActivity._meta.get_field('status').choices
    activity_type_choices = VolunteerActivity._meta.get_field('activity_type').choices

    favorites_count = 0
    participation_rate = 0
    if activity.max_participants and activity.max_participants > 0:
        participation_rate = (activity.current_participants / activity.max_participants) * 100

    if request.method == 'POST':
        action = request.POST.get('action')
        if action in ['update_info', 'update_activity']:
            activity.title = request.POST.get('title', activity.title)
            activity.activity_type = request.POST.get('activity_type', activity.activity_type)
            activity.description = request.POST.get('description', activity.description)
            activity.start_time = request.POST.get('start_time') or activity.start_time
            activity.end_time = request.POST.get('end_time') or activity.end_time
            activity.location = request.POST.get('location', activity.location)
            activity.max_participants = request.POST.get('max_participants', activity.max_participants)
            activity.save()
            messages.success(request, "活动信息已更新")
            return redirect('admin_activity_detail', activity_id=activity.id)

        elif action in ['approve', 'reject', 'need_review']:
            review_notes = request.POST.get('review_notes', '')
            if action == 'approve':
                activity.is_approved = True
                activity.status = 'published'
                activity.approved_by = request.user
                activity.approved_at = timezone.now()
                # 给发布者增加发布积分
                if activity.organizer and activity.organizer.user:
                    add_points_transaction(
                        user=activity.organizer.user,
                        transaction_type='publish_activity',
                        amount=10,  # 假设发布活动积分为10
                        source_obj=activity,
                        operator=None,
                        remark='活动发布审核通过'
                    )
            elif action == 'reject':
                activity.is_approved = False
                activity.status = 'rejected'
            elif action == 'need_review':
                activity.is_approved = False
                activity.status = 'draft'
            activity.reviewed_by = request.user
            activity.reviewed_at = timezone.now()
            activity.review_notes = review_notes
            activity.save()
                
            # 活动审核通过，给发布者增加积分（放在保存之后）
            if action == 'approve':
                if activity.organizer and activity.organizer.user:
                    from .utils import add_points_transaction
                    add_points_transaction(
                        user=activity.organizer.user,
                        transaction_type='publish_activity',
                        amount=20,  # 固定积分
                        source_obj=activity,
                        operator=request.user,
                        remark=f'活动审核通过：{activity.title}'
                    )

            ActivityReviewLog.objects.create(
                activity=activity,
                action=action,
                performed_by=request.user,
                notes=review_notes,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, "活动审核状态已更新")
            return redirect('admin_activity_detail', activity_id=activity.id)

        elif action == 'update_status':
            new_status = request.POST.get('status')
            valid_statuses = dict(status_choices)
            if new_status in valid_statuses:
                activity.status = new_status
                if new_status == 'published' and not activity.is_approved:
                    activity.is_approved = True
                    activity.approved_by = request.user
                    activity.approved_at = timezone.now()
                activity.save()
                messages.success(request, f"活动状态已更新为 {activity.get_status_display()}")
            return redirect('admin_activity_detail', activity_id=activity.id)

        elif action == 'approve_application':
            app_id = request.POST.get('application_id')
            app = get_object_or_404(ActivityApplication, id=app_id)
            app.status = 'approved'
            app.reviewed_by = request.user
            app.reviewed_at = timezone.now()
            app.save()
            # 给志愿者增加报名积分
            if app.volunteer and app.volunteer.user:
                add_points_transaction(
                    user=app.volunteer.user,
                    transaction_type='signup_activity',
                    amount=5,  # 假设报名积分为5
                    source_obj=app.activity,
                    operator=None,
                    remark='活动报名审核通过'
                )
            send_application_status_email(app)
            messages.success(request, "报名已批准")
            return redirect('admin_activity_detail', activity_id=activity.id)

        elif action == 'reject_application':
            app_id = request.POST.get('application_id')
            app = get_object_or_404(ActivityApplication, id=app_id)
            app.status = 'rejected'
            app.reviewed_by = request.user
            app.reviewed_at = timezone.now()
            app.review_notes = request.POST.get('reject_reason', '管理员拒绝了您的报名申请')
            app.save()
            send_application_status_email(app)
            messages.success(request, "报名已拒绝")
            return redirect('admin_activity_detail', activity_id=activity.id)

    context = {
        'activity': activity,
        'applications': applications,
        'status_choices': status_choices,
        'activity_type_choices': activity_type_choices,
        'favorites_count': favorites_count,
        'participation_rate': participation_rate,
    }
    return render(request, 'volunteers/admin/activity_detail.html', context)

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def batch_action_activities(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_activities')
        if not selected_ids:
            messages.error(request, "请选择要操作的活动")
            return redirect('admin_activities')
        activities = VolunteerActivity.objects.filter(id__in=selected_ids)
        count = 0
        if action == 'publish':
            qs = activities.filter(status='draft')
            for activity in qs:
                activity.status = 'published'
                activity.is_approved = True
                activity.approved_by = request.user
                activity.approved_at = timezone.now()
                activity.save()
                # 给发布者增加发布积分（可选）
                if activity.organizer and activity.organizer.user:
                    add_points_transaction(
                        user=activity.organizer.user,
                        transaction_type='publish_activity',
                        amount=10,
                        source_obj=activity,
                        operator=None,
                        remark='活动批量发布'
                    )
                count += 1
            messages.success(request, f"已发布 {count} 个活动")
        elif action == 'cancel':
            qs = activities.filter(status__in=['published', 'ongoing'])
            for activity in qs:
                activity.status = 'cancelled'
                activity.save()
                count += 1
            messages.success(request, f"已取消 {count} 个活动")
        elif action == 'delete':
            count = activities.count()
            activities.delete()
            messages.success(request, f"已删除 {count} 个活动")
        return redirect('admin_activities')
    return redirect('admin_activities')

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def delete_activity(request, activity_id):
    activity = get_object_or_404(VolunteerActivity, id=activity_id)
    if request.method == 'POST':
        activity.delete()
        messages.success(request, "活动已删除")
        return redirect('admin_activities')
    return redirect('admin_activity_detail', activity_id=activity_id)

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def activity_analytics(request):
    total_activities = VolunteerActivity.objects.count()
    status_stats = VolunteerActivity.objects.values('status').annotate(count=Count('id'))
    type_stats = VolunteerActivity.objects.values('activity_type').annotate(count=Count('id'))
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    daily_activities = []
    for i in range(30):
        date = thirty_days_ago + timedelta(days=i)
        count = VolunteerActivity.objects.filter(created_at__date=date).count()
        daily_activities.append({'date': date, 'count': count})
    participation_stats = VolunteerActivity.objects.annotate(
        participation_rate=ExpressionWrapper(
            F('current_participants') * 1.0 / F('max_participants'),
            output_field=FloatField()
        )
    ).filter(max_participants__gt=0).order_by('-participation_rate')[:10]
    return render(request, 'volunteers/admin/activity_analytics.html', {
        'total_activities': total_activities,
        'status_stats': status_stats,
        'type_stats': type_stats,
        'daily_activities': daily_activities,
        'participation_stats': participation_stats,
    })

# ==================== 通知功能 ====================
@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def send_activity_notification(request, activity_id):
    if request.method == 'POST':
        activity = get_object_or_404(VolunteerActivity, id=activity_id)
        content = request.POST.get('content')
        notification_type = request.POST.get('type', 'other')
        if not content:
            messages.error(request, "通知内容不能为空")
            return redirect('admin_activity_detail', activity_id=activity.id)
        approved_apps = ActivityApplication.objects.filter(
            activity=activity, status='approved'
        ).select_related('volunteer__user')
        recipients = [app.volunteer.user for app in approved_apps]
        for user in recipients:
            Notification.objects.create(
                recipient=user,
                sender=request.user,
                activity=activity,
                notification_type=notification_type,
                content=content,
                is_read=False
            )
        messages.success(request, f"通知已发送给 {len(recipients)} 位参与者")
        return redirect('admin_activity_detail', activity_id=activity.id)
    return redirect('admin_activity_detail', activity_id=activity_id)

# ==================== 系统设置 ====================
@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def system_settings(request):
    from .models import SystemSettingManager
    setting_keys = [
        'site_name', 'site_description', 'contact_email', 'contact_phone',
        'site_address', 'icp_number', 'copyright', 'enable_registration',
        'require_email_verification', 'enable_feedback', 'auto_approve_volunteers',
        'auto_approve_organizers', 'auto_approve_activities'
    ]
    settings = {}
    for key in setting_keys:
        if key in ['enable_registration', 'require_email_verification', 
                   'enable_feedback', 'auto_approve_volunteers',
                   'auto_approve_organizers', 'auto_approve_activities']:
            settings[key] = SystemSettingManager.get_setting(key, True)
        else:
            settings[key] = SystemSettingManager.get_setting(key, '')
    if request.method == 'POST':
        for key in setting_keys:
            if key in request.POST:
                if key in ['enable_registration', 'require_email_verification', 
                           'enable_feedback', 'auto_approve_volunteers',
                           'auto_approve_organizers', 'auto_approve_activities']:
                    value = request.POST.get(key) == 'on'
                else:
                    value = request.POST.get(key)
                SystemSettingManager.set_setting(key, value)
        messages.success(request, "系统设置已保存")
        return redirect('system_settings')
    user_count = User.objects.count()
    activity_count = VolunteerActivity.objects.count()
    return render(request, 'volunteers/admin/system_settings.html', {
        'settings': settings,
        'user_count': user_count,
        'activity_count': activity_count,
    })

# ==================== 数据管理 ====================
@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def data_management(request):
    stats = {
        'total_users': User.objects.count(),
        'total_profiles': UserProfile.objects.count(),
        'total_activities': VolunteerActivity.objects.count(),
        'total_applications': ActivityApplication.objects.count(),
        'total_feedback': Feedback.objects.count(),
        'total_announcements': Announcement.objects.count(),
        'total_guides': Guide.objects.count(),
        'total_verification_logs': VerificationLog.objects.count(),
        'total_data_access_logs': DataAccessLog.objects.count(),
        'total_email_codes': EmailVerificationCode.objects.count(),
    }
    from django.db import connection
    db_size = '未知'
    try:
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                db_size = cursor.fetchone()[0]
        elif connection.vendor == 'sqlite':
            import os
            db_name = connection.settings_dict['NAME']
            if os.path.exists(db_name):
                size_bytes = os.path.getsize(db_name)
                db_size = f"{size_bytes / 1024 / 1024:.2f} MB"
        elif connection.vendor == 'mysql':
            with connection.cursor() as cursor:
                cursor.execute("SELECT SUM(data_length + index_length) FROM information_schema.tables WHERE table_schema = DATABASE()")
                size_bytes = cursor.fetchone()[0] or 0
                db_size = f"{size_bytes / 1024 / 1024:.2f} MB"
    except Exception as e:
        db_size = '无法获取'
    return render(request, 'volunteers/admin/data_management.html', {
        'stats': stats,
        'db_size': db_size,
    })

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def cleanup_data(request):
    if request.method == 'POST':
        cleanup_type = request.POST.get('cleanup_type')
        days = int(request.POST.get('days', 30))
        cutoff_date = timezone.now() - timedelta(days=days)
        count = 0
        if cleanup_type == 'verification_codes':
            expired_codes = EmailVerificationCode.objects.filter(expires_at__lt=timezone.now())
            count = expired_codes.count()
            expired_codes.delete()
        elif cleanup_type == 'old_logs':
            old_logs = VerificationLog.objects.filter(performed_at__lt=cutoff_date)
            count = old_logs.count()
            old_logs.delete()
        elif cleanup_type == 'completed_activities':
            completed_activities = VolunteerActivity.objects.filter(
                status='completed',
                end_time__lt=cutoff_date
            )
            count = completed_activities.count()
            completed_activities.delete()
        messages.success(request, f"已清理 {count} 条过期数据")
    return redirect('data_management')

# ==================== 全局数据统计 ====================
@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def admin_statistics(request):
    today = timezone.now().date()
    total_users = User.objects.count()
    active_users = User.objects.filter(last_login__date=today).count()
    new_today = User.objects.filter(date_joined__date=today).count()
    role_choices = dict(UserProfile._meta.get_field('role').choices)
    role_qs = UserProfile.objects.values('role').annotate(count=Count('id'))
    role_distribution = []
    for item in role_qs:
        role_distribution.append({
            'role': item['role'],
            'count': item['count'],
            'role_display': role_choices.get(item['role'], item['role']),
        })
    user_stats = {
        'total': total_users,
        'active': active_users,
        'new_today': new_today,
        'role_distribution': role_distribution,
    }
    total_activities = VolunteerActivity.objects.count()
    published = VolunteerActivity.objects.filter(status='published').count()
    draft = VolunteerActivity.objects.filter(status='draft').count()
    ongoing = VolunteerActivity.objects.filter(status='ongoing').count()
    completed = VolunteerActivity.objects.filter(status='completed').count()
    cancelled = VolunteerActivity.objects.filter(status='cancelled').count()
    rejected = VolunteerActivity.objects.filter(status='rejected').count()
    status_choices = dict(VolunteerActivity._meta.get_field('status').choices)
    status_qs = VolunteerActivity.objects.values('status').annotate(count=Count('id'))
    status_stats = []
    for item in status_qs:
        status_stats.append({
            'status': item['status'],
            'count': item['count'],
            'status_display': status_choices.get(item['status'], item['status']),
        })
    type_choices = dict(VolunteerActivity._meta.get_field('activity_type').choices)
    type_qs = VolunteerActivity.objects.values('activity_type').annotate(count=Count('id'))
    by_type = []
    for item in type_qs:
        by_type.append({
            'activity_type': item['activity_type'],
            'count': item['count'],
            'type_display': type_choices.get(item['activity_type'], item['activity_type']),
        })
    activity_stats = {
        'total': total_activities,
        'published': published,
        'draft': draft,
        'ongoing': ongoing,
        'completed': completed,
        'cancelled': cancelled,
        'rejected': rejected,
        'status_stats': status_stats,
        'by_type': by_type,
    }
    total_applications = ActivityApplication.objects.count()
    pending_app = ActivityApplication.objects.filter(status='pending').count()
    approved_app = ActivityApplication.objects.filter(status='approved').count()
    rejected_app = ActivityApplication.objects.filter(status='rejected').count()
    application_stats = {
        'total': total_applications,
        'pending': pending_app,
        'approved': approved_app,
        'rejected': rejected_app,
    }
    thirty_days_ago = today - timedelta(days=30)
    daily_signups = []
    daily_activities = []
    for i in range(30):
        date = thirty_days_ago + timedelta(days=i)
        signups = User.objects.filter(date_joined__date=date).count()
        activities = VolunteerActivity.objects.filter(created_at__date=date).count()
        daily_signups.append({'date': date, 'count': signups})
        daily_activities.append({'date': date, 'count': activities})
    context = {
        'user_stats': user_stats,
        'activity_stats': activity_stats,
        'application_stats': application_stats,
        'daily_signups': daily_signups,
        'daily_activities': daily_activities,
        'today': today,
    }
    return render(request, 'volunteers/admin/statistics.html', context)

# ==================== 用户管理 ====================
@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def user_management(request):
    search_query = request.GET.get('q', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    users = UserProfile.objects.all().select_related('user')
    if search_query:
        users = users.filter(
            Q(user__username__icontains=search_query) |
            Q(real_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
    if role_filter:
        users = users.filter(role=role_filter)
    if status_filter:
        users = users.filter(verification_status=status_filter)
    total_count = UserProfile.objects.count()
    verified_count = UserProfile.objects.filter(verification_status='approved').count()
    pending_count = UserProfile.objects.filter(verification_status='pending').count()
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'volunteers/admin/user_management.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'total_count': total_count,
        'verified_count': verified_count,
        'pending_count': pending_count,
    })

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def user_detail(request, user_id):
    user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(UserProfile, user=user)
    participated_activities = ActivityApplication.objects.filter(
        volunteer=profile
    ).select_related('activity')
    organized_activities = VolunteerActivity.objects.filter(
        organizer=profile
    )
    user_feedback = Feedback.objects.filter(user=user)
    access_logs = DataAccessLog.objects.filter(
        accessed_profile=profile
    ).order_by('-accessed_at')
    # 获取积分信息
    try:
        points = UserPoints.objects.get(user=user)
    except UserPoints.DoesNotExist:
        points = None
    return render(request, 'volunteers/admin/user_detail.html', {
        'user': user,
        'profile': profile,
        'participated_activities': participated_activities,
        'organized_activities': organized_activities,
        'user_feedback': user_feedback,
        'access_logs': access_logs,
        'points': points,
    })

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def update_user_status(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'activate':
            user.is_active = True
            user.save()
            messages.success(request, f"用户 {user.username} 已激活")
        elif action == 'deactivate':
            user.is_active = False
            user.save()
            messages.success(request, f"用户 {user.username} 已禁用")
    return redirect('user_detail', user_id=user_id)

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def export_users(request):
    import csv
    from django.http import HttpResponse
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    users = UserProfile.objects.all().select_related('user')
    if role_filter:
        users = users.filter(role=role_filter)
    if status_filter:
        users = users.filter(verification_status=status_filter)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['用户名', '邮箱', '真实姓名', '手机号', '角色', '认证状态', '注册时间', '最后登录'])
    for user_profile in users:
        user = user_profile.user
        writer.writerow([
            user.username,
            user.email,
            user_profile.real_name or '',
            user_profile.phone_number or '',
            user_profile.get_role_display(),
            user_profile.get_verification_status_display(),
            user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
            user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else ''
        ])
    return response

# ==================== 内容管理 ====================
@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def content_management(request):
    from .models import Announcement, Guide
    announcements = Announcement.objects.all().order_by('-created_at')
    guides = Guide.objects.all().order_by('order', '-created_at')
    if request.method == 'POST':
        if 'create_announcement' in request.POST:
            title = request.POST.get('title')
            content = request.POST.get('content')
            is_published = request.POST.get('is_published') == 'on'
            Announcement.objects.create(
                title=title,
                content=content,
                is_published=is_published,
             )
            messages.success(request, "公告已创建")
        elif 'publish_announcement' in request.POST:
            announcement_id = request.POST.get('announcement_id')
            try:
                announcement = Announcement.objects.get(id=announcement_id)
                announcement.is_published = True
                announcement.save()
                messages.success(request, "公告已发布")
            except Announcement.DoesNotExist:
                messages.error(request, "公告不存在")
        elif 'unpublish_announcement' in request.POST:
            announcement_id = request.POST.get('announcement_id')
            try:
                announcement = Announcement.objects.get(id=announcement_id)
                announcement.is_published = False
                announcement.save()
                messages.success(request, "公告已取消发布")
            except Announcement.DoesNotExist:
                messages.error(request, "公告不存在")
        elif 'delete_announcement' in request.POST:
            announcement_id = request.POST.get('announcement_id')
            try:
                announcement = Announcement.objects.get(id=announcement_id)
                announcement.delete()
                messages.success(request, "公告已删除")
            except Announcement.DoesNotExist:
                messages.error(request, "公告不存在")
        elif 'create_guide' in request.POST:
            title = request.POST.get('guide_title')
            content = request.POST.get('guide_content')
            category = request.POST.get('category')
            order = request.POST.get('order', 0)
            Guide.objects.create(
                title=title,
                content=content,
                category=category,
                order=order,
            )
            messages.success(request, "操作指南已创建")
    return render(request, 'volunteers/admin/content_management.html', {
        'announcements': announcements,
        'guides': guides,
    })

# ==================== 反馈管理 ====================
@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def feedback_management(request):
    from .models import Feedback
    feedback_list = Feedback.objects.all().select_related('user').order_by('-created_at')
    status_filter = request.GET.get('status', '')
    if status_filter:
        feedback_list = feedback_list.filter(status=status_filter)
    if request.method == 'POST':
        feedback_id = request.POST.get('feedback_id')
        action = request.POST.get('action')
        feedback = get_object_or_404(Feedback, id=feedback_id)
        if action == 'mark_reviewed':
            feedback.status = 'reviewed'
            feedback.save()
            messages.success(request, "反馈已标记为已查看")
        elif action == 'mark_resolved':
            feedback.status = 'resolved'
            feedback.resolved_at = timezone.now()
            feedback.response = request.POST.get('response', '')
            feedback.save()
            messages.success(request, "反馈已标记为已解决")
        elif action == 'delete':
            feedback.delete()
            messages.success(request, "反馈已删除")
    return render(request, 'volunteers/admin/feedback_management.html', {
        'feedback_list': feedback_list,
        'status_filter': status_filter,
    })

# ==================== 积分商城管理 ====================
from .models import PointsShopItem

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def shop_item_list(request):
    """积分商品列表"""
    items = PointsShopItem.objects.all().order_by('-is_active', '-created_at')
    return render(request, 'volunteers/admin/shop_item_list.html', {
        'items': items,
    })

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def shop_item_create(request):
    """创建商品"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        points_required = request.POST.get('points_required')
        stock = request.POST.get('stock', 0)
        is_active = request.POST.get('is_active') == 'on'
        # 图片处理（可选）
        image = request.FILES.get('image')
        
        if not all([name, description, points_required]):
            messages.error(request, "请填写必填项")
        else:
            item = PointsShopItem(
                name=name,
                description=description,
                points_required=points_required,
                stock=stock,
                is_active=is_active,
                image=image,
            )
            item.save()
            messages.success(request, f"商品 {name} 创建成功")
            return redirect('shop_item_list')
    
    return render(request, 'volunteers/admin/shop_item_form.html', {
        'action': '创建',
    })

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def shop_item_edit(request, item_id):
    """编辑商品"""
    item = get_object_or_404(PointsShopItem, id=item_id)
    if request.method == 'POST':
        item.name = request.POST.get('name')
        item.description = request.POST.get('description')
        item.points_required = request.POST.get('points_required')
        item.stock = request.POST.get('stock', 0)
        item.is_active = request.POST.get('is_active') == 'on'
        if request.FILES.get('image'):
            item.image = request.FILES.get('image')
        item.save()
        messages.success(request, f"商品 {item.name} 更新成功")
        return redirect('shop_item_list')
    
    return render(request, 'volunteers/admin/shop_item_form.html', {
        'item': item,
        'action': '编辑',
    })

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def shop_item_delete(request, item_id):
    """删除商品"""
    item = get_object_or_404(PointsShopItem, id=item_id)
    if request.method == 'POST':
        item.delete()
        messages.success(request, f"商品 {item.name} 已删除")
    return redirect('shop_item_list')

@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def admin_shop_orders(request):
    """管理员订单管理"""
    orders = PointsOrder.objects.all().select_related('user', 'item').order_by('-created_at')
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        action = request.POST.get('action')
        order = get_object_or_404(PointsOrder, id=order_id)
        if action == 'complete':
            order.status = 'completed'
            order.processed_at = timezone.now()
            order.processed_by = request.user
            order.save()
            messages.success(request, f"订单 {order.id} 已完成")
        elif action == 'cancel':
            from .utils import add_points_transaction
            order.status = 'cancelled'
            order.processed_at = timezone.now()
            order.processed_by = request.user
            order.save()
            # 返还积分
            add_points_transaction(
                user=order.user,
                transaction_type='reward',
                amount=order.points_spent,
                source_obj=order.item,
                operator=request.user,
                remark=f'订单取消返还积分：{order.item.name}'
            )
            messages.success(request, f"订单 {order.id} 已取消，积分已返还")
        return redirect('admin_shop_orders')
    return render(request, 'volunteers/admin/shop_orders.html', {'orders': orders})

# ==================== 积分管理 ====================
@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def points_management(request):
    """积分管理首页"""
    # 统计信息
    total_users = User.objects.count()
    users_with_points = UserPoints.objects.count()
    total_points_earned = UserPoints.objects.aggregate(total=Sum('total_earned'))['total'] or 0
    total_points_balance = UserPoints.objects.aggregate(total=Sum('balance'))['total'] or 0
    recent_transactions = PointsTransaction.objects.select_related('user', 'operator').order_by('-created_at')[:20]
    
    context = {
        'total_users': total_users,
        'users_with_points': users_with_points,
        'total_points_earned': total_points_earned,
        'total_points_balance': total_points_balance,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'volunteers/admin/points_management.html', context)


@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def adjust_points(request):
    """手动调整用户积分（奖励/惩罚）"""
    if request.method == 'POST':
        username = request.POST.get('username')
        amount = request.POST.get('amount')
        remark = request.POST.get('remark', '')
        try:
            user = User.objects.get(username=username)
            amount = int(amount)
            if amount == 0:
                messages.error(request, "积分变动不能为0")
            else:
                transaction_type = 'reward' if amount > 0 else 'penalty'
                success = add_points_transaction(
                    user=user,
                    transaction_type=transaction_type,
                    amount=amount,
                    operator=request.user,
                    remark=remark
                )
                if success:
                    messages.success(request, f"已为 {user.username} 调整积分 {amount}")
                else:
                    messages.error(request, "积分调整失败")
        except User.DoesNotExist:
            messages.error(request, "用户不存在")
        except ValueError:
            messages.error(request, "积分数量必须为整数")
        return redirect('points_management')
    
    # GET 请求显示表单
    return render(request, 'volunteers/admin/adjust_points.html')


@login_required(login_url='/admin/login/')
@user_passes_test(is_admin, login_url='/admin/login/')
def star_level_config(request):
    """星级配置管理"""
    configs = StarLevelConfig.objects.all().order_by('role', 'min_points')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            role = request.POST.get('role')
            min_points = request.POST.get('min_points')
            level_name = request.POST.get('level_name')
            description = request.POST.get('description', '')
            order = request.POST.get('order', 0)
            StarLevelConfig.objects.create(
                role=role,
                min_points=min_points,
                level_name=level_name,
                description=description,
                order=order,
                is_active=True
            )
            messages.success(request, "星级配置已添加")
        elif action == 'update':
            config_id = request.POST.get('config_id')
            config = get_object_or_404(StarLevelConfig, id=config_id)
            config.min_points = request.POST.get('min_points')
            config.level_name = request.POST.get('level_name')
            config.description = request.POST.get('description', '')
            config.order = request.POST.get('order', 0)
            config.is_active = request.POST.get('is_active') == 'on'
            config.save()
            messages.success(request, "星级配置已更新")
        elif action == 'delete':
            config_id = request.POST.get('config_id')
            config = get_object_or_404(StarLevelConfig, id=config_id)
            config.delete()
            messages.success(request, "星级配置已删除")
        return redirect('star_level_config')
    
    return render(request, 'volunteers/admin/star_level_config.html', {'configs': configs})
