from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
from django.conf import settings
import uuid

# 邮箱验证码表
class EmailVerificationCode(models.Model):
    email = models.EmailField(verbose_name="邮箱地址")
    code = models.CharField(max_length=6, verbose_name="验证码")
    purpose = models.CharField(max_length=20, choices=[
        ('register', '注册'),
        ('login', '登录'),
        ('reset', '重置密码')
    ], verbose_name="用途")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    expires_at = models.DateTimeField(verbose_name="过期时间")
    is_used = models.BooleanField(default=False, verbose_name="是否已使用")
    
    class Meta:
        indexes = [
            models.Index(fields=['email', 'purpose']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.email} - {self.code}"

# 用户详细资料模型（存储敏感信息）
class UserProfile(models.Model):
    USER_ROLES = [
        ('unverified', '未认证'),
        ('volunteer', '志愿者'),
        ('organizer', '活动发布者'),
        ('admin', '管理员'),
    ]
    
    VERIFICATION_STATUS = [
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('needs_review', '需要补充资料'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="用户")
    role = models.CharField(max_length=20, choices=USER_ROLES, default='unverified', verbose_name="用户角色")
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='pending', verbose_name="认证状态")
    
    # 基础个人信息（所有用户都需要填写）
    real_name = models.CharField(max_length=50, blank=True, null=True, verbose_name="真实姓名")
    phone_regex = RegexValidator(regex=r'^1[3-9]\d{9}$', message="请输入有效的中国大陆手机号码")
    phone_number = models.CharField(validators=[phone_regex], max_length=11, blank=True, null=True, verbose_name="手机号码")
    id_card_number = models.CharField(max_length=18, blank=True, null=True, verbose_name="身份证号")
    current_address = models.TextField(blank=True, null=True, verbose_name="现居住地址")
    emergency_contact = models.CharField(max_length=50, blank=True, null=True, verbose_name="紧急联系人")
    emergency_phone = models.CharField(max_length=11, blank=True, null=True, verbose_name="紧急联系电话")
    
    # 志愿者特定信息
    volunteer_experience = models.TextField(blank=True, verbose_name="志愿服务经历")
    skills = models.TextField(blank=True, verbose_name="专业技能")
    available_time = models.CharField(max_length=100, blank=True, verbose_name="可服务时间")
    
    # 活动发布者特定信息
    organization_name = models.CharField(max_length=200, blank=True, verbose_name="组织/机构名称")
    organization_type = models.CharField(max_length=50, blank=True, choices=[
        ('ngo', '非政府组织'),
        ('school', '学校'),
        ('company', '企业'),
        ('community', '社区组织'),
        ('government', '政府部门'),
        ('other', '其他'),
    ], verbose_name="组织类型")
    organization_certificate = models.ImageField(upload_to='certificates/%Y/%m/%d/', blank=True, verbose_name="组织机构证明")
    organization_description = models.TextField(blank=True, verbose_name="组织描述")
    
    # 证明文件（可上传多个）
    identity_document = models.ImageField(upload_to='identities/%Y/%m/%d/', blank=True, null=True, verbose_name="身份证明文件")
    additional_documents = models.JSONField(default=list, blank=True, verbose_name="附加证明文件")
    
    # 审核信息
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="提交时间")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='reviewed_profiles', verbose_name="审核人")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    review_notes = models.TextField(blank=True, verbose_name="审核意见")
    
    # 隐私设置
    data_consent = models.BooleanField(default=False, verbose_name="数据使用同意")
    last_data_access = models.DateTimeField(null=True, blank=True, verbose_name="上次数据访问时间")
    
    class Meta:
        verbose_name = "用户详细资料"
        verbose_name_plural = "用户详细资料"
    
    def __str__(self):
        return f"{self.real_name} ({self.user.username})"
    
    def get_role_display_name(self):
        return dict(self.USER_ROLES).get(self.role, '未知')
    
    def can_participate(self):
        """检查用户是否可以参与志愿活动"""
        return self.role == 'volunteer' and self.verification_status == 'approved'
    
    def can_publish(self):
        """检查用户是否可以发布活动"""
        return self.role == 'organizer' and self.verification_status == 'approved'

