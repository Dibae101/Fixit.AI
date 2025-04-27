import time
from datetime import datetime
from collections import defaultdict, deque
from rest_framework.response import Response
from rest_framework import status

class WeakRateLimiter:
    """
    A deliberately weak rate limiter that will fail after ~10 requests
    in a short time period. This is designed to be vulnerable to high traffic.
    """
    # Track request timestamps per IP address
    request_history = defaultdict(lambda: deque(maxlen=100))
    
    # Increased threshold to allow more API requests
    MAX_REQUESTS = 50  # Maximum number of requests allowed (increased from 10)
    TIME_WINDOW = 10   # Time window in seconds
    
    @classmethod
    def is_rate_limited(cls, request):
        """
        Check if the request should be rate limited.
        Returns True if the request should be blocked.
        """
        # Don't rate limit internal requests or API response detail views
        path = request.path_info if hasattr(request, 'path_info') else ''
        if 'api-response' in path:
            return False
            
        # Get client IP (or a default value if not available)
        client_ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        current_time = time.time()
        
        # Add current timestamp to the request history
        cls.request_history[client_ip].append(current_time)
        
        # Count requests within the time window
        recent_requests = [
            req_time for req_time in cls.request_history[client_ip]
            if current_time - req_time < cls.TIME_WINDOW
        ]
        
        # More forgiving implementation
        return len(recent_requests) > cls.MAX_REQUESTS
    
    @staticmethod
    def get_rate_limit_response():
        """
        Return a standardized response for rate-limited requests
        """
        return Response(
            {"error": "Too many requests. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )