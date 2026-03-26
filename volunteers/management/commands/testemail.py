from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import smtplib

class Command(BaseCommand):
    help = '测试邮件发送功能'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            help='收件人邮箱地址'
        )
    
    def handle(self, *args, **options):
        to_email = options.get('to') or settings.EMAIL_HOST_USER
        
        self.stdout.write('=== 测试邮件发送 ===')
        self.stdout.write(f'发件人: {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write(f'收件人: {to_email}')
        
        # 测试1: 直接SMTP连接
        self.stdout.write('\n[测试1] 直接SMTP连接...')
        try:
            server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10)
            server.ehlo()
            if settings.EMAIL_USE_TLS:
                server.starttls()
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            self.stdout.write(self.style.SUCCESS('  ✅ SMTP连接成功'))
            server.quit()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ SMTP连接失败: {e}'))
        
        # 测试2: Django邮件发送
        self.stdout.write('\n[测试2] Django邮件发送...')
        try:
            send_mail(
                subject='桑榆共暖 - 功能测试邮件',
                message='这是一封测试邮件，确认您的邮件配置正确。',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS('  ✅ 邮件发送成功'))
            self.stdout.write('  请检查收件箱和垃圾邮件箱')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ 邮件发送失败: {e}'))
        
        self.stdout.write('\n=== 测试完成 ===')