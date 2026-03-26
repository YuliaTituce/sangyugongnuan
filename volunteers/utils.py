# volunteers/utils.py
from django.core.mail import send_mail          # <-- 在此处添加
from django.conf import settings
from django.db import transaction
from .models import EmailVerificationCode, User, UserProfile, UserPoints, PointsTransaction
import random
import string
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

def generate_verification_code(length=6):
    """生成数字验证码"""
    return ''.join(random.choices(string.digits, k=length))

def send_verification_email(email, purpose='register'):
    """发送验证码邮件"""
    try:
        # 延迟导入，避免在非Django环境下配置问题
        from django.core.mail import send_mail
        from django.conf import settings
        from django.utils import timezone
        from .models import EmailVerificationCode
        
        # 清理过期验证码
        EmailVerificationCode.objects.filter(
            email=email, 
            purpose=purpose,
            expires_at__lt=timezone.now()
        ).delete()
        
        # 检查发送频率（防止滥用）
        recent_codes = EmailVerificationCode.objects.filter(
            email=email,
            purpose=purpose,
            created_at__gte=timezone.now() - timedelta(minutes=1)
        ).count()
        
        if recent_codes >= 3:
            return False, "发送过于频繁，请稍后再试"
        
        # 生成验证码
        code = generate_verification_code()
        expires_at = timezone.now() + timedelta(minutes=10)
        
        # 保存到数据库
        EmailVerificationCode.objects.create(
            email=email,
            code=code,
            purpose=purpose,
            expires_at=expires_at
        )
        
        # 发送邮件
        subject = "桑榆共暖志愿服务平台验证码"
        
        if purpose == 'register':
            message = f"您正在注册桑榆共暖志愿服务平台，验证码为：{code}，10分钟内有效。"
        elif purpose == 'login':
            message = f"您正在登录桑榆共暖志愿服务平台，验证码为：{code}，10分钟内有效。"
        else:
            message = f"您的验证码为：{code}，10分钟内有效。"
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            return True, "验证码已发送"
        except Exception as e:
            return False, f"发送失败：{str(e)}"
            
    except Exception as e:
        logger.error(f"发送验证码邮件失败: {str(e)}")
        return False, f"系统错误：{str(e)}"

def verify_email_code(email, code, purpose):
    """验证邮箱验证码"""
    try:
        from django.utils import timezone
        from .models import EmailVerificationCode
        
        verification = EmailVerificationCode.objects.get(
            email=email,
            code=code,
            purpose=purpose,
            is_used=False,
            expires_at__gt=timezone.now()
        )
        verification.is_used = True
        verification.save()
        return True, "验证成功"
    except EmailVerificationCode.DoesNotExist:
        return False, "验证码无效或已过期"
    except Exception as e:
        logger.error(f"验证邮箱验证码失败: {str(e)}")
        return False, f"验证出错：{str(e)}"

def send_verification_status_email(profile):
    """发送认证状态通知邮件"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from django.utils import timezone
        
        user_email = profile.user.email
        print(f"\n📧 准备发送邮件给: {user_email}")
        print(f"👤 用户: {profile.real_name}")
        print(f"🎯 状态: {profile.verification_status}")
        
        # 根据状态生成邮件内容
        if profile.verification_status == 'approved':
            subject = "恭喜！您的身份认证已通过 - 桑榆共暖"
            
            if profile.role == 'volunteer':
                message = f"""
尊敬的{profile.real_name}：

恭喜！您的志愿者身份认证已经通过审核。

您现在可以：
1. 完善个人资料
2. 浏览并报名参与志愿活动
3. 享受平台提供的所有功能

感谢您对桑榆共暖志愿服务平台的支持！

此致
桑榆共暖团队
{timezone.now().date()}
                """
            else:
                message = f"""
尊敬的{profile.real_name}：

恭喜！您的活动发布者身份认证已经通过审核。

您现在可以：
1. 发布和管理志愿活动
2. 招募和管理志愿者
3. 享受平台提供的所有功能

感谢您对桑榆共暖志愿服务平台的支持！

此致
桑榆共暖团队
{timezone.now().date()}
                """
                
        elif profile.verification_status == 'rejected':
            subject = "您的身份认证未通过 - 桑榆共暖"
            message = f"""
尊敬的{profile.real_name}：

很遗憾，您的身份认证申请未通过审核。

原因：{profile.review_notes or '请检查填写的信息是否准确完整'}

请您：
1. 检查并修改认证信息
2. 重新提交认证申请
3. 如有疑问，请联系平台客服

感谢您对桑榆共暖志愿服务平台的支持！

此致
桑榆共暖团队
{timezone.now().date()}
            """
            
        elif profile.verification_status == 'needs_review':
            subject = "请补充认证资料 - 桑榆共暖"
            message = f"""
尊敬的{profile.real_name}：

