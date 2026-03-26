from django import template
from ..models import SystemSettingManager

register = template.Library()

@register.simple_tag
def get_setting(key, default=''):
    """模板标签：获取系统设置"""
    try:
        return SystemSettingManager.get_setting(key, default)
    except:
        return default

@register.filter
def get_setting_value(key, default=''):
    """模板过滤器：获取系统设置"""
    try:
        return SystemSettingManager.get_setting(key, default)
    except:
        return default

@register.simple_tag
def site_name():
    """获取网站名称"""
    return SystemSettingManager.get_setting('site_name', '桑榆共暖')

@register.simple_tag
def contact_email():
    """获取联系邮箱"""
    return SystemSettingManager.get_setting('contact_email', '2994192894@qq.com')

@register.simple_tag
def contact_phone():
    """获取联系电话"""
    return SystemSettingManager.get_setting('contact_phone', '')

@register.simple_tag
def site_description():
    """获取网站描述"""
    return SystemSettingManager.get_setting('site_description', '志愿服务平台')