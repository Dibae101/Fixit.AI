import json
import random
import logging
from django.utils import timezone
from ..models import ApiRequest, ChaosTestRun
from .api_client import ApiClient

logger = logging.getLogger(__name__)

class ChaosInjector:
    """Utility for simulating API failures and errors"""
    
    @staticmethod
    def run_chaos_test(chaos_test_run):
        """
        Execute a chaos test run with API requests that have various error conditions
        
        Args:
            chaos_test_run (ChaosTestRun): The chaos test run to execute
            
        Returns:
            bool: True if the test completed successfully
        """
        try:
            if not chaos_test_run:
                logger.error("Cannot run chaos test: No chaos test run provided")
                return False
                
            logger.info(f"Starting chaos test run '{chaos_test_run.name}'")
            
            # Update test run status
            chaos_test_run.start_time = timezone.now()
            chaos_test_run.status = 'IN_PROGRESS'
            chaos_test_run.save()
            
            # Generate and execute requests for each chaos type
            try:
                ChaosInjector._generate_malformed_json_requests(chaos_test_run)
                ChaosInjector._generate_invalid_param_requests(chaos_test_run)
                ChaosInjector._generate_timeout_requests(chaos_test_run)
                ChaosInjector._generate_rate_limit_requests(chaos_test_run)
                ChaosInjector._generate_data_validation_requests(chaos_test_run)
            except Exception as e:
                logger.error(f"Error during chaos test run: {str(e)}")
                chaos_test_run.status = 'FAILED'
                chaos_test_run.end_time = timezone.now()
                chaos_test_run.save()
                return False
            
            # Complete the test run
            chaos_test_run.status = 'COMPLETED'
            chaos_test_run.end_time = timezone.now()
            chaos_test_run.save()
            
            logger.info(f"Completed chaos test run '{chaos_test_run.name}'")
            return True
        
        except Exception as e:
            logger.error(f"Error in run_chaos_test: {str(e)}")
            
            # Update test run status if possible
            if chaos_test_run:
                chaos_test_run.status = 'FAILED'
                chaos_test_run.end_time = timezone.now()
                chaos_test_run.save()
            
            return False
    
    @staticmethod
    def _generate_malformed_json_requests(chaos_test_run):
        """Generate API requests with malformed JSON body"""
        base_url = chaos_test_run.base_url
        
        if not base_url:
            base_url = "https://httpbin.org/post"  # Default fallback
        
        # Ensure base URL ends with proper path if needed
        if base_url.endswith('/'):
            base_url = base_url[:-1]
            
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url
            
        malformed_json_cases = [
            {
                "description": "Missing closing brace",
                "body": '{"key": "value"',
                "headers": json.dumps({"Content-Type": "application/json"})
            },
            {
                "description": "Invalid JSON with unquoted property",
                "body": '{key: "value"}',
                "headers": json.dumps({"Content-Type": "application/json"})
            },
            {
                "description": "Trailing comma in JSON object",
                "body": '{"key": "value",}',
                "headers": json.dumps({"Content-Type": "application/json"})
            }
        ]
        
        for case in malformed_json_cases:
            # Create request
            request = ApiRequest.objects.create(
                chaos_test_run=chaos_test_run,
                url=f"{base_url}/test-json",
                method="POST",
                headers=case["headers"],
                body=case["body"],
                description=f"Malformed JSON test: {case['description']}"
            )
            
            # Execute request
            ApiClient.execute_request(request)
    
    @staticmethod
    def _generate_invalid_param_requests(chaos_test_run):
        """Generate API requests with invalid parameters"""
        base_url = chaos_test_run.base_url
        
        if not base_url:
            base_url = "https://httpbin.org/get"  # Default fallback
        
        # Ensure base URL ends with proper path if needed
        if base_url.endswith('/'):
            base_url = base_url[:-1]
            
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url
            
        invalid_param_cases = [
            {
                "description": "Invalid parameter type (string instead of number)",
                "url_suffix": "?id=abc",
                "expected_error": "Parameter 'id' must be a number"
            },
            {
                "description": "Missing required parameter",
                "url_suffix": "",
                "expected_error": "Missing required parameter"
            },
            {
                "description": "Parameter value out of range",
                "url_suffix": "?limit=1000000",
                "expected_error": "Parameter 'limit' out of range"
            }
        ]
        
        for case in invalid_param_cases:
            # Create request
            request = ApiRequest.objects.create(
                chaos_test_run=chaos_test_run,
                url=f"{base_url}/test-params{case['url_suffix']}",
                method="GET",
                headers=json.dumps({"Content-Type": "application/json"}),
                description=f"Invalid parameter test: {case['description']}"
            )
            
            # Execute request
            ApiClient.execute_request(request)
    
    @staticmethod
    def _generate_timeout_requests(chaos_test_run):
        """Generate API requests that should timeout"""
        base_url = chaos_test_run.base_url
        
        if not base_url:
            base_url = "https://httpbin.org/delay"  # Default fallback
        
        # Ensure base URL ends with proper path if needed
        if base_url.endswith('/'):
            base_url = base_url[:-1]
            
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url
            
        # Create request with expected timeout (using httpbin.org/delay/15 which waits 15 seconds)
        request = ApiRequest.objects.create(
            chaos_test_run=chaos_test_run,
            url=f"{base_url}/test-timeout",
            method="GET",
            headers=json.dumps({"Content-Type": "application/json"}),
            description="Request expected to timeout"
        )
        
        # Execute request (should timeout based on client timeout setting)
        ApiClient.execute_request(request)
    
    @staticmethod
    def _generate_rate_limit_requests(chaos_test_run):
        """Generate API requests that should trigger rate limiting"""
        base_url = chaos_test_run.base_url
        
        if not base_url:
            base_url = "https://httpbin.org/get"  # Default fallback
        
        # Ensure base URL ends with proper path if needed
        if base_url.endswith('/'):
            base_url = base_url[:-1]
            
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url
            
        # Create multiple requests in rapid succession
        for i in range(10):
            request = ApiRequest.objects.create(
                chaos_test_run=chaos_test_run,
                url=f"{base_url}/test-rate-limit?request={i}",
                method="GET",
                headers=json.dumps({"Content-Type": "application/json"}),
                description=f"Rate limit test request #{i+1}"
            )
            
            # Execute request - should eventually trigger rate limiting on many APIs
            ApiClient.execute_request(request)
    
    @staticmethod
    def _generate_data_validation_requests(chaos_test_run):
        """Generate API requests with data validation issues"""
        base_url = chaos_test_run.base_url
        
        if not base_url:
            base_url = "https://httpbin.org/post"  # Default fallback
        
        # Ensure base URL ends with proper path if needed
        if base_url.endswith('/'):
            base_url = base_url[:-1]
            
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url
            
        validation_cases = [
            {
                "description": "Missing required field",
                "body": json.dumps({"optional_field": "value"}),
                "expected_error": "Missing required field"
            },
            {
                "description": "Invalid email format",
                "body": json.dumps({"email": "not-an-email"}),
                "expected_error": "Invalid email format"
            },
            {
                "description": "Value exceeds maximum length",
                "body": json.dumps({"name": "a" * 1000}),
                "expected_error": "Value exceeds maximum length"
            }
        ]
        
        for case in validation_cases:
            # Create request
            request = ApiRequest.objects.create(
                chaos_test_run=chaos_test_run,
                url=f"{base_url}/test-validation",
                method="POST",
                headers=json.dumps({"Content-Type": "application/json"}),
                body=case["body"],
                description=f"Data validation test: {case['description']}"
            )
            
            # Execute request
            ApiClient.execute_request(request)