# 审核记录表（记录所有审核操作）
class VerificationLog(models.Model):
    ACTION_TYPES = [
        ('submit', '提交认证'),
        ('approve', '通过认证'),
        ('reject', '拒绝认证'),
        ('request_update', '要求补充资料'),
        ('role_change', '角色变更'),
    ]
    
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='logs', verbose_name="用户资料")
    action = models.CharField(max_length=20, choices=ACTION_TYPES, verbose_name="操作类型")
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='verification_actions', verbose_name="执行人")
    performed_at = models.DateTimeField(auto_now_add=True, verbose_name="执行时间")
    notes = models.TextField(blank=True, verbose_name="操作说明")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP地址")
    
    class Meta:
        ordering = ['-performed_at']
        verbose_name = "认证日志"
        verbose_name_plural = "认证日志"
    
    def __str__(self):
        return f"{self.profile.real_name} - {self.get_action_display()}"

# 数据访问日志（记录管理员查看用户信息）
class DataAccessLog(models.Model):
    ACCESS_TYPES = [
        ('view_profile', '查看用户资料'),
        ('export_data', '导出数据'),
        ('modify_data', '修改数据'),
    ]
    
    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='data_accesses', verbose_name="管理员")
    accessed_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='access_logs', verbose_name="被访问用户")
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPES, verbose_name="访问类型")
    accessed_at = models.DateTimeField(auto_now_add=True, verbose_name="访问时间")
    reason = models.TextField(verbose_name="访问原因")
    accessed_fields = models.JSONField(default=list, verbose_name="访问字段")
    
    class Meta:
        ordering = ['-accessed_at']
        verbose_name = "数据访问日志"
        verbose_name_plural = "数据访问日志"

