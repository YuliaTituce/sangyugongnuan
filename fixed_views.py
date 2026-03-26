# views.py 顶部，确保导入了所有需要的模型
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import json
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q

# 导入所有需要的模型
from .models import (
    UserProfile, VerificationLog, EmailVerificationCode, DataAccessLog,
    Announcement, Guide, Feedback, VolunteerActivity, ActivityApplication,
    SystemSetting, SystemSettingManager
)

# 导入表单
from .forms import (
    ActivityForm, ActivityApplicationForm, FeedbackForm,
    VolunteerVerificationForm, OrganizerVerificationForm
)

# 导入工具函数
from .utils import send_verification_email, verify_email_code

# 首页视图
def index(request):
    """首页重定向到门户页面"""
    return redirect('portal')

def portal_view(request):
    """门户导航页面 - 无需登录即可访问"""
    from .models import SystemSettingManager

    show_activities_count = SystemSettingManager.get_setting('show_latest_activities_count', 5)
    latest_activities = VolunteerActivity.objects.filter(
        status='published',
        is_approved=True
    ).order_by('-published_at')[:show_activities_count]

    show_announcements_count = SystemSettingManager.get_setting('show_latest_announcements_count', 3)
    latest_announcements = Announcement.objects.filter(
        is_published=True
    ).order_by('-created_at')[:show_announcements_count]

    guides = Guide.objects.filter(
        is_published=True
    ).order_by('order', '-created_at')[:5]

    context = {
        'latest_activities': latest_activities,
        'latest_announcements': latest_announcements,
        'guides': guides,
        'site_name': SystemSettingManager.get_setting('site_name', '桑榆共暖'),
        'site_description': SystemSettingManager.get_setting('site_description', '志愿服务平台'),
        'contact_email': SystemSettingManager.get_setting('contact_email', '2994192894@qq.com'),
        'contact_phone': SystemSettingManager.get_setting('contact_phone', ''),
        'site_address': SystemSettingManager.get_setting('site_address', '北京市海淀区'),
    }
    return render(request, 'volunteers/portal.html', context)

class RegisterView(View):
    """注册视图 - 使用系统设置控制功能"""
    def get(self, request):
        if not SystemSettingManager.get_setting('enable_registration', True):
            messages.error(request, "当前暂不接受新用户注册")
            return redirect('index')
        return render(request, 'volunteers/register.html')

    def post(self, request):
        if not SystemSettingManager.get_setting('enable_registration', True):
            messages.error(request, "当前暂不接受新用户注册")
            return redirect('index')

        require_verification = SystemSettingManager.get_setting('enable_email_verification', True)

        email = request.POST.get('email')
        code = request.POST.get('verification_code')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        min_password_length = SystemSettingManager.get_setting('password_min_length', 8)
        if len(password) < min_password_length:
            messages.error(request, f"密码长度至少需要 {min_password_length} 位")
            return render(request, 'volunteers/register.html')

        if SystemSettingManager.get_setting('require_password_complexity', False):
            import re
            if not (re.search(r'[A-Z]', password) and
                    re.search(r'[a-z]', password) and
                    re.search(r'\d', password) and
                    re.search(r'[!@#$%^&*(),.?":{}|<>]', password)):
                messages.error(request, "密码必须包含大小写字母、数字和特殊字符")
                return render(request, 'volunteers/register.html')

        if require_verification:
            success, message = verify_email_code(email, code, 'register')
            if not success:
                messages.error(request, message)
                return render(request, 'volunteers/register.html')

        try:
            username = email.split('@')[0] + str(User.objects.count())
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_active=True
            )

            login(request, user)
            messages.success(request, "注册成功！请选择您的身份类型进行认证。")
            return redirect('role_selection')
        except Exception as e:
            messages.error(request, f"注册失败：{str(e)}")
            return render(request, 'volunteers/register.html')

