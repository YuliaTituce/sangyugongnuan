# test_email_notification.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'volunteer_project.settings')
django.setup()

from volunteers.models import UserProfile, User
from volunteers.utils import send_verification_status_email

def test_email_notification():
    """测试邮件通知功能"""
    print("测试邮件通知功能...")
    
    # 获取一个测试用户
    try:
        # 查找一个通过认证的用户
        profile = UserProfile.objects.filter(
            verification_status='approved'
        ).first()
        
        if profile:
            print(f"测试用户: {profile.user.username} ({profile.user.email})")
            print(f"用户角色: {profile.role}")
            print(f"验证状态: {profile.verification_status}")
            
            # 测试不同状态的邮件
            test_statuses = ['approved', 'rejected', 'needs_review']
            
            for status in test_statuses:
                print(f"\n测试 {status} 状态邮件:")
                profile.verification_status = status
                profile.review_notes = f"测试邮件 - {status}"
                
                try:
                    send_verification_status_email(profile)
                    print(f"✅ {status} 状态邮件发送成功")
                except Exception as e:
                    print(f"❌ {status} 状态邮件发送失败: {e}")
        else:
            print("未找到合适的测试用户")
            
    except Exception as e:
        print(f"测试失败: {e}")

if __name__ == "__main__":
    test_email_notification()