您的身份认证申请需要补充资料。

管理员意见：{profile.review_notes}

请您：
1. 登录平台查看具体要求
2. 补充或修改相关资料
3. 重新提交认证申请

感谢您对桑榆共暖志愿服务平台的支持！

此致
桑榆共暖团队
{timezone.now().date()}
            """
        else:
            return
        
        # 发送邮件
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user_email],
                fail_silently=False,
            )
            print(f"✅ 邮件发送成功: {user_email}")
            return True
        except Exception as e:
            print(f"❌ 邮件发送失败: {str(e)}")
            return False
            
    except Exception as e:
        print(f"💥 邮件功能异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def send_activity_review_email(activity, action, notes=''):
    """发送活动审核结果通知给组织者"""
    if not activity.organizer or not activity.organizer.user.email:
        return

    subject_map = {
        'approve': '【桑榆共暖】您的活动已通过审核',
        'reject': '【桑榆共暖】您的活动审核未通过',
        'need_review': '【桑榆共暖】您的活动需要修改',
    }
    subject = subject_map.get(action, '活动审核通知')

    action_text = {
        'approve': '已通过',
        'reject': '已被拒绝',
        'need_review': '需要修改后重新提交',
    }.get(action, '已处理')

    message = f"""
    <h3>活动审核结果通知</h3>
    <p>您好，{activity.organizer.real_name or activity.organizer.user.username}：</p>
    <p>您创建的活动 <strong>《{activity.title}》</strong> {action_text}。</p>
    """

    if notes:
        message += f"<p>审核备注：{notes}</p>"

    message += "<p>您可以登录系统查看详细信息。</p>"

    send_mail(
        subject,
        '',  # 纯文本内容（可留空）
        settings.DEFAULT_FROM_EMAIL,
        [activity.organizer.user.email],
        html_message=message,
        fail_silently=True,
    )

# ==================== 在 utils.py 末尾添加 ====================
def send_application_status_email(application):
    """发送报名审批结果邮件"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from django.utils import timezone

        user_email = application.volunteer.user.email
        activity = application.activity

        if application.status == 'approved':
            subject = f"报名成功：{activity.title} - 桑榆共暖"
            message = f"""
尊敬的{application.volunteer.real_name}：

恭喜！您对活动《{activity.title}》的报名申请已通过审核。

活动时间：{activity.start_time.strftime('%Y-%m-%d %H:%M')} - {activity.end_time.strftime('%Y-%m-%d %H:%M')}
活动地点：{activity.location}
组织者：{activity.organizer.real_name}（联系方式请登录平台查看）

请按时参加活动，如有变动请及时联系组织者。

此致
桑榆共暖团队
{timezone.now().date()}
            """
        elif application.status == 'rejected':
            subject = f"报名未通过：{activity.title} - 桑榆共暖"
            reason = application.review_notes or '未提供具体原因'
            message = f"""
尊敬的{application.volunteer.real_name}：

很遗憾，您对活动《{activity.title}》的报名申请未通过审核。

拒绝理由：{reason}

您可查看其他活动或联系平台管理员。

此致
桑榆共暖团队
{timezone.now().date()}
            """
        else:
            return

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=True,
        )
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"发送报名状态邮件失败: {e}")

def add_points_transaction(user, transaction_type, amount, source_obj=None, operator=None, remark=''):
    """
    为用户增加积分（amount可为负数），记录交易日志，并更新用户积分账户。
    返回布尔值表示是否成功。
    """
    from .models import UserPoints, PointsTransaction
    from django.db import transaction

    with transaction.atomic():
        points_account, created = UserPoints.objects.get_or_create(user=user)
        old_balance = points_account.balance
        old_total = points_account.total_earned

        # 更新账户
        points_account.balance += amount
        if amount > 0:
            points_account.total_earned += amount
        # 注意：扣除积分（amount<0）时 total_earned 不变，因为总获取积分不应减少
        points_account.save()

        # 记录交易
        source_id = str(source_obj.id) if source_obj else None
        source_type = source_obj.__class__.__name__ if source_obj else None
        PointsTransaction.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=points_account.balance,
            total_earned_after=points_account.total_earned,
            source_object_id=source_id,
            source_object_type=source_type,
            operator=operator,
            remark=remark
        )
        return True

def grant_daily_login_points(user):
    """给用户发放每日登录积分（如果今天未领取）"""
    from .models import PointsTransaction
    from datetime import date
    today = date.today()
    # 检查今天是否有 daily_login 记录
    if not PointsTransaction.objects.filter(
        user=user,
        transaction_type='daily_login',
        created_at__date=today
    ).exists():
        # 发放积分，设定为5分（可根据需要调整）
        points = 5
        add_points_transaction(
            user=user,
            transaction_type='daily_login',
            amount=points,
            operator=None,
            remark='每日登录奖励'
        )
        return True
    return False
