from django import forms
from .models import UserProfile, VolunteerActivity, ActivityApplication
from django.core.validators import RegexValidator
from django.utils import timezone
from django import forms
from .models import VolunteerActivity, ActivityApplication, EmailVerificationCode

class VolunteerVerificationForm(forms.ModelForm):
    """志愿者认证表单"""
    # 添加 agree_terms 字段，因为模板中使用的是这个名称
    agree_terms = forms.BooleanField(
        required=True,
        label='我同意平台根据《隐私政策》收集和使用我的个人信息',
        error_messages={'required': '请同意个人信息保护政策'}
    )
    
    class Meta:
        model = UserProfile
        fields = [
            'real_name', 'phone_number', 'id_card_number', 'current_address',
            'emergency_contact', 'emergency_phone',
            'volunteer_experience', 'skills', 'available_time',
            'identity_document'
        ]
        widgets = {
            'real_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入真实姓名'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入手机号码'}),
            'id_card_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入18位身份证号码'}),
            'current_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '请输入现居住地址'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入紧急联系人姓名'}),
            'emergency_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入紧急联系人电话'}),
            'volunteer_experience': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '如无请填写"无"'}),
            'skills': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '请描述您的专业技能'}),
            'available_time': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '如"周末"、"工作日晚上"等'}),
            'identity_document': forms.FileInput(attrs={'class': 'form-control-file'}),
        }
        labels = {
            'real_name': '真实姓名',
            'phone_number': '手机号码',
            'id_card_number': '身份证号码',
            'current_address': '现居住地址',
            'emergency_contact': '紧急联系人姓名',
            'emergency_phone': '紧急联系人电话',
            'volunteer_experience': '志愿服务经历',
            'skills': '专业技能',
            'available_time': '可服务时间',
            'identity_document': '身份证明文件（身份证正反面照片）',
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 设置必填字段的标记
        for field in self.fields:
            if field != 'agree_terms' and field != 'volunteer_experience' and field != 'skills' and field != 'available_time':
                self.fields[field].required = True
                self.fields[field].label_suffix = ' *'

class OrganizerVerificationForm(forms.ModelForm):
    """活动发布者认证表单"""
    # 添加 agree_terms 字段
    agree_terms = forms.BooleanField(
        required=True,
        label='我同意平台根据《隐私政策》收集和使用我的个人信息',
        error_messages={'required': '请同意个人信息保护政策'}
    )
    
    class Meta:
        model = UserProfile
        fields = [
            'real_name', 'phone_number', 'id_card_number', 'current_address',
            'emergency_contact', 'emergency_phone',
            'organization_name', 'organization_type', 'organization_description',
            'organization_certificate', 'identity_document'
        ]
        widgets = {
            'real_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入负责人真实姓名'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入负责人手机号码'}),
            'id_card_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入负责人身份证号码'}),
            'current_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '请输入组织办公地址'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入备用联系人姓名'}),
            'emergency_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入备用联系人电话'}),
            'organization_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入组织/机构全称'}),
            'organization_type': forms.Select(attrs={'class': 'form-control'}),
            'organization_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '请详细描述您的组织/机构'}),
            'organization_certificate': forms.FileInput(attrs={'class': 'form-control-file'}),
            'identity_document': forms.FileInput(attrs={'class': 'form-control-file'}),
        }
        labels = {
            'real_name': '负责人真实姓名',
            'phone_number': '负责人手机号码',
            'id_card_number': '负责人身份证号码',
            'current_address': '组织办公地址',
            'emergency_contact': '备用联系人姓名',
            'emergency_phone': '备用联系人电话',
            'organization_name': '组织/机构名称',
            'organization_type': '组织类型',
            'organization_description': '组织描述',
            'organization_certificate': '组织机构证明文件',
            'identity_document': '负责人身份证明文件',
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 设置必填字段的标记
        for field in self.fields:
            if field != 'agree_terms' and field != 'emergency_contact' and field != 'emergency_phone':
                self.fields[field].required = True
                self.fields[field].label_suffix = ' *'

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from .forms import VolunteerVerificationForm, OrganizerVerificationForm
from .models import UserProfile, VerificationLog

@method_decorator(login_required, name='dispatch')
class ProfileVerificationView(View):
    """用户身份认证视图"""
    
    def get(self, request):
        # 检查用户是否已经认证
        if hasattr(request.user, 'profile'):
            profile = request.user.profile
            
            if profile.verification_status == 'approved':
                messages.info(request, "您已经通过认证")
                return redirect('dashboard')
            
            # 根据用户选择显示不同表单
            role = request.GET.get('role', profile.role)
            
            if role == 'volunteer':
                form = VolunteerVerificationForm(instance=profile)
            elif role == 'organizer':
                form = OrganizerVerificationForm(instance=profile)
            else:
                # 首次选择角色
                return render(request, 'volunteers/select_role.html')
            
            return render(request, 'volunteers/profile_verification.html', {
                'form': form,
                'role': role
            })
        
        return redirect('select_role')
    
    def post(self, request):
        role = request.POST.get('role')
        
        if hasattr(request.user, 'profile'):
            profile = request.user.profile
            
            if role == 'volunteer':
                form = VolunteerVerificationForm(request.POST, request.FILES, instance=profile)
            elif role == 'organizer':
                form = OrganizerVerificationForm(request.POST, request.FILES, instance=profile)
            else:
                messages.error(request, "请选择认证类型")
                return redirect('profile_verification')
            
            if form.is_valid():
                # 更新用户角色和状态
                profile = form.save(commit=False)
                profile.role = role
                profile.verification_status = 'pending'
                profile.save()
                
                # 记录审核日志
                VerificationLog.objects.create(
                    profile=profile,
                    action='submit',
                    performed_by=request.user,
                    notes='用户提交认证申请',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                # 发送通知邮件给管理员（可选）
                self.notify_admins(profile)
                
                messages.success(request, "认证申请已提交，管理员将在1-3个工作日内审核")
                return redirect('verification_status')
            else:
                messages.error(request, "请检查表单错误")
        else:
            messages.error(request, "请先完善个人信息")
        
        return render(request, 'volunteers/profile_verification.html', {
            'form': form,
            'role': role
        })
    
    def notify_admins(self, profile):
        """通知管理员有新的认证申请"""
        # 这里可以发送邮件或站内信给管理员
        pass

@login_required
def verification_status(request):
    """查看认证状态"""
    if hasattr(request.user, 'profile'):
        profile = request.user.profile
        logs = VerificationLog.objects.filter(profile=profile).order_by('-performed_at')
        
        return render(request, 'volunteers/verification_status.html', {
            'profile': profile,
            'logs': logs
        })
    return redirect('profile_verification')

class ActivityForm(forms.ModelForm):
    """活动发布表单"""

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_start_time(self):
        from django.utils import timezone
        from django.core.exceptions import ValidationError
        start_time = self.cleaned_data.get('start_time')
        if self.user and (self.user.is_superuser or self.user.is_staff):
            return start_time
        if start_time and start_time < timezone.now():
            raise ValidationError('开始时间不能早于当前时间')
        return start_time

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if start_time and end_time:
            if start_time >= end_time:
                raise forms.ValidationError("结束时间必须晚于开始时间")

            # 如果是管理员，跳过过去时间验证（但已在 clean_start_time 中处理，这里可保留或移除）
            # 为了保险，仍然保留条件，避免重复验证
            if not (self.user and (self.user.is_superuser or self.user.is_staff)):
                if start_time < timezone.now():
                    raise forms.ValidationError("开始时间不能是过去的时间")

        return cleaned_data

    class Meta:
        model = VolunteerActivity
        fields = [
            'title', 'description', 'activity_type',
            'start_time', 'end_time',
            'location', 'address_detail',
            'max_participants'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入活动标题'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': '请输入活动详细描述'}),
            'activity_type': forms.Select(attrs={'class': 'form-control'}),
            'start_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入活动地点'}),
            'address_detail': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '请输入详细地址'}),
            'max_participants': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
        labels = {
            'title': '活动标题',
            'description': '活动描述',
            'activity_type': '活动类型',
            'start_time': '开始时间',
            'end_time': '结束时间',
            'location': '活动地点',
            'address_detail': '详细地址',
            'max_participants': '最大参与人数',
        }

class ActivityApplicationForm(forms.ModelForm):
    """活动报名表单"""
    class Meta:
        model = ActivityApplication
        fields = ['application_notes', 'experience_expectation']
        widgets = {
            'application_notes': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': '请说明您为什么想参加这个活动'
            }),
            'experience_expectation': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': '您希望通过这次活动获得什么经验或收获？'
            }),
        }
        labels = {
            'application_notes': '报名备注',
            'experience_expectation': '经验期望',
        }

class FeedbackForm(forms.Form):
    content = forms.CharField(
        label='反馈内容',
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': '请描述您遇到的问题或提出宝贵建议...',
            'class': 'form-control'
        })
    )
    contact = forms.CharField(
        label='联系方式',
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '邮箱/电话（可选，方便我们联系您）',
            'class': 'form-control'
        })
    )
