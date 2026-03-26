from django.urls import path
from . import views, admin_views
from django.views.generic import RedirectView

urlpatterns = [
    # 首页路由
    path('', views.portal_view, name='home'),  # 根路径指向门户
    path('portal/', views.portal_view, name='portal'),  # 保留portal路径
    path('index/', RedirectView.as_view(pattern_name='home', permanent=True), name='index'), 
    
    # 搜索和反馈
    path('search/', views.search_view, name='search'),
    path('feedback/', views.feedback_view, name='feedback'),
    
    # 用户认证相关
    path('register/', views.RegisterView.as_view(), name='register'),
    path('send-code/', views.SendVerificationCodeView.as_view(), name='send_code'),
    path('login/code/', views.LoginWithCodeView.as_view(), name='login_with_code'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # 身份认证相关
    path('role-selection/', views.RoleSelectionView.as_view(), name='role_selection'),
    path('profile/verification/', views.profile_verification, name='profile_verification'),
    path('verification/status/', views.verification_status, name='verification_status'),

    # 活动策划者活动管理
    path('organizer/activities/', views.organizer_activities, name='organizer_activities'),
    
    # 活动相关（去掉重复的）
    path('activities/', views.activity_list, name='activity_list'),
    path('activities/create/', views.create_activity, name='create_activity'),
    path('activities/<int:activity_id>/', views.activity_detail, name='activity_detail'),
    path('activities/<int:activity_id>/apply/', views.apply_activity, name='apply_activity'),
    path('activities/<int:activity_id>/edit/', views.edit_activity, name='edit_activity'),
    path('activities/<int:activity_id>/delete/', views.delete_activity, name='delete_activity'),

    # 管理员路由
    path('admin/login/', admin_views.admin_login, name='admin_login'),
    path('admin/logout/', admin_views.admin_logout, name='admin_logout'),
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('admin/statistics/', admin_views.admin_statistics, name='admin_statistics'),
    path('admin/users/', admin_views.user_management, name='user_management'),
    path('admin/users/<int:user_id>/', admin_views.user_detail, name='user_detail'),
    path('admin/content/', admin_views.content_management, name='content_management'),
    path('admin/feedback/', admin_views.feedback_management, name='feedback_management'),
    path('admin/settings/', admin_views.system_settings, name='system_settings'),
    path('admin/review/<int:profile_id>/', admin_views.review_profile, name='review_profile'),
    path('admin/batch-approve/', admin_views.batch_approve, name='batch_approve'),

    # 活动管理路由
    path('admin/activities/', admin_views.admin_activities, name='admin_activities'),
    path('admin/activities/<int:activity_id>/', admin_views.admin_activity_detail, name='admin_activity_detail'),
    path('admin/activities/batch/', admin_views.batch_action_activities, name='batch_action_activities'),
    path('admin/activities/analytics/', admin_views.activity_analytics, name='activity_analytics'),
    
    # 用户管理增强路由
    path('admin/users/<int:user_id>/update/', admin_views.update_user_status, name='update_user_status'),
    path('admin/users/export/', admin_views.export_users, name='export_users'),
    
    # 数据管理路由
    path('admin/data/', admin_views.data_management, name='data_management'),
    path('admin/data/cleanup/', admin_views.cleanup_data, name='cleanup_data'),

    # 活动管理批量操作
    path('admin/activities/batch/', admin_views.batch_action_activities, name='batch_action_activities'),
    # 单个活动删除
    path('admin/activity/<int:activity_id>/delete/', admin_views.delete_activity, name='delete_activity'),
    # 发送活动通知
    path('admin/activity/<int:activity_id>/notify/', admin_views.send_activity_notification, name='send_activity_notification'),
    # 活动分析（可选）
    path('admin/analytics/activities/', admin_views.activity_analytics, name='activity_analytics'),

    # 积分管理
    path('admin/points/', admin_views.points_management, name='points_management'),
    path('admin/points/adjust/', admin_views.adjust_points, name='adjust_points'),
    path('admin/points/star-level/', admin_views.star_level_config, name='star_level_config'),

    # 积分商城管理
    path('admin/shop/items/', admin_views.shop_item_list, name='shop_item_list'),
    path('admin/shop/items/create/', admin_views.shop_item_create, name='shop_item_create'),
    path('admin/shop/items/<int:item_id>/edit/', admin_views.shop_item_edit, name='shop_item_edit'),
    path('admin/shop/items/<int:item_id>/delete/', admin_views.shop_item_delete, name='shop_item_delete'),

    # 积分商城用户端
    path('shop/', views.shop_index, name='shop_index'),
    path('shop/exchange/<int:item_id>/', views.shop_exchange, name='shop_exchange'),
    path('shop/orders/', views.shop_orders, name='shop_orders'),
    # 管理员订单管理
    path('admin/shop/orders/', admin_views.admin_shop_orders, name='admin_shop_orders'),	
	# AI 助手 API
    path('api/activities/create/', views.api_create_activity, name='api_create_activity'),
    path('api/activities/list/', views.api_list_activities, name='api_list_activities'),
    path('api/activities/update/', views.api_update_activity_compatible, name='api_update_activity_compatible'),
    path('api/activities/<int:activity_id>/update/', views.api_update_activity, name='api_update_activity'),
]


