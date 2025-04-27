import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone  # Add timezone import
from .models import (
    ApiRequest, ApiResponse, ChaosTest, ChaosTestRun, 
    RootCauseAnalysis, TodoItem, Product
)
from .forms import ApiRequestForm, ChaosTestForm, RcaGenerateForm
from .utils.api_client import ApiClient
from .utils.chaos_injector import ChaosInjector
from .utils.rca_engine import RcaEngine
from .utils.rate_limiter import WeakRateLimiter  # Import the rate limiter
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from .serializers import TodoItemSerializer, ProductSerializer

# The GEMINI_API_KEY should be loaded from environment variables

# Dashboard View
def index(request):
    """Main dashboard view showing overall statistics and recent activity"""
    # Get recent activity
    recent_requests = ApiRequest.objects.all().order_by('-created_at')[:10]
    recent_chaos_runs = ChaosTestRun.objects.all().order_by('-created_at')[:5]
    recent_rcas = RootCauseAnalysis.objects.all().order_by('-created_at')[:5]
    
    # Paginate all requests
    all_requests = ApiRequest.objects.all().order_by('-created_at')
    request_paginator = Paginator(all_requests, 10)
    request_page = request.GET.get('page', 1)
    paginated_requests = request_paginator.get_page(request_page)
    
    # Paginate chaos tests
    all_chaos_tests = ChaosTest.objects.all()
    chaos_paginator = Paginator(all_chaos_tests, 10)
    chaos_page = request.GET.get('chaos_page', 1)
    available_chaos_tests = chaos_paginator.get_page(chaos_page)
    
    # Paginate RCAs
    all_rcas_list = RootCauseAnalysis.objects.all().order_by('-created_at')
    rca_paginator = Paginator(all_rcas_list, 10)
    rca_page = request.GET.get('rca_page', 1)
    all_rcas = rca_paginator.get_page(rca_page)
    
    # Calculate statistics
    api_requests_count = ApiRequest.objects.count()
    chaos_runs_count = ChaosTestRun.objects.count()
    rca_count = RootCauseAnalysis.objects.count()
    
    # Calculate percentages for progress bars
    # These are placeholder calculations, you might want to adjust based on your business logic
    api_requests_count_percentage = min(100, api_requests_count)
    chaos_runs_percentage = min(100, chaos_runs_count)
    rca_percentage = min(100, rca_count)
    
    # Calculate success rate
    successful_responses = ApiResponse.objects.filter(status_code__gte=200, status_code__lt=400).count()
    total_responses = ApiResponse.objects.count()
    api_success_rate = int((successful_responses / total_responses) * 100) if total_responses > 0 else 0
    
    # Calculate recent chaos tests
    recent_chaos_tests = ChaosTestRun.objects.filter(created_at__gte=timezone.now() - timezone.timedelta(hours=24)).count()
    
    # Count fixed issues - since there's no 'status' field, we'll count those with 'HIGH' confidence as fixed
    fixed_issues_count = RootCauseAnalysis.objects.filter(confidence='HIGH').count()
    
    context = {
        'recent_requests': recent_requests,
        'recent_chaos_runs': recent_chaos_runs,
        'recent_rcas': recent_rcas,
        'all_requests': paginated_requests,
        'available_chaos_tests': available_chaos_tests,
        'all_rcas': all_rcas,
        
        # Stats for cards
        'api_requests_count': api_requests_count,
        'api_requests_count_percentage': api_requests_count_percentage,
        'api_success_rate': api_success_rate,
        'chaos_runs_count': chaos_runs_count,
        'chaos_runs_percentage': chaos_runs_percentage,
        'recent_chaos_tests': recent_chaos_tests,
        'rca_count': rca_count,
        'rca_percentage': rca_percentage,
        'fixed_issues_count': fixed_issues_count,
    }
    
    return render(request, 'playground/index.html', context)

