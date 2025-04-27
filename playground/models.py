from django.db import models
import uuid

class ApiRequest(models.Model):
    """Model to store API request details"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField(max_length=500)
    method = models.CharField(max_length=10)
    headers = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.method} {self.url} ({self.created_at.strftime('%Y-%m-%d %H:%M:%S')})"
    
    class Meta:
        ordering = ['-created_at']


class ApiResponse(models.Model):
    """Model to store API response details"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ApiRequest, on_delete=models.CASCADE, related_name='responses')
    status_code = models.IntegerField()
    response_headers = models.TextField(blank=True, null=True)
    response_body = models.TextField(blank=True, null=True)
    response_time_ms = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Response {self.status_code} for {self.request}"
    
    class Meta:
        ordering = ['-created_at']


class ChaosTest(models.Model):
    """Model to store chaos test configurations"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    
    FAULT_TYPE_CHOICES = [
        ('MISSING_FIELD', 'Missing Required Field'),
        ('AUTH_FAILURE', 'Authentication Failure'),
        ('CORRUPT_PAYLOAD', 'Corrupted JSON Payload'),
        ('TIMEOUT', 'Request Timeout'),
        ('MISSING_DB', 'Missing Database Record'),
        ('INVALID_PARAM', 'Invalid Parameter Value'),
        ('OTHER', 'Other'),
    ]
    
    fault_type = models.CharField(max_length=20, choices=FAULT_TYPE_CHOICES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']


class ChaosTestRun(models.Model):
    """Model to store results of chaos test runs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chaos_test = models.ForeignKey(ChaosTest, on_delete=models.CASCADE, related_name='test_runs')
    original_request = models.ForeignKey(
        ApiRequest, on_delete=models.CASCADE, related_name='original_for_chaos_runs'
    )
    modified_request = models.ForeignKey(
        ApiRequest, on_delete=models.CASCADE, related_name='modified_for_chaos_runs'
    )
    failed_response = models.ForeignKey(
        ApiResponse, on_delete=models.CASCADE, related_name='failure_for_chaos_runs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.chaos_test.name} on {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    class Meta:
        ordering = ['-created_at']


class RootCauseAnalysis(models.Model):
    """
    Model to store AI-generated root cause analysis of failures.
    
    This model captures comprehensive data about system failures and their analyses:
    - Basic information linking to the test run that produced the failure
    - Analysis confidence and severity metrics
    - Detailed breakdown of root causes, analysis, and solutions
    - Categorization and classification data for better organization
    - Metadata for tracking and reporting
    
    Key relationships:
    - Each RCA is linked to exactly one ChaosTestRun that triggered the analysis
    - Multiple RCAs can be generated for a single test run (different analysis approaches)
    
    Usage:
    - Created automatically by the RcaEngine after chaos test failures
    - Used for displaying detailed analysis in the RCA detail view
    - Supports filtering, tagging, and categorization for better organization
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chaos_test_run = models.ForeignKey(
        ChaosTestRun, on_delete=models.CASCADE, related_name='root_cause_analyses', null=True, blank=True
    )
    # New field for linking to direct API responses
    api_response = models.ForeignKey(
        ApiResponse, on_delete=models.CASCADE, related_name='root_cause_analyses', null=True, blank=True
    )
    
    # Analysis quality metrics
    ANALYSIS_CONFIDENCE_CHOICES = [
        ('HIGH', 'High - Strong evidence with high certainty'),
        ('MEDIUM', 'Medium - Reasonable evidence but some uncertainty'),
        ('LOW', 'Low - Limited evidence with significant uncertainty'),
    ]
    confidence = models.CharField(
        max_length=10, 
        choices=ANALYSIS_CONFIDENCE_CHOICES,
        help_text="Confidence level in the accuracy of this analysis"
    )
    
    # Core analysis content
    root_cause = models.TextField(
        help_text="Brief summary of the primary root cause identified"
    )
    detailed_analysis = models.TextField(
        help_text="In-depth explanation of the failure and its causes"
    )
    potential_solutions = models.TextField(
        help_text="Recommended actions to address the root cause"
    )
    
    # Impact and categorization
    SEVERITY_CHOICES = [
        ('CRITICAL', 'Critical - Service outage or data loss'),
        ('HIGH', 'High - Major functionality impaired'),
        ('MEDIUM', 'Medium - Limited functionality impact'),
        ('LOW', 'Low - Minor or cosmetic issues'),
    ]
    impact_severity = models.CharField(
        max_length=10, 
        choices=SEVERITY_CHOICES, 
        default='MEDIUM',
        help_text="Severity of the impact this failure would have in production"
    )
    
    failure_category = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="General category of failure (e.g., 'API Validation', 'Authentication', 'Database')"
    )
    
    # Technical details
    affected_components = models.JSONField(
        default=list, 
        blank=True, 
        null=True,
        help_text="List of system components affected by this failure"
    )
    time_to_detect_ms = models.IntegerField(
        default=0,
        help_text="Time taken to detect the failure in milliseconds"
    )
    
    # Metadata
    tags = models.JSONField(
        default=list, 
        blank=True, 
        null=True,
        help_text="Tags for filtering and grouping RCAs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        if self.chaos_test_run:
            return f"RCA for {self.chaos_test_run} ({self.confidence})"
        elif self.api_response:
            return f"RCA for API Response {self.api_response.status_code} ({self.confidence})"
        return f"RCA ({self.confidence})"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Root cause analyses"
        indexes = [
            models.Index(fields=['failure_category']),
            models.Index(fields=['impact_severity']),
            models.Index(fields=['confidence']),
        ]
        
    def get_summary(self):
        """Returns a short summary of the RCA suitable for display in lists"""
        return f"{self.get_confidence_display()}: {self.root_cause[:100]}..."
        
    def get_affected_components_list(self):
        """Returns the affected components as a formatted list"""
        if not self.affected_components:
            return []
        return self.affected_components


class TodoItem(models.Model):
    """Model for Todo items in our internal REST API"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    completed = models.BooleanField(default=False)
    priority = models.IntegerField(default=1)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Product(models.Model):
    """Model for Products in our internal REST API"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    inventory = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
