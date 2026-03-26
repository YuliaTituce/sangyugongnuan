from django.shortcuts import redirect
from django.contrib import messages
from .models import SystemSettingManager

class FeatureControlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # 检查注册功能是否开启
        if request.path == '/register/' and not SystemSettingManager.get_setting('enable_registration', True):
            messages.error(request, "当前暂不接受新用户注册")
            return redirect('index')
        
        # 检查反馈功能是否开启
        if request.path == '/feedback/' and not SystemSettingManager.get_setting('enable_feedback', True):
            messages.error(request, "反馈功能暂时关闭")
            return redirect('portal')
        
        response = self.get_response(request)
        return response