from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """用户创建时自动创建用户资料"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """用户保存时自动保存用户资料"""
    if hasattr(instance, 'profile'):
        instance.profile.save()

class VolunteerActivity(models.Model):
    """志愿活动模型"""
    ACTIVITY_STATUS = [
        ('draft', '草稿'),
        ('published', '已发布'),
        ('ongoing', '进行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]
    
    ACTIVITY_TYPES = [
        ('elderly', '敬老服务'),
        ('environment', '环境保护'),
        ('education', '教育支持'),
        ('medical', '医疗健康'),
        ('community', '社区服务'),
        ('other', '其他'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="活动标题")
    description = models.TextField(verbose_name="活动描述")
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES, default='other', verbose_name="活动类型")
    
    # 活动时间
    start_time = models.DateTimeField(verbose_name="开始时间")
    end_time = models.DateTimeField(verbose_name="结束时间")
    
    # 活动地点
    location = models.CharField(max_length=200, verbose_name="活动地点")
    address_detail = models.TextField(verbose_name="详细地址")
    
    # 组织者
    organizer = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='organized_activities', verbose_name="组织者")
    
    # 参与人数
    max_participants = models.PositiveIntegerField(verbose_name="最大参与人数")
    current_participants = models.PositiveIntegerField(default=0, verbose_name="当前报名人数")
    
    # 状态
    status = models.CharField(max_length=20, choices=ACTIVITY_STATUS, default='draft', verbose_name="活动状态")
    
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="发布时间")
    
    # 审核信息
    is_approved = models.BooleanField(default=False, verbose_name="是否审核通过")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_activities', verbose_name="审核人")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    
    # 审核扩展字段（与现有 is_approved/approved_by 配合）
    review_notes = models.TextField(blank=True, verbose_name='审核备注')
    reviewed_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_activities',
        verbose_name='审核人'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')

    # 新增拒绝状态（可选项：'rejected'）
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('published', '已发布'),
        ('ongoing', '进行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
        ('rejected', '已拒绝'),          # 新增
    )
    
    class Meta:
        verbose_name = "志愿活动"
        verbose_name_plural = "志愿活动"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def is_full(self):
        """检查活动是否已满"""
        return self.current_participants >= self.max_participants
    
    def can_apply(self):
        """检查是否可以报名"""
        return (
            self.status == 'published' and 
            not self.is_full() and
            self.is_approved
        )
    
    def get_duration(self):
        """获取活动持续时间"""
        from django.utils import timezone
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_activities', verbose_name='审核人'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    review_notes = models.TextField(blank=True, verbose_name='审核备注')

class ActivityApplication(models.Model):
    """活动报名记录"""
    APPLICATION_STATUS = [
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('cancelled', '已取消'),
    ]
    
    activity = models.ForeignKey(VolunteerActivity, on_delete=models.CASCADE, related_name='applications', verbose_name="活动")
    volunteer = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='applications', verbose_name="志愿者")
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS, default='pending', verbose_name="报名状态")
    
    # 报名信息
    application_notes = models.TextField(blank=True, verbose_name="报名备注")
    experience_expectation = models.TextField(blank=True, verbose_name="经验期望")
    
    # 审核信息
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_applications', verbose_name="审核人")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    review_notes = models.TextField(blank=True, verbose_name="审核意见")
    
    # 时间戳
    applied_at = models.DateTimeField(auto_now_add=True, verbose_name="报名时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        verbose_name = "活动报名"
        verbose_name_plural = "活动报名"
        unique_together = ['activity', 'volunteer']
        ordering = ['-applied_at']
    
    def __str__(self):
        return f"{self.volunteer.real_name} - {self.activity.title}"

    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_applications', verbose_name='审批人'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    review_notes = models.TextField(blank=True, verbose_name='审批备注/拒绝理由')

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('reminder', '活动提醒'),
        ('change', '活动变更'),
        ('cancellation', '活动取消'),
        ('other', '其他通知'),
    )
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='received_notifications',
        verbose_name='接收者'
    )
    sender = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_notifications', verbose_name='发送者'
    )
    activity = models.ForeignKey(
        VolunteerActivity, on_delete=models.CASCADE, null=True, blank=True,
        related_name='notifications', verbose_name='关联活动'
    )
    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPES, default='other',
        verbose_name='通知类型'
    )
    content = models.TextField(verbose_name='通知内容')
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='阅读时间')

    class Meta:
        ordering = ['-created_at']
        verbose_name = '通知'
        verbose_name_plural = '通知'

    def __str__(self):
        return f"通知给 {self.recipient.username} - {self.created_at:%Y-%m-%d}"

    # models.py 中添加
class Announcement(models.Model):
    """平台公告"""
    title = models.CharField(max_length=200, verbose_name="公告标题")
    content = models.TextField(verbose_name="公告内容")
    is_published = models.BooleanField(default=True, verbose_name="是否发布")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    created_by = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            verbose_name="创建者"
            )

    class Meta:
        verbose_name = "平台公告"
        verbose_name_plural = "平台公告"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title

class Guide(models.Model):
    """操作指南"""
    title = models.CharField(max_length=200, verbose_name="指南标题")
    content = models.TextField(verbose_name="指南内容")
    category = models.CharField(max_length=50, choices=[
        ('register', '注册登录'),
        ('verification', '身份认证'),
        ('activity', '活动参与'),
        ('organizer', '活动发布'),
        ('other', '其他')
    ], verbose_name="分类")
    is_published = models.BooleanField(default=True, verbose_name="是否发布")
    order = models.IntegerField(default=0, verbose_name="排序")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    
    class Meta:
        verbose_name = "操作指南"
        verbose_name_plural = "操作指南"
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return self.title

class Feedback(models.Model):
    """用户反馈"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="反馈用户")
    content = models.TextField(verbose_name="反馈内容")
    contact = models.CharField(max_length=100, blank=True, verbose_name="联系方式")
    status = models.CharField(max_length=20, choices=[
        ('pending', '待处理'),
        ('reviewed', '已查看'),
        ('resolved', '已解决'),
        ('ignored', '忽略')
    ], default='pending', verbose_name="处理状态")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="解决时间")
    response = models.TextField(blank=True, verbose_name="回复内容")
    
    class Meta:
        verbose_name = "用户反馈"
        verbose_name_plural = "用户反馈"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"反馈 - {self.user.username if self.user else '匿名'}"

class SystemSetting(models.Model):
    """系统设置存储模型"""
    SETTING_CATEGORIES = [
        ('general', '常规设置'),
        ('security', '安全设置'),
        ('email', '邮件设置'),
        ('verification', '验证设置'),
        ('activity', '活动设置'),
        ('ui', '界面设置'),
    ]
    
    SETTING_TYPES = [
        ('string', '字符串'),
        ('integer', '整数'),
        ('boolean', '布尔值'),
        ('json', 'JSON对象'),
        ('text', '长文本'),
    ]
    
    key = models.CharField(max_length=100, unique=True, verbose_name="设置键")
    value = models.TextField(verbose_name="设置值")
    name = models.CharField(max_length=200, verbose_name="设置名称")
    description = models.TextField(blank=True, verbose_name="设置描述")
    category = models.CharField(max_length=50, choices=SETTING_CATEGORIES, default='general', verbose_name="分类")
    type = models.CharField(max_length=20, choices=SETTING_TYPES, default='string', verbose_name="值类型")
    is_public = models.BooleanField(default=False, verbose_name="是否公开")
    is_editable = models.BooleanField(default=True, verbose_name="是否可编辑")
    
    # 审计信息
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="最后更新者")
    
    class Meta:
        verbose_name = "系统设置"
        verbose_name_plural = "系统设置"
        ordering = ['category', 'key']
    
    def __str__(self):
        return f"{self.name} ({self.key})"
    
    def get_typed_value(self):
        """根据类型获取转换后的值"""
        if self.type == 'boolean':
            return self.value.lower() in ['true', '1', 'yes', 'y', 'on']
        elif self.type == 'integer':
            try:
                return int(self.value)
            except:
                return 0
        elif self.type == 'json':
            try:
                return json.loads(self.value)
            except:
                return {}
        else:
            return self.value

class ActivityReviewLog(models.Model):
    """活动审核日志"""
    ACTION_CHOICES = (
        ('submit', '提交审核'),
        ('approve', '通过'),
        ('reject', '拒绝'),
        ('need_review', '要求修改'),
        ('update', '更新'),
        ('publish', '发布'),
        ('cancel', '取消'),
    )
    activity = models.ForeignKey(
        'VolunteerActivity', on_delete=models.CASCADE,
        related_name='review_logs', verbose_name='关联活动'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='操作')
    performed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='activity_review_logs', verbose_name='操作人'
    )
    performed_at = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')
    notes = models.TextField(blank=True, verbose_name='备注')
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name='IP地址')

    class Meta:
        ordering = ['-performed_at']
        verbose_name = '活动审核日志'
        verbose_name_plural = '活动审核日志'

    def __str__(self):
        return f"{self.activity.title} - {self.get_action_display()} - {self.performed_at:%Y-%m-%d}"

class SystemSettingManager:
    """系统设置管理器"""
    
    _cache = {}
    
    @classmethod
    def get_setting(cls, key, default=None):
        """获取设置值"""
        # 先检查缓存
        if key in cls._cache:
            return cls._cache[key]
        
        try:
            setting = SystemSetting.objects.get(key=key)
            value = setting.get_typed_value()
            cls._cache[key] = value
            return value
        except SystemSetting.DoesNotExist:
            return default
    
    @classmethod
    def set_setting(cls, key, value, name=None, description=None, 
                   category='general', type='string', is_public=False, user=None):
        """设置或更新系统设置"""
        try:
            setting = SystemSetting.objects.get(key=key)
            # 更新现有设置
            setting.value = str(value)
            setting.name = name or setting.name
            setting.description = description or setting.description
            setting.category = category
            setting.type = type
            setting.is_public = is_public
            if user:
                setting.updated_by = user
            setting.save()
        except SystemSetting.DoesNotExist:
            # 创建新设置
            setting = SystemSetting.objects.create(
                key=key,
                value=str(value),
                name=name or key,
                description=description or '',
                category=category,
                type=type,
                is_public=is_public,
                updated_by=user
            )
        
        # 更新缓存
        cls._cache[key] = setting.get_typed_value()
        
        return setting
    
    @classmethod
    def get_all_settings(cls, category=None):
        """获取所有设置"""
        queryset = SystemSetting.objects.all()
        if category:
            queryset = queryset.filter(category=category)
        
        settings = {}
        for setting in queryset:
            settings[setting.key] = {
                'value': setting.get_typed_value(),
                'name': setting.name,
                'description': setting.description,
                'category': setting.category,
                'type': setting.type,
                'is_editable': setting.is_editable,
                'updated_at': setting.updated_at,
                'updated_by': setting.updated_by.username if setting.updated_by else None,
            }
        
        return settings
    
    @classmethod
    def initialize_default_settings(cls):
        """初始化默认设置"""
        default_settings = [
            # 常规设置
            {
                'key': 'site_name',
                'value': '桑榆共暖志愿服务平台',
                'name': '网站名称',
                'description': '网站显示的名称',
                'category': 'general',
                'type': 'string',
                'is_public': True,
            },
            {
                'key': 'site_description',
                'value': '连接志愿者与需要帮助的老人，传递温暖与关怀',
                'name': '网站描述',
                'description': '网站的描述信息',
                'category': 'general',
                'type': 'text',
                'is_public': True,
            },
            {
                'key': 'contact_email',
                'value': '2994192894@qq.com',
                'name': '联系邮箱',
                'description': '网站的联系邮箱',
                'category': 'general',
                'type': 'string',
                'is_public': True,
            },
            {
                'key': 'contact_phone',
                'value': '',
                'name': '联系电话',
                'description': '网站的联系电话',
                'category': 'general',
                'type': 'string',
                'is_public': True,
            },
            {
                'key': 'site_address',
                'value': '北京市海淀区',
                'name': '联系地址',
                'description': '',
                'category': 'general',
                'type': 'string',
                'is_public': True,
            },
            
            # 功能开关
            {
                'key': 'enable_registration',
                'value': 'true',
                'name': '启用用户注册',
                'description': '是否允许新用户注册',
                'category': 'general',
                'type': 'boolean',
                'is_public': False,
            },
            {
                'key': 'enable_email_verification',
                'value': 'true',
                'name': '启用邮箱验证',
                'description': '注册和登录时是否需要进行邮箱验证',
                'category': 'verification',
                'type': 'boolean',
                'is_public': False,
            },
            {
                'key': 'enable_feedback',
                'value': 'true',
                'name': '启用反馈系统',
                'description': '是否允许用户提交反馈',
                'category': 'general',
                'type': 'boolean',
                'is_public': False,
            },
            {
                'key': 'enable_activity_creation',
                'value': 'true',
                'name': '允许创建活动',
                'description': '认证通过的活动发布者是否可以创建新活动',
                'category': 'activity',
                'type': 'boolean',
                'is_public': False,
            },
            
            # 审核设置
            {
                'key': 'auto_approve_volunteers',
                'value': 'false',
                'name': '自动批准志愿者',
                'description': '志愿者注册后是否自动通过审核',
                'category': 'verification',
                'type': 'boolean',
                'is_public': False,
            },
            {
                'key': 'auto_approve_organizers',
                'value': 'false',
                'name': '自动批准活动发布者',
                'description': '活动发布者注册后是否自动通过审核',
                'category': 'verification',
                'type': 'boolean',
                'is_public': False,
            },
            {
                'key': 'auto_approve_activities',
                'value': 'false',
                'name': '自动批准活动',
                'description': '新创建的活动是否自动通过审核',
                'category': 'activity',
                'type': 'boolean',
                'is_public': False,
            },
            {
                'key': 'verification_expiry_days',
                'value': '30',
                'name': '认证有效期（天）',
                'description': '用户认证通过后的有效期天数',
                'category': 'verification',
                'type': 'integer',
                'is_public': False,
            },
            
            # 活动设置
            {
                'key': 'max_activities_per_organizer',
                'value': '10',
                'name': '活动发布者最大活动数',
                'description': '每个活动发布者可以同时发布的最大活动数量',
                'category': 'activity',
                'type': 'integer',
                'is_public': False,
            },
            {
                'key': 'max_participants_per_activity',
                'value': '50',
                'name': '活动最大参与人数',
                'description': '每个活动最多可以有多少人参与',
                'category': 'activity',
                'type': 'integer',
                'is_public': True,
            },
            {
                'key': 'activity_application_deadline_hours',
                'value': '24',
                'name': '活动报名截止时间（小时）',
                'description': '活动开始前多少小时停止接受报名',
                'category': 'activity',
                'type': 'integer',
                'is_public': True,
            },
            
            # 邮件设置
            {
                'key': 'email_smtp_server',
                'value': 'smtp.qq.com',
                'name': 'SMTP服务器',
                'description': '发送邮件的SMTP服务器地址',
                'category': 'email',
                'type': 'string',
                'is_public': False,
            },
            {
                'key': 'email_smtp_port',
                'value': '587',
                'name': 'SMTP端口',
                'description': 'SMTP服务器的端口号',
                'category': 'email',
                'type': 'integer',
                'is_public': False,
            },
            {
                'key': 'email_smtp_user',
                'value': '2994192894@qq.com',
                'name': 'SMTP用户名',
                'description': 'SMTP服务器的登录用户名',
                'category': 'email',
                'type': 'string',
                'is_public': False,
            },
            {
                'key': 'email_from_name',
                'value': '桑榆共暖志愿服务平台',
                'name': '发件人名称',
                'description': '等我写完再说',
                'category': 'email',
                'type': 'string',
                'is_public': True,
            },
            {
                'key': 'email_smtp_password',
                'value': 'K2(4{%vHdbSjhEhE', 
                'name': 'SMTP密码',
                'description': 'SMTP服务器的登录密码',
                'category': 'email',
                'type': 'string',
                'is_public': False,
            },
            
            # 安全设置
            {
                'key': 'max_login_attempts',
                'value': '5',
                'name': '最大登录尝试次数',
                'description': '用户连续登录失败的最大次数，超过将被锁定',
                'category': 'security',
                'type': 'integer',
                'is_public': False,
            },
            {
                'key': 'session_timeout_minutes',
                'value': '120',
                'name': '会话超时时间（分钟）',
                'description': '用户登录后会话的超时时间',
                'category': 'security',
                'type': 'integer',
                'is_public': False,
            },
            {
                'key': 'password_min_length',
                'value': '8',
                'name': '密码最小长度',
                'description': '用户密码的最小长度要求',
                'category': 'security',
                'type': 'integer',
                'is_public': True,
            },
            {
                'key': 'require_password_complexity',
                'value': 'true',
                'name': '要求密码复杂度',
                'description': '是否要求密码包含大小写字母、数字和特殊字符',
                'category': 'security',
                'type': 'boolean',
                'is_public': True,
            },
            
            # 界面设置
            {
                'key': 'theme_color',
                'value': '#1a237e',
                'name': '主题颜色',
                'description': '网站的主题颜色',
                'category': 'ui',
                'type': 'string',
                'is_public': True,
            },
            {
                'key': 'show_latest_activities_count',
                'value': '5',
                'name': '首页显示最新活动数量',
                'description': '首页门户显示的最新活动数量',
                'category': 'ui',
                'type': 'integer',
                'is_public': False,
            },
            {
                'key': 'show_latest_announcements_count',
                'value': '3',
                'name': '首页显示最新公告数量',
                'description': '首页门户显示的最新公告数量',
                'category': 'ui',
                'type': 'integer',
                'is_public': False,
            },
        ]
        
        for setting_data in default_settings:
            try:
                cls.set_setting(**setting_data)
            except Exception as e:
                print(f"初始化设置 {setting_data['key']} 失败: {e}")
        
        return True