class SendVerificationCodeView(View):
    """发送验证码视图"""
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        try:
            try:
                data = json.loads(request.body)
                email = data.get('email')
                purpose = data.get('purpose', 'register')
            except:
                email = request.POST.get('email')
                purpose = request.POST.get('purpose', 'register')

            if not email:
                return JsonResponse({'success': False, 'message': '请输入邮箱地址'})

            success, message = send_verification_email(email, purpose)
            return JsonResponse({'success': success, 'message': message})
        except Exception as e:
            return JsonResponse({'success': False, 'message': '服务器内部错误'}, status=500)

class LoginWithCodeView(View):
    """使用验证码登录"""
    def get(self, request):
        return render(request, 'volunteers/login_with_code.html')

    def post(self, request):
        email = request.POST.get('email')
        code = request.POST.get('verification_code')

        success, message = verify_email_code(email, code, 'login')
        if not success:
            messages.error(request, message)
            return render(request, 'volunteers/login_with_code.html')

        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                messages.error(request, "账户已被禁用")
                return render(request, 'volunteers/login_with_code.html')

            login(request, user)

            if hasattr(user, 'profile'):
                if user.profile.verification_status == 'approved':
                    messages.success(request, "登录成功！")
                    return redirect('dashboard')
                else:
                    messages.info(request, "登录成功！请完成身份认证。")
                    return redirect('role_selection')
            else:
                messages.info(request, "登录成功！请完善个人信息。")
                return redirect('role_selection')
        except User.DoesNotExist:
            messages.error(request, "该邮箱尚未注册")
            return render(request, 'volunteers/login_with_code.html')

@method_decorator(login_required, name='dispatch')
class RoleSelectionView(View):
    """角色选择视图"""
    def get(self, request):
        if hasattr(request.user, 'profile') and request.user.profile.verification_status == 'approved':
            messages.info(request, "您已经通过认证")
            return redirect('dashboard')
        return render(request, 'volunteers/role_selection.html')

    def post(self, request):
        role = request.POST.get('role')
        if not role:
            messages.error(request, "请选择一个身份类型")
            return redirect('role_selection')

        request.session['selected_role'] = role
        if role == 'skip':
            return redirect('dashboard')
        return redirect('profile_verification')