# API Tester Views
def api_tester(request):
    """View for testing APIs"""
    if request.method == 'POST':
        form = ApiRequestForm(request.POST)
        if form.is_valid():
            # Create ApiRequest object
            api_request = ApiRequest.objects.create(
                url=form.cleaned_data['url'],
                method=form.cleaned_data['method'],
                headers=form.cleaned_data['headers'],
                body=form.cleaned_data['body']
            )
            
            # Execute the request
            api_response = ApiClient.execute_request(api_request)
            
            # Check if the response status code indicates a failure
            if api_response.status_code < 200 or api_response.status_code >= 300:
                # Automatically generate RCA for non-successful responses
                try:
                    rca = RcaEngine.generate_rca(api_response=api_response)
                    messages.info(request, f'API request returned status code {api_response.status_code}. Root Cause Analysis was automatically generated.')
                except Exception as e:
                    messages.warning(request, f'API request returned status code {api_response.status_code}. Failed to auto-generate RCA: {str(e)}')
            else:
                messages.success(request, f'API request sent successfully! Status code: {api_response.status_code}')
            
            # Redirect to response detail
            return redirect('api_response_detail', response_id=api_response.id)
    else:
        form = ApiRequestForm()
    
    # Get recent responses for history panel
    recent_responses = ApiResponse.objects.all().order_by('-created_at')[:10]
    
    context = {
        'form': form,
        'recent_responses': recent_responses,
    }
    
    return render(request, 'playground/api_tester.html', context)

def api_response_detail(request, response_id):
    """View for displaying API response details"""
    try:
        api_response = get_object_or_404(ApiResponse, id=response_id)
        api_request = api_response.request
        
        # Format response body if it's JSON
        try:
            if api_response.response_body:
                # Check if the response body starts with a JSON structure
                if (api_response.response_body.strip().startswith('{') or 
                    api_response.response_body.strip().startswith('[')):
                    json_body = json.loads(api_response.response_body)
                    formatted_response = json.dumps(json_body, indent=2)
                else:
                    formatted_response = api_response.response_body
            else:
                formatted_response = ''
        except json.JSONDecodeError:
            formatted_response = api_response.response_body
        except Exception as e:
            formatted_response = f"Error parsing response: {str(e)}"
        
        # Format request body if it's JSON
        try:
            if api_request.body:
                # Check if the request body starts with a JSON structure
                if (api_request.body.strip().startswith('{') or 
                    api_request.body.strip().startswith('[')):
                    json_body = json.loads(api_request.body)
                    formatted_request_body = json.dumps(json_body, indent=2)
                else:
                    formatted_request_body = api_request.body
            else:
                formatted_request_body = ''
        except json.JSONDecodeError:
            formatted_request_body = api_request.body
        except Exception as e:
            formatted_request_body = f"Error parsing request body: {str(e)}"
        
        # Check if this response already has an RCA
        has_rca = RootCauseAnalysis.objects.filter(api_response=api_response).exists()
        
        context = {
            'api_response': api_response,
            'api_request': api_request,
            'formatted_response': formatted_response,
            'formatted_request_body': formatted_request_body,
            'has_rca': has_rca,
        }
        
        # If it has an RCA, include it in the context
        if has_rca:
            try:
                rca = RootCauseAnalysis.objects.get(api_response=api_response)
                context['rca'] = rca
            except RootCauseAnalysis.DoesNotExist:
                # This shouldn't happen based on the has_rca check, but just in case
                pass
            except Exception as e:
                messages.error(request, f"Error loading RCA: {str(e)}")
        
        return render(request, 'playground/api_response_detail.html', context)
    
    except Exception as e:
        # Log the exception for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in api_response_detail view: {str(e)}")
        
        # Show a user-friendly error message
        messages.error(request, f"An error occurred while loading the API response: {str(e)}")
        return redirect('api_tester')

def generate_api_rca(request):
    """View for generating RCA for a failed API response"""
    if request.method == 'POST':
        response_id = request.POST.get('response_id')
        
        if not response_id:
            messages.error(request, 'No API response selected for analysis.')
            return redirect('api_tester')
        
        try:
            # Get the API response
            api_response = ApiResponse.objects.get(id=response_id)
            
            # Check if RCA already exists
            if RootCauseAnalysis.objects.filter(api_response=api_response).exists():
                rca = RootCauseAnalysis.objects.get(api_response=api_response)
                messages.info(request, 'An RCA already exists for this API response.')
            else:
                # Generate RCA using the enhanced RcaEngine
                try:
                    rca = RcaEngine.generate_rca(api_response=api_response)
                    messages.success(request, 'Root Cause Analysis for API failure generated successfully!')
                except Exception as e:
                    messages.error(request, f'Error generating RCA: {str(e)}')
                    return redirect('api_response_detail', response_id=response_id)
            
            # Redirect to the API response detail with the RCA included
            return redirect('api_response_detail', response_id=api_response.id)
            
        except ApiResponse.DoesNotExist:
            messages.error(request, 'API response not found.')
            return redirect('api_tester')
        except Exception as e:
            messages.error(request, f'Error generating RCA: {str(e)}')
            return redirect('api_tester')
    
    # If not POST, redirect to the API tester
    return redirect('api_tester')

def view_api_rca(request, response_id):
    """View for displaying RCA for an API response"""
    api_response = get_object_or_404(ApiResponse, id=response_id)
    rca = get_object_or_404(RootCauseAnalysis, api_response=api_response)
    
    # Get related RCAs with similar failure type
    related_rcas = RootCauseAnalysis.objects.filter(
        failure_category=rca.failure_category
    ).exclude(id=rca.id).order_by('-created_at')[:3]
    
    # Get failure categories for analytics
    categories = RootCauseAnalysis.objects.exclude(failure_category__isnull=True).values_list('failure_category', flat=True).distinct()
    
    context = {
        'rca': rca,
        'api_response': api_response,
        'related_rcas': related_rcas,
        'failure_categories': list(categories),
    }
    
    return render(request, 'playground/rca_detail.html', context)

# Break the App Views
def break_app(request):
    """View for showing chaos test dashboard"""
    # Get or create chaos tests
    if ChaosTest.objects.count() == 0:
        # Create some default chaos tests if none exist
        default_tests = [
            {
                'name': 'Missing Required Field',
                'fault_type': 'MISSING_FIELD',
                'description': 'Removes a required field from the request body'
            },
            {
                'name': 'Authentication Failure',
                'fault_type': 'AUTH_FAILURE',
                'description': 'Removes or invalidates authentication tokens'
            },
            {
                'name': 'Corrupted JSON Payload',
                'fault_type': 'CORRUPT_PAYLOAD',
                'description': 'Corrupts the JSON payload to make it invalid'
            },
            {
                'name': 'Request Timeout',
                'fault_type': 'TIMEOUT',
                'description': 'Simulates a request timeout'
            },
            {
                'name': 'Missing Database Record',
                'fault_type': 'MISSING_DB',
                'description': 'Modifies the URL to request a non-existent record'
            },
        ]
        
        for test in default_tests:
            ChaosTest.objects.create(**test)
    
    # Handle form for creating new chaos test
    if request.method == 'POST':
        form = ChaosTestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'New chaos test created successfully!')
            return redirect('break_app')
    else:
        form = ChaosTestForm()
    
    # Get API requests for selection
    api_requests = ApiRequest.objects.all().order_by('-created_at')[:20]
    
    # Get chaos tests
    chaos_tests = ChaosTest.objects.all()
    
    # Get recent chaos test runs
    recent_runs = ChaosTestRun.objects.all().order_by('-created_at')[:10]
    
    context = {
        'form': form,
        'api_requests': api_requests,
        'chaos_tests': chaos_tests,
        'recent_runs': recent_runs,
    }
    
    return render(request, 'playground/break_app.html', context)