class UserPoints(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='points')
    total_earned = models.IntegerField(default=0, verbose_name="总获取积分")  # 用于星级评定
    balance = models.IntegerField(default=0, verbose_name="可用积分")          # 用于兑换
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "用户积分账户"
        verbose_name_plural = "用户积分账户"

class PointsTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('daily_login', '每日登录'),
        ('signup_activity', '报名活动'),
        ('publish_activity', '发布活动'),
        ('reward', '奖励积分'),
        ('penalty', '惩罚扣除'),
        ('exchange', '积分兑换'),
        ('admin_adjust', '管理员调整'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='points_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name="类型")
    amount = models.IntegerField(verbose_name="变动数量")  # 正为增加，负为扣除
    balance_after = models.IntegerField(verbose_name="变动后可用积分")
    total_earned_after = models.IntegerField(verbose_name="变动后总获取积分")
    source_object_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="来源对象ID")  # 如活动ID、订单ID等
    source_object_type = models.CharField(max_length=50, blank=True, null=True, verbose_name="来源对象类型")  # 如 'activity', 'order'
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='operated_transactions', verbose_name="操作人")
    remark = models.TextField(blank=True, verbose_name="备注")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "积分变动记录"
        verbose_name_plural = "积分变动记录"

class StarLevelConfig(models.Model):
    ROLE_CHOICES = (
        ('volunteer', '志愿者'),
        ('organizer', '活动发布者'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="角色")
    min_points = models.IntegerField(verbose_name="最低总获取积分")
    level_name = models.CharField(max_length=50, verbose_name="星级名称")  # 如 "一星志愿者"
    description = models.TextField(blank=True, verbose_name="描述")
    order = models.IntegerField(default=0, verbose_name="排序")
    is_active = models.BooleanField(default=True, verbose_name="启用")

    class Meta:
        ordering = ['role', 'order']
        unique_together = ['role', 'min_points']
        verbose_name = "星级评定配置"
        verbose_name_plural = "星级评定配置"

class PointsShopItem(models.Model):
    name = models.CharField(max_length=200, verbose_name="商品名称")
    description = models.TextField(verbose_name="商品描述")
    points_required = models.IntegerField(verbose_name="所需积分")
    stock = models.IntegerField(default=0, verbose_name="库存")  # -1 表示不限
    image = models.ImageField(upload_to='shop_items/', blank=True, null=True, verbose_name="商品图片")
    is_active = models.BooleanField(default=True, verbose_name="上架")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "积分商城商品"
        verbose_name_plural = "积分商城商品"

    def __str__(self):
        return self.name

class PointsOrder(models.Model):
    STATUS_CHOICES = (
        ('pending', '待处理'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='points_orders')
    item = models.ForeignKey(PointsShopItem, on_delete=models.PROTECT, verbose_name="商品")
    quantity = models.PositiveIntegerField(default=1, verbose_name="数量")
    points_spent = models.IntegerField(verbose_name="消耗积分")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    remark = models.TextField(blank=True, verbose_name="备注")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="处理时间")
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_orders', verbose_name="处理人")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "积分兑换订单"
        verbose_name_plural = "积分兑换订单"
