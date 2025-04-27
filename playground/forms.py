from django import forms
from .models import ChaosTest, ChaosTestRun, RootCauseAnalysis

class ApiRequestForm(forms.Form):
    """Form for creating and validating API requests"""
    url = forms.URLField(
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://api.example.com/endpoint'}),
        help_text="The URL to send the request to"
    )
    
    METHOD_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
    ]
    
    method = forms.ChoiceField(
        choices=METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="The HTTP method to use"
    )
    
    headers = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': '{"Content-Type": "application/json", "Authorization": "Bearer token"}',
            'rows': 3
        }),
        help_text="Request headers as JSON (optional)",
        required=False
    )
    
    body = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': '{"key": "value"}',
            'rows': 6
        }),
        help_text="Request body as JSON (optional)",
        required=False
    )
    
    def clean_headers(self):
        """Validate that headers are valid JSON if provided"""
        headers = self.cleaned_data.get('headers')
        if headers:
            try:
                import json
                json.loads(headers)
            except json.JSONDecodeError:
                raise forms.ValidationError("Headers must be valid JSON")
        return headers
    
    def clean_body(self):
        """Validate that body is valid JSON if provided"""
        body = self.cleaned_data.get('body')
        if body:
            try:
                import json
                json.loads(body)
            except json.JSONDecodeError:
                raise forms.ValidationError("Body must be valid JSON")
        return body


class ChaosTestForm(forms.ModelForm):
    """Form for creating chaos tests"""
    class Meta:
        model = ChaosTest
        fields = ['name', 'fault_type', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'fault_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class RcaGenerateForm(forms.Form):
    """Form for generating RCA from chaos test runs"""
    chaos_test_run = forms.ModelChoiceField(
        queryset=ChaosTestRun.objects.all().order_by('-created_at'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Select a failed chaos test run to analyze"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Update the queryset to show only runs without RCAs
        existing_rcas = RootCauseAnalysis.objects.values_list('chaos_test_run', flat=True)
        self.fields['chaos_test_run'].queryset = ChaosTestRun.objects.exclude(
            id__in=existing_rcas
        ).order_by('-created_at')