def apply_chaos(request):
    """View for applying a chaos test to an API request"""
    if request.method == 'POST':
        request_id = request.POST.get('request_id')
        test_id = request.POST.get('test_id')
        
        if not request_id or not test_id:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Please select both an API request and a chaos test.'}, status=400)
            messages.error(request, 'Please select both an API request and a chaos test.')
            return redirect('break_app')
        
        try:
            # Get the original request and chaos test
            original_request = ApiRequest.objects.get(id=request_id)
            chaos_test = ChaosTest.objects.get(id=test_id)
            
            # Apply chaos injection
            test_run = ChaosInjector.inject_chaos(original_request, chaos_test)
            failed_response = test_run.failed_response
            
            # Return JSON response for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Chaos test "{chaos_test.name}" applied successfully!',
                    'status_code': failed_response.status_code,
                    'test_run_id': str(test_run.id)
                })
            
            messages.success(
                request, 
                f'Chaos test "{chaos_test.name}" applied successfully! Status code: {failed_response.status_code}'
            )
            
            # Redirect to the chaos test run detail
            return redirect('chaos_test_run_detail', run_id=test_run.id)
            
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': str(e)}, status=500)
            messages.error(request, f'Error applying chaos test: {str(e)}')
            return redirect('break_app')
    
    # If not POST, redirect to the break_app view
    return redirect('break_app')

def chaos_test_runs(request):
    """View for listing all chaos test runs"""
    runs = ChaosTestRun.objects.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(runs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'playground/chaos_test_runs.html', context)

def chaos_test_run_detail(request, run_id):
    """View for displaying chaos test run details"""
    run = get_object_or_404(ChaosTestRun, id=run_id)
    
    # Check if this run already has an RCA
    has_rca = RootCauseAnalysis.objects.filter(chaos_test_run=run).exists()
    
    context = {
        'run': run,
        'has_rca': has_rca,
    }
    
    # If it has an RCA, include it in the context
    if has_rca:
        rca = RootCauseAnalysis.objects.get(chaos_test_run=run)
        context['rca'] = rca
    
    return render(request, 'playground/chaos_test_run_detail.html', context)

# RCA Generator Views
def rca_generator(request):
    """View for generating RCA from chaos test runs"""
    try:
        if request.method == 'POST':
            form = RcaGenerateForm(request.POST)
            if form.is_valid():
                chaos_test_run = form.cleaned_data['chaos_test_run']
                
                # Check if RCA already exists
                if RootCauseAnalysis.objects.filter(chaos_test_run=chaos_test_run).exists():
                    rca = RootCauseAnalysis.objects.get(chaos_test_run=chaos_test_run)
                    messages.info(request, 'An RCA already exists for this test run.')
                else:
                    # Generate RCA
                    try:
                        rca = RcaEngine.generate_rca(chaos_test_run)
                        messages.success(request, 'Root Cause Analysis generated successfully!')
                    except Exception as e:
                        # Log the exception for debugging
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error in RCA generation: {str(e)}")
                        
                        messages.error(request, f'Error generating RCA: {str(e)}')
                        return redirect('rca_generator')
                
                # Redirect to RCA detail
                return redirect('rca_detail', rca_id=rca.id)
            else:
                # Form validation failed
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        else:
            form = RcaGenerateForm()
        
        # Get recent RCAs
        rcas = RootCauseAnalysis.objects.all().order_by('-created_at')[:10]
        
        context = {
            'form': form,
            'rcas': rcas,
        }
        
        return render(request, 'playground/rca_generator.html', context)
        
    except Exception as e:
        # Log the exception for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Uncaught error in rca_generator view: {str(e)}")
        
        # Show a user-friendly error message
        messages.error(request, f"An unexpected error occurred: {str(e)}")
        
        # Create an empty form for the template
        form = RcaGenerateForm()
        
        # Get recent RCAs (if possible)
        try:
            rcas = RootCauseAnalysis.objects.all().order_by('-created_at')[:10]
        except Exception:
            rcas = []
        
        context = {
            'form': form,
            'rcas': rcas,
        }
        
        return render(request, 'playground/rca_generator.html', context)