@login_required
def profile_verification(request):
    """身份认证表单视图 - 使用自动审核设置"""
    selected_role = request.session.get('selected_role')
    if not selected_role or selected_role == 'skip':
        messages.info(request, "请先选择身份类型")
        return redirect('role_selection')

    try:
        profile = UserProfile.objects.get(user=request.user)
        profile.role = selected_role
        profile.save()
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(
            user=request.user,
            role=selected_role,
            verification_status='pending'
        )

    if profile.verification_status == 'approved':
        messages.info(request, "您已经通过认证")
        return redirect('dashboard')

    if selected_role == 'volunteer':
        form_class = VolunteerVerificationForm
        template = 'volunteers/volunteer_verification.html'
    else:
        form_class = OrganizerVerificationForm
        template = 'volunteers/organizer_verification.html'

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.role = selected_role

            if selected_role == 'volunteer':
                auto_approve = SystemSettingManager.get_setting('auto_approve_volunteers', False)
            else:
                auto_approve = SystemSettingManager.get_setting('auto_approve_organizers', False)

            if auto_approve:
                profile.verification_status = 'approved'
                profile.reviewed_at = timezone.now()
                profile.review_notes = '自动审核通过'
                messages.success(request, "认证已自动通过！")
            else:
                profile.verification_status = 'pending'
                messages.success(request, "认证申请已提交，管理员将在1-3个工作日内审核")

            profile.submitted_at = timezone.now()
            profile.data_consent = form.cleaned_data.get('agree_terms', False)
            profile.save()

            VerificationLog.objects.create(
                profile=profile,
                action='submit',
                performed_by=request.user,
                notes='用户提交认证申请',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return redirect('verification_status')
    else:
        initial = {}
        if profile.data_consent:
            initial['agree_terms'] = True
        form = form_class(instance=profile, initial=initial)

    return render(request, template, {
        'form': form,
        'role': selected_role,
        'profile': profile
    })

@login_required
def verification_status(request):
    """查看认证状态"""
    try:
        profile = UserProfile.objects.get(user=request.user)
        logs = VerificationLog.objects.filter(profile=profile).order_by('-performed_at')
        return render(request, 'volunteers/verification_status.html', {
            'profile': profile,
            'logs': logs
        })
    except UserProfile.DoesNotExist:
        messages.info(request, "请先完成身份认证")
        return redirect('role_selection')

def activity_list(request):
    """活动列表视图 - 使用系统设置控制分页"""
    per_page = SystemSettingManager.get_setting('activities_per_page', 10)
    all_activities = VolunteerActivity.objects.filter(
        status='published',
        is_approved=True
    ).order_by('-published_at')

    paginator = Paginator(all_activities, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    activities = page_obj.object_list

    user_can_apply = False
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        user_profile = request.user.profile
        user_can_apply = (
            user_profile.verification_status == 'approved' and
            user_profile.role == 'volunteer'
        )

    return render(request, 'volunteers/activity_list.html', {
        'activities': activities,
        'page_obj': page_obj,
        'user_can_apply': user_can_apply,
        'per_page': per_page,
    })

def activity_detail(request, activity_id):
    """活动详情"""
    activity = get_object_or_404(VolunteerActivity, id=activity_id)

    can_apply = False
    already_applied = False
    application = None

    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        user_profile = request.user.profile
        can_apply = (
            activity.can_apply() and
            user_profile.verification_status == 'approved' and
            user_profile.role == 'volunteer'
        )
        if can_apply:
            already_applied = ActivityApplication.objects.filter(
                activity=activity,
                volunteer=user_profile
            ).exists()
            if already_applied:
                application = ActivityApplication.objects.get(
                    activity=activity,
                    volunteer=user_profile
                )

    return render(request, 'volunteers/activity_detail.html', {
        'activity': activity,
        'can_apply': can_apply,
        'already_applied': already_applied,
        'application': application,
    })

@login_required
def create_activity(request):
    """发布活动 - 使用系统设置检查限制"""
    if not SystemSettingManager.get_setting('enable_activity_creation', True):
        messages.error(request, "当前不允许创建新活动")
        return redirect('dashboard')

    if not hasattr(request.user, 'profile') or not request.user.profile.can_publish():
        messages.error(request, "您没有权限发布活动")
        return redirect('dashboard')

    max_activities = SystemSettingManager.get_setting('max_activities_per_organizer', 10)
    current_activities = VolunteerActivity.objects.filter(
        organizer=request.user.profile,
        status__in=['draft', 'published', 'ongoing']
    ).count()

    if current_activities >= max_activities:
        messages.error(request, f"您已达到最大活动数限制（{max_activities}个），无法创建新活动")
        return redirect('dashboard')

    default_max_participants = SystemSettingManager.get_setting('max_participants_per_activity', 50)

    if request.method == 'POST':
        form = ActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.organizer = request.user.profile
            activity.status = 'draft'

            if SystemSettingManager.get_setting('auto_approve_activities', False):
                activity.status = 'published'
                activity.is_approved = True
                activity.approved_by = request.user
                activity.approved_at = timezone.now()
                messages.success(request, "活动已自动审核通过并发布")
            else:
                activity.status = 'draft'
                messages.success(request, "活动已创建，等待管理员审核")

            activity.save()
            return redirect('activity_detail', activity_id=activity.id)
    else:
        initial_data = {'max_participants': default_max_participants}
        form = ActivityForm(initial=initial_data)

    return render(request, 'volunteers/create_activity.html', {
        'form': form,
        'max_activities': max_activities,
        'current_activities': current_activities,
    })

@login_required
def apply_activity(request, activity_id):
    """报名活动"""
    activity = get_object_or_404(VolunteerActivity, id=activity_id)

    if not hasattr(request.user, 'profile') or not request.user.profile.can_participate():
        messages.error(request, "您需要先通过志愿者认证才能报名活动")
        return redirect('activity_detail', activity_id=activity_id)

    if not activity.can_apply():
        messages.error(request, "该活动当前不能报名")
        return redirect('activity_detail', activity_id=activity_id)

    if ActivityApplication.objects.filter(activity=activity, volunteer=request.user.profile).exists():
        messages.warning(request, "您已经报名了该活动")
        return redirect('activity_detail', activity_id=activity_id)

    if activity.is_full():
        messages.error(request, "该活动报名人数已满")
        return redirect('activity_detail', activity_id=activity_id)

    if request.method == 'POST':
        form = ActivityApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.activity = activity
            application.volunteer = request.user.profile
            application.status = 'pending'
            application.save()

            activity.current_participants += 1
            activity.save()

            messages.success(request, "报名成功！请等待组织者审核")
            return redirect('activity_detail', activity_id=activity_id)
    else:
        form = ActivityApplicationForm()

    return render(request, 'volunteers/apply_activity.html', {
        'form': form,
        'activity': activity,
    })

def dashboard(request):
    """用户仪表盘"""
    if hasattr(request.user, 'profile'):
        profile = request.user.profile
        context = {
            'profile': profile,
            'is_authenticated': profile.verification_status == 'approved'
        }
    else:
        context = {'is_authenticated': False}
    return render(request, 'volunteers/dashboard.html', context)

def login_view(request):
    """传统的用户名密码登录"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "用户名或密码错误")
    return render(request, 'volunteers/login.html')

def logout_view(request):
    """退出登录"""
    logout(request)
    return redirect('home')

def search_view(request):
    """搜索功能"""
    query = request.GET.get('q', '').strip()
    results = {
        'activities': [],
        'announcements': [],
        'guides': [],
    }
    if query:
        results['activities'] = VolunteerActivity.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query),
            status='published',
            is_approved=True
        )[:10]
        results['announcements'] = Announcement.objects.filter(
            Q(title__icontains=query) | Q(content__icontains=query),
            is_published=True
        )[:10]
        results['guides'] = Guide.objects.filter(
            Q(title__icontains=query) | Q(content__icontains=query),
            is_published=True
        )[:10]
    return render(request, 'volunteers/search_results.html', {
        'query': query,
        'results': results,
    })

def feedback_view(request):
    """反馈和意见页面"""
    if request.method == 'POST' and request.user.is_authenticated:
        feedback_form = FeedbackForm(request.POST)
        if feedback_form.is_valid():
            content = feedback_form.cleaned_data['content']
            contact = feedback_form.cleaned_data['contact']
            try:
                from .models import Feedback
                Feedback.objects.create(
                    user=request.user,
                    content=content,
                    contact=contact,
                    status='pending'
                )
                messages.success(request, "感谢您的反馈！")
                return redirect('portal')
            except Exception as e:
                messages.error(request, f"提交反馈失败：{str(e)}")
    else:
        feedback_form = FeedbackForm()
    return render(request, 'volunteers/feedback.html', {
        'form': feedback_form,
        'can_submit': request.user.is_authenticated
    })

@login_required
def organizer_activities(request):
    """组织者活动管理页面"""
    if not hasattr(request.user, 'profile') or not request.user.profile.can_publish():
        messages.error(request, "您没有权限访问此页面")
        return redirect('dashboard')

    profile = request.user.profile
    activities = VolunteerActivity.objects.filter(
        organizer=profile
    ).order_by('-created_at')

    paginator = Paginator(activities, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'profile': profile,
    }
    return render(request, 'volunteers/organizer_activities.html', context)
