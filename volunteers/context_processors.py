from .models import SystemSettingManager

def system_settings(request):
    """将系统设置添加到所有模板上下文中"""
    return {
        'site_name': SystemSettingManager.get_setting('site_name', '桑榆共暖'),
        'site_description': SystemSettingManager.get_setting('site_description', '志愿服务平台'),
        'contact_email': SystemSettingManager.get_setting('contact_email', 'contact@example.com'),
        'contact_phone': SystemSettingManager.get_setting('contact_phone', ''),
        'site_address': SystemSettingManager.get_setting('site_address', '北京市海淀区'),
    }