# volunteers/management/commands/init_settings.py
from django.core.management.base import BaseCommand
from volunteers.models import SystemSettingManager

class Command(BaseCommand):
    help = '初始化系统默认设置'
    
    def handle(self, *args, **kwargs):
        self.stdout.write('正在初始化系统默认设置...')
        count = SystemSettingManager.initialize_default_settings()
        self.stdout.write(self.style.SUCCESS(f'系统默认设置初始化完成，共初始化{count}个设置项'))