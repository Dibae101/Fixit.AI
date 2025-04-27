from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Set up the router for REST API endpoints
router = DefaultRouter()
router.register(r'todos', views.TodoItemViewSet)
router.register(r'products', views.ProductViewSet)

urlpatterns = [
    # Main dashboard
    path('', views.index, name='index'),
    
    # API Tester
    path('api-tester/', views.api_tester, name='api_tester'),
    path('api-response/<uuid:response_id>/', views.api_response_detail, name='api_response_detail'),
    
    # API RCA Generation
    path('generate-api-rca/', views.generate_api_rca, name='generate_api_rca'),
    path('view-api-rca/<uuid:response_id>/', views.view_api_rca, name='view_api_rca'),
    
    # Break the App
    path('break-app/', views.break_app, name='break_app'),
    path('apply-chaos/', views.apply_chaos, name='apply_chaos'),
    path('chaos-test-runs/', views.chaos_test_runs, name='chaos_test_runs'),
    path('chaos-test-run/<uuid:run_id>/', views.chaos_test_run_detail, name='chaos_test_run_detail'),
    
    # RCA Generator
    path('rca-generator/', views.rca_generator, name='rca_generator'),
    path('rca-detail/<uuid:rca_id>/', views.rca_detail, name='rca_detail'),
    
    # REST API
    path('api/', include(router.urls)),
]