def rca_detail(request, rca_id):
    """View for displaying RCA details"""
    rca = get_object_or_404(RootCauseAnalysis, id=rca_id)
    
    # Get failure categories for analytics
    categories = RootCauseAnalysis.objects.exclude(failure_category__isnull=True).values_list('failure_category', flat=True).distinct()
    
    # Get related RCAs with similar failure type
    if rca.failure_category:
        related_rcas = RootCauseAnalysis.objects.filter(
            failure_category=rca.failure_category
        ).exclude(id=rca.id).order_by('-created_at')[:3]
    elif rca.chaos_test_run:
        # Fallback to chaos test type if no failure category
        related_rcas = RootCauseAnalysis.objects.filter(
            chaos_test_run__chaos_test__fault_type=rca.chaos_test_run.chaos_test.fault_type
        ).exclude(id=rca.id).order_by('-created_at')[:3]
    else:
        # No good way to relate, just get recent ones
        related_rcas = RootCauseAnalysis.objects.exclude(id=rca.id).order_by('-created_at')[:3]
    
    context = {
        'rca': rca,
        'related_rcas': related_rcas,
        'failure_categories': list(categories),
    }
    
    # Add source-specific context
    if rca.chaos_test_run:
        context['chaos_test_run'] = rca.chaos_test_run
        context['source_type'] = 'chaos_test'
    elif rca.api_response:
        context['api_response'] = rca.api_response
        context['source_type'] = 'api_response'
    
    return render(request, 'playground/rca_detail.html', context)

# Internal REST API Views
class TodoItemViewSet(viewsets.ModelViewSet):
    """ViewSet for TodoItem CRUD operations"""
    queryset = TodoItem.objects.all().order_by('-created_at')
    serializer_class = TodoItemSerializer

    def dispatch(self, request, *args, **kwargs):
        # Apply weak rate limiting to all TodoItem API endpoints
        if WeakRateLimiter.is_rate_limited(request):
            return WeakRateLimiter.get_rate_limit_response()
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            # Log the exception for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in TodoItemViewSet: {str(e)}")
            
            # Return a 500 error with a helpful message
            return Response(
                {"error": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['delete'])
    def delete_completed(self, request):
        """Delete all completed todos"""
        try:
            # Check rate limiting again for this specific action
            if WeakRateLimiter.is_rate_limited(request):
                return WeakRateLimiter.get_rate_limit_response()
                
            deleted_count = TodoItem.objects.filter(completed=True).delete()[0]
            return Response({
                "message": f"Deleted {deleted_count} completed todo items",
                "deleted_count": deleted_count
            })
        except Exception as e:
            return Response(
                {"error": f"Failed to delete completed todos: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for Product CRUD operations"""
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer

    def dispatch(self, request, *args, **kwargs):
        # Apply weak rate limiting to all Product API endpoints
        if WeakRateLimiter.is_rate_limited(request):
            return WeakRateLimiter.get_rate_limit_response()
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            # Log the exception for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in ProductViewSet: {str(e)}")
            
            # Return a 500 error with a helpful message
            return Response(
                {"error": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get only available products"""
        try:
            # Check rate limiting again for this specific action
            if WeakRateLimiter.is_rate_limited(request):
                return WeakRateLimiter.get_rate_limit_response()
                
            available_products = Product.objects.filter(is_available=True)
            serializer = self.get_serializer(available_products, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve available products: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def update_inventory(self, request, pk=None):
        """Update product inventory"""
        try:
            # Check rate limiting again for this specific action
            if WeakRateLimiter.is_rate_limited(request):
                return WeakRateLimiter.get_rate_limit_response()
                
            product = self.get_object()
            try:
                quantity = int(request.data.get('quantity', 0))
                if quantity < 0 and abs(quantity) > product.inventory:
                    return Response({
                        "error": f"Cannot reduce inventory by {abs(quantity)}. Only {product.inventory} items in stock"
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                product.inventory += quantity
                product.save()
                
                return Response({
                    "message": f"Inventory updated successfully. New inventory: {product.inventory}",
                    "inventory": product.inventory
                })
            except ValueError:
                return Response({
                    "error": "Quantity must be a valid integer"
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to update inventory: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
