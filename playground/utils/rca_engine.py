import json
import os
import requests
from django.conf import settings
from ..models import RootCauseAnalysis
import time
import re
import logging

logger = logging.getLogger(__name__)

class RcaEngine:
    """
    Root Cause Analysis Engine that uses Gemini to analyze API failures.
    
    This engine performs detailed analysis of failures detected during chaos testing:
    - Extracts contextual information from the chaos test run
    - Formats the data for processing by the Gemini AI model
    - Processes the AI response into structured RCA data
    - Creates and returns a comprehensive RootCauseAnalysis record
    
    The engine includes fallback mechanisms for error handling and supports
    different confidence levels based on the quality of available data.
    """
    
    # Updated to use a more reliable model
    GEMINI_MODEL = "gemini-pro"
    
    @classmethod
    def generate_rca(cls, chaos_test_run=None, api_response=None):
        """
        Generate a Root Cause Analysis for a failed API request.
        
        This method orchestrates the RCA generation process by:
        1. Building context from the test run data or direct API response
        2. Calling the Gemini API with structured prompts
        3. Processing the AI response into structured data
        4. Creating and returning a RootCauseAnalysis record
        
        Args:
            chaos_test_run: ChaosTestRun model instance (optional)
            api_response: ApiResponse model instance (optional)
            
        Returns:
            RootCauseAnalysis model instance with complete analysis data
            
        Note:
            At least one of chaos_test_run or api_response must be provided.
            If both are provided, chaos_test_run takes precedence.
        """
        if not chaos_test_run and not api_response:
            raise ValueError("Either chaos_test_run or api_response must be provided")
        
        start_time = time.time()
        
        try:
            # Extract data based on what's provided
            if chaos_test_run:
                context = cls._build_context_from_chaos_run(chaos_test_run)
            else:
                context = cls._build_context_from_api_response(api_response)
            
            # Generate RCA using Gemini
            try:
                # First try with the API
                rca_data = cls._call_gemini_api(context)
            except Exception as e:
                logger.error(f"Error calling Gemini API: {str(e)}")
                # Fall back to local analysis
                rca_data = cls._generate_fallback_analysis(context)
            
            # Calculate time to detect
            time_to_detect = int((time.time() - start_time) * 1000)
            
            # Create the RCA record with enhanced data
            rca_kwargs = {
                'confidence': rca_data.get('confidence', 'MEDIUM'),
                'root_cause': rca_data['root_cause'],
                'detailed_analysis': rca_data['detailed_analysis'],
                'potential_solutions': json.dumps(rca_data['potential_solutions']),  # Convert list to JSON string
                'impact_severity': rca_data.get('impact_severity', 'MEDIUM'),
                'failure_category': rca_data.get('failure_category', None),
                'affected_components': rca_data.get('affected_components', []),
                'time_to_detect_ms': time_to_detect,
                'tags': rca_data.get('tags', []),
            }
            
            # Set the appropriate relation
            if chaos_test_run:
                rca_kwargs['chaos_test_run'] = chaos_test_run
            else:
                rca_kwargs['api_response'] = api_response
            
            rca = RootCauseAnalysis.objects.create(**rca_kwargs)
            
            return rca
            
        except Exception as e:
            # Handle errors gracefully
            error_msg = str(e)
            logger.error(f"Error in generate_rca: {error_msg}")
            time_to_detect = int((time.time() - start_time) * 1000)
            
            # Create a more detailed fallback analysis
            detailed_analysis = f"Analysis failed with error: {error_msg}\n\n"
            
            # Add context information to help troubleshoot
            try:
                if chaos_test_run:
                    chaos_test = chaos_test_run.chaos_test
                    fault_type = chaos_test.fault_type
                    
                    # Add fault-specific analysis
                    if fault_type == 'MISSING_FIELD':
                        detailed_analysis += "The API failure was likely caused by a required field missing from the request."
                    elif fault_type == 'AUTH_FAILURE':
                        detailed_analysis += "The API failure appears to be related to authentication issues."
                    elif fault_type == 'CORRUPT_PAYLOAD':
                        detailed_analysis += "The API failure was likely caused by malformed or corrupt data in the request payload."
                    elif fault_type == 'TIMEOUT':
                        detailed_analysis += "The API failure was caused by a timeout, indicating potential performance issues."
                    elif fault_type == 'MISSING_DB':
                        detailed_analysis += "The API failure appears to be related to database connectivity or availability issues."
                    elif fault_type == 'INVALID_PARAM':
                        detailed_analysis += "The API failure was likely caused by one or more invalid parameters in the request."
                    else:
                        detailed_analysis += f"The API failure of type '{fault_type}' requires further investigation."
                    
                    # Add request-specific information
                    if hasattr(chaos_test_run, 'modified_request') and chaos_test_run.modified_request:
                        modified_request = chaos_test_run.modified_request
                        detailed_analysis += f"\n\nThe failed request was sent to {modified_request.url} using {modified_request.method} method."
                    
                    # Add response information if available
                    if hasattr(chaos_test_run, 'failed_response') and chaos_test_run.failed_response:
                        response = chaos_test_run.failed_response
                        detailed_analysis += f"\n\nThe response had status code {response.status_code} with response time of {response.response_time_ms}ms."
                
                elif api_response:
                    # Get failure info from the API response
                    request = api_response.request
                    status_code = api_response.status_code
                    
                    # Base analysis on status code
                    if 400 <= status_code < 500:
                        detailed_analysis += f"The API failure resulted in a {status_code} client error, indicating an issue with the request format or parameters."
                    elif 500 <= status_code < 600:
                        detailed_analysis += f"The API failure resulted in a {status_code} server error, indicating an issue with the API server or backend services."
                    else:
                        detailed_analysis += f"The API failure resulted in an unexpected status code {status_code}."
                    
                    # Add request-specific information
                    detailed_analysis += f"\n\nThe failed request was sent to {request.url} using {request.method} method."
                    
                    # Add response information
                    detailed_analysis += f"\n\nThe response had status code {status_code} with response time of {api_response.response_time_ms}ms."
            
            except Exception as context_error:
                # If we can't extract context info, just use a simpler analysis
                logger.error(f"Error extracting context for fallback analysis: {str(context_error)}")
                detailed_analysis += "Unable to extract additional context information for analysis."
            
            # Create a fallback RCA with the more detailed analysis
            rca_kwargs = {
                'confidence': 'LOW',
                'root_cause': f"Error generating RCA: {error_msg}",
                'detailed_analysis': detailed_analysis,
                'potential_solutions': json.dumps([
                    "Check API key configuration and connectivity to the Gemini API.", 
                    "If the issue persists, examine the request/response data for format issues."
                ]),  # Convert list to JSON string
                'impact_severity': 'LOW',
                'failure_category': 'ERROR',
                'time_to_detect_ms': time_to_detect,
                'tags': ['error', 'analysis_failure'],
            }
            
            # Set the appropriate relation
            if chaos_test_run:
                rca_kwargs['chaos_test_run'] = chaos_test_run
            else:
                rca_kwargs['api_response'] = api_response
                
            rca = RootCauseAnalysis.objects.create(**rca_kwargs)
            
            return rca
    
    @classmethod
    def _build_context_from_chaos_run(cls, chaos_test_run):
        """
        Build the context for the Gemini API from a chaos test run.
        
        Extracts and structures all relevant data from the chaos test run
        to provide sufficient context for accurate analysis.
        
        Args:
            chaos_test_run: ChaosTestRun model instance
            
        Returns:
            dict: Structured context dictionary with test and request/response data
        """
        # Basic information
        chaos_test = chaos_test_run.chaos_test
        original_request = chaos_test_run.original_request
        modified_request = chaos_test_run.modified_request
        failed_response = chaos_test_run.failed_response
        
        # Format request bodies for comparison - with error handling
        try:
            original_body = json.loads(original_request.body) if original_request.body and original_request.body.strip() else {}
        except json.JSONDecodeError:
            original_body = original_request.body if original_request.body else ""
        
        try:
            modified_body = json.loads(modified_request.body) if modified_request.body and modified_request.body.strip() else {}
        except json.JSONDecodeError:
            modified_body = modified_request.body if modified_request.body else ""
        
        # Format headers for comparison - with error handling
        try:
            original_headers = json.loads(original_request.headers) if original_request.headers and original_request.headers.strip() else {}
        except json.JSONDecodeError:
            original_headers = original_request.headers if original_request.headers else ""
        
        try:
            modified_headers = json.loads(modified_request.headers) if modified_request.headers and modified_request.headers.strip() else {}
        except json.JSONDecodeError:
            modified_headers = modified_request.headers if modified_request.headers else ""
        
        # Safe processing of response data
        try:
            response_headers = json.loads(failed_response.response_headers) if failed_response.response_headers and failed_response.response_headers.strip() else {}
        except (json.JSONDecodeError, AttributeError):
            response_headers = "Could not parse headers"
        
        try:
            response_body = failed_response.response_body if failed_response.response_body else ""
            # If response body is very large, truncate it
            if isinstance(response_body, str) and len(response_body) > 10000:
                response_body = response_body[:10000] + "... [truncated]"
        except AttributeError:
            response_body = "No response body"
        
        # Context dictionary
        context = {
            "source_type": "chaos_test",
            "chaos_test": {
                "name": chaos_test.name,
                "fault_type": chaos_test.fault_type,
                "description": chaos_test.description
            },
            "original_request": {
                "url": original_request.url,
                "method": original_request.method,
                "headers": original_headers,
                "body": original_body
            },
            "modified_request": {
                "url": modified_request.url,
                "method": modified_request.method,
                "headers": modified_headers,
                "body": modified_body
            },
            "failed_response": {
                "status_code": failed_response.status_code,
                "headers": response_headers,
                "body": response_body,
                "response_time_ms": failed_response.response_time_ms
            }
        }
        
        return context
    
    @classmethod
    def _build_context_from_api_response(cls, api_response):
        """
        Build the context for the Gemini API from a direct API response.
        
        Extracts and structures all relevant data from the API response
        to provide sufficient context for accurate analysis.
        
        Args:
            api_response: ApiResponse model instance
            
        Returns:
            dict: Structured context dictionary with request/response data
        """
        # Get the request associated with this response
        request = api_response.request
        
        # Format request body - with error handling
        try:
            request_body = json.loads(request.body) if request.body and request.body.strip() else {}
        except json.JSONDecodeError:
            request_body = request.body if request.body else ""
        
        # Format headers - with error handling
        try:
            request_headers = json.loads(request.headers) if request.headers and request.headers.strip() else {}
        except json.JSONDecodeError:
            request_headers = request.headers if request.headers else ""
            
        # Format response headers - with error handling
        try:
            response_headers = json.loads(api_response.response_headers) if api_response.response_headers and api_response.response_headers.strip() else {}
        except json.JSONDecodeError:
            response_headers = api_response.response_headers if api_response.response_headers else ""
        
        # Format response body - with error handling
        try:
            if api_response.response_body and api_response.response_body.strip():
                if api_response.response_body.strip().startswith('{') or api_response.response_body.strip().startswith('['):
                    try:
                        response_body = json.loads(api_response.response_body)
                    except json.JSONDecodeError:
                        response_body = api_response.response_body
                else:
                    response_body = api_response.response_body
                
                # If response body is very large, truncate it
                if isinstance(response_body, str) and len(response_body) > 10000:
                    response_body = response_body[:10000] + "... [truncated]"
            else:
                response_body = ""
        except json.JSONDecodeError:
            response_body = api_response.response_body if api_response.response_body else ""
        
        # Context dictionary for direct API response
        context = {
            "source_type": "api_response",
            "request": {
                "url": request.url,
                "method": request.method,
                "headers": request_headers,
                "body": request_body
            },
            "response": {
                "status_code": api_response.status_code,
                "headers": response_headers,
                "body": response_body,
                "response_time_ms": api_response.response_time_ms
            }
        }
        
        return context
    
    @classmethod
    def _call_gemini_api(cls, context):
        """
        Call the Gemini API to generate root cause analysis.
        
        Formats the context into a structured prompt for the Gemini model
        and processes the response into a standardized RCA data structure.
        
        Args:
            context: Dictionary with structured context data
            
        Returns:
            dict: Structured RCA data with all required fields
        """
        # Get API key from environment or settings
        api_key = os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', None)
        
        # Ensure API key is configured
        if not api_key:
            raise ValueError("Gemini API key not configured in settings or environment")
        
        # Format the prompt for Gemini based on context source
        if context.get("source_type") == "chaos_test":
            prompt = cls._format_gemini_prompt_for_chaos_test(context)
        else:
            prompt = cls._format_gemini_prompt_for_api_response(context)
        
        # Prepare request payload
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 2048,
            }
        }
        
        # Call Gemini API with error handling and retry
        max_retries = 2
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                response = requests.post(
                    f"https://generativelanguage.googleapis.com/v1/models/{cls.GEMINI_MODEL}:generateContent?key={api_key}",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=20  # Increased timeout to prevent hanging requests
                )
                
                # Check for API errors
                if response.status_code != 200:
                    error_message = f"Gemini API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        if 'error' in error_data:
                            error_message += f" - {error_data['error'].get('message', '')}"
                    except:
                        error_message += f" - {response.text[:100]}"
                    
                    raise Exception(error_message)
                
                # Process the response
                response_data = response.json()
                
                # Extract the text from the response
                generated_text = ""
                try:
                    generated_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    raise Exception("Unexpected response format from Gemini API")
                
                # Parse the generated text into structured RCA data
                rca_data = cls._parse_gemini_response(generated_text, context)
                
                return rca_data
                
            except Exception as e:
                last_error = e
                retry_count += 1
                logger.warning(f"Gemini API call failed (attempt {retry_count}): {str(e)}")
                time.sleep(1)  # Wait a second before retrying
        
        # If we've exhausted retries, raise the last error or fall back
        if last_error:
            logger.error(f"All Gemini API retries failed: {str(last_error)}")
            return cls._generate_fallback_analysis(context)
    
    @classmethod
    def _generate_fallback_analysis(cls, context):
        """Generate a fallback analysis when the API call fails"""
        if context.get("source_type") == "chaos_test":
            fault_type = context["chaos_test"]["fault_type"]
            
            # Create analysis based on fault type
            root_cause = f"API failure due to {fault_type.lower().replace('_', ' ')} issue"
            
            if fault_type == 'MISSING_FIELD':
                detailed_analysis = "The API request is missing one or more required fields, causing validation to fail."
                potential_solutions = ["Ensure all required fields are included in the request", 
                                      "Verify the API documentation for required fields",
                                      "Implement request validation before sending to the API"]
                category = "Validation"
                
            elif fault_type == 'AUTH_FAILURE':
                detailed_analysis = "The API request has invalid or missing authentication credentials."
                potential_solutions = ["Verify authentication credentials are correct", 
                                      "Check that the authentication token is not expired",
                                      "Ensure authentication headers are properly formatted"]
                category = "Authentication"
                
            elif fault_type == 'CORRUPT_PAYLOAD':
                detailed_analysis = "The API request contains malformed or corrupt data that cannot be processed."
                potential_solutions = ["Validate request payload format before sending", 
                                      "Ensure JSON is properly formatted and valid",
                                      "Check for encoding issues in the request body"]
                category = "Data Format"
                
            elif fault_type == 'TIMEOUT':
                detailed_analysis = "The API request timed out, indicating potential performance issues."
                potential_solutions = ["Implement retry logic with exponential backoff", 
                                      "Consider optimizing the API endpoint for better performance",
                                      "Check for backend service availability"]
                category = "Performance"
                
            elif fault_type == 'INVALID_PARAM':
                detailed_analysis = "The API request contains invalid parameters that cannot be processed."
                potential_solutions = ["Review API documentation for correct parameter formats", 
                                      "Implement input validation before sending requests",
                                      "Check for type conversion issues in parameters"]
                category = "Validation"
                
            else:
                detailed_analysis = f"The API failure was caused by a {fault_type} issue that requires investigation."
                potential_solutions = ["Review API documentation", 
                                      "Check request format and parameters",
                                      "Implement better error handling"]
                category = "Other"
                
            # Modified URL comparison for context
            original_url = context["original_request"]["url"]
            modified_url = context["modified_request"]["url"]
            
            if original_url != modified_url:
                detailed_analysis += f"\n\nThe URL was modified from {original_url} to {modified_url}, which likely contributed to the failure."
                
            # Add response code context
            status_code = context["failed_response"]["status_code"]
            detailed_analysis += f"\n\nThe request resulted in a {status_code} status code."
            
        elif context.get("source_type") == "api_response":
            status_code = context["response"]["status_code"]
            
            # Create analysis based on status code
            if 400 <= status_code < 500:
                root_cause = f"Client error ({status_code}) in API request"
                detailed_analysis = cls._generate_analysis_from_status_code(status_code, context)
                
                if status_code == 400:
                    potential_solutions = ["Validate request format against API documentation",
                                          "Check for missing or invalid parameters",
                                          "Verify correct data types are being sent"]
                    category = "Validation"
                    
                elif status_code == 401:
                    potential_solutions = ["Verify authentication credentials",
                                          "Check if authentication token has expired",
                                          "Ensure correct authentication method is being used"]
                    category = "Authentication"
                    
                elif status_code == 403:
                    potential_solutions = ["Verify user permissions for the requested resource",
                                          "Check if the API key has correct scopes/permissions",
                                          "Contact API provider to ensure account has proper access"]
                    category = "Authorization"
                    
                elif status_code == 404:
                    potential_solutions = ["Verify the resource URL is correct",
                                          "Check if the resource exists or has been deleted",
                                          "Ensure API version and endpoint paths are correct"]
                    category = "Resource Not Found"
                    
                else:
                    potential_solutions = ["Review API documentation for correct request format",
                                          "Check for request validation errors",
                                          "Implement better error handling in the client"]
                    category = "Client Error"
                    
            elif 500 <= status_code < 600:
                root_cause = f"Server error ({status_code}) in API response"
                detailed_analysis = cls._generate_analysis_from_status_code(status_code, context)
                
                potential_solutions = ["Retry the request after a delay",
                                      "Contact the API provider to report the server error",
                                      "Implement circuit breaker pattern to handle repeated failures"]
                category = "Server Error"
                
            else:
                root_cause = f"Unexpected status code ({status_code}) in API response"
                detailed_analysis = f"The API returned an unusual status code {status_code}, which is outside the standard HTTP status code ranges."
                potential_solutions = ["Contact the API provider for clarification",
                                      "Check documentation for custom status codes",
                                      "Implement more robust error handling for unexpected responses"]
                category = "Other"
        else:
            # Generic fallback
            root_cause = "API failure with unknown cause"
            detailed_analysis = "Insufficient context to determine the specific cause of the API failure."
            potential_solutions = ["Implement better logging to capture request/response details",
                                  "Review API documentation for common error cases",
                                  "Add validation and error handling to all API calls"]
            category = "Unknown"
            
        return {
            "root_cause": root_cause,
            "detailed_analysis": detailed_analysis,
            "potential_solutions": potential_solutions,
            "confidence": "MEDIUM",
            "impact_severity": "MEDIUM",
            "failure_category": category,
            "affected_components": ["API Client", "Request Handling"],
            "tags": ["fallback", "auto-generated"]
        }

    # Other methods remain the same
    @classmethod
    def _format_gemini_prompt_for_chaos_test(cls, context):
        """Format a structured prompt for the Gemini API for chaos test analysis."""
        # Create a structured prompt from the chaos test context
        return f"""
You are an expert API Root Cause Analysis system. Analyze the following API failure from a chaos test and provide a detailed root cause analysis.

## CHAOS TEST INFORMATION
- Test Name: {context['chaos_test']['name']}
- Fault Type: {context['chaos_test']['fault_type']}
- Description: {context['chaos_test']['description']}

## ORIGINAL REQUEST (Working)
- URL: {context['original_request']['url']}
- Method: {context['original_request']['method']}
- Headers: {json.dumps(context['original_request']['headers'], indent=2)}
- Body: {json.dumps(context['original_request']['body'], indent=2)}

## MODIFIED REQUEST (Failed)
- URL: {context['modified_request']['url']}
- Method: {context['modified_request']['method']}
- Headers: {json.dumps(context['modified_request']['headers'], indent=2)}
- Body: {json.dumps(context['modified_request']['body'], indent=2)}

## FAILED RESPONSE
- Status Code: {context['failed_response']['status_code']}
- Headers: {json.dumps(context['failed_response']['headers'], indent=2)}
- Body: {context['failed_response']['body']}
- Response Time: {context['failed_response']['response_time_ms']} ms

## INSTRUCTIONS
Perform a detailed root cause analysis of this API failure. Return your response in the following JSON format:

```json
{{
  "root_cause": "Brief summary of the primary cause",
  "detailed_analysis": "Detailed explanation of why the failure occurred and the technical reasons behind it",
  "potential_solutions": ["List", "of", "recommended", "solutions", "to", "prevent", "this", "failure"],
  "confidence": "HIGH, MEDIUM, or LOW - your confidence in this analysis",
  "impact_severity": "CRITICAL, HIGH, MEDIUM, or LOW - severity if this happened in production",
  "failure_category": "Category of failure, e.g. 'Authentication', 'Validation', 'Database'",
  "affected_components": ["list", "of", "affected", "components"],
  "tags": ["relevant", "tags", "for", "this", "failure"]
}}
```

Your analysis should be detailed, technically accurate, and provide actionable insights.
"""

    @classmethod
    def _format_gemini_prompt_for_api_response(cls, context):
        """Format a structured prompt for the Gemini API for direct API response analysis."""
        # Create a structured prompt from the API response context
        return f"""
You are an expert API Root Cause Analysis system. Analyze the following failed API request and response to provide a detailed root cause analysis.

## API REQUEST
- URL: {context['request']['url']}
- Method: {context['request']['method']}
- Headers: {json.dumps(context['request']['headers'], indent=2)}
- Body: {json.dumps(context['request']['body'], indent=2)}

## API RESPONSE (Failed)
- Status Code: {context['response']['status_code']}
- Headers: {json.dumps(context['response']['headers'], indent=2)}
- Body: {context['response']['body']}
- Response Time: {context['response']['response_time_ms']} ms

## INSTRUCTIONS
Perform a detailed root cause analysis of this API failure. Be practical and realistic about what might have gone wrong, considering common API failure patterns based on the status code and response content.

Return your response in the following JSON format:

```json
{{
  "root_cause": "Brief summary of the primary cause",
  "detailed_analysis": "Detailed explanation of why the failure occurred and the technical reasons behind it",
  "potential_solutions": ["List", "of", "recommended", "solutions", "to", "prevent", "this", "failure"],
  "confidence": "HIGH, MEDIUM, or LOW - your confidence in this analysis",
  "impact_severity": "CRITICAL, HIGH, MEDIUM, or LOW - severity if this happened in production",
  "failure_category": "Category of failure, e.g. 'Authentication', 'Validation', 'Database'",
  "affected_components": ["list", "of", "affected", "components"],
  "tags": ["relevant", "tags", "for", "this", "failure"]
}}
```

Your analysis should be detailed, technically accurate, and provide actionable insights for the API consumer. Be specific about what the error means and how to fix it, basing your analysis on the specific status code, error messages, and any patterns in the request/response.
"""
    
    @classmethod
    def _parse_gemini_response(cls, response_text, context):
        """
        Parse the Gemini response into structured RCA data.
        
        Extracts the JSON data from the response and ensures all
        required fields are present, with sensible defaults for missing fields.
        
        Args:
            response_text: Raw text response from Gemini API
            context: Original context dictionary (for reference)
            
        Returns:
            dict: Structured RCA data with all required fields
        """
        # Try to extract JSON from the response
        try:
            # Look for JSON within the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_data = response_text[json_start:json_end]
                rca_data = json.loads(json_data)
                # Log successful JSON extraction
                logger.info("Successfully extracted and parsed JSON from Gemini response")
            else:
                # If no valid JSON is found, fall back to text extraction
                logger.warning("No JSON found in Gemini response, falling back to text extraction")
                rca_data = cls._extract_structured_data_from_text(response_text, context)
                
        except (json.JSONDecodeError, ValueError) as e:
            # Create structured data from unstructured text as a fallback
            logger.error(f"Error parsing Gemini response as JSON: {str(e)}")
            rca_data = cls._extract_structured_data_from_text(response_text, context)
            
        # Ensure all required fields are present
        required_fields = ['root_cause', 'detailed_analysis', 'potential_solutions']
        for field in required_fields:
            if field not in rca_data or not rca_data[field]:
                if field == 'detailed_analysis':
                    # If we failed to extract detailed analysis, use the full response text
                    if response_text and len(response_text) > 10:
                        cleaned_text = cls._clean_response_text(response_text)
                        rca_data[field] = cleaned_text
                    else:
                        # If context is from API response, try to generate analysis based on status code
                        if context.get('source_type') == 'api_response':
                            status_code = context['response']['status_code']
                            rca_data[field] = cls._generate_analysis_from_status_code(status_code, context)
                        else:
                            # Fallback for chaos test
                            rca_data[field] = f"Analysis of the API failure indicates that it was likely caused by a {context['chaos_test']['fault_type']} issue. Examine the request and response data for more specific details about what went wrong."
                elif field == 'potential_solutions':
                    # If potential_solutions is a string, convert it to a list
                    if isinstance(rca_data.get(field), str):
                        solutions_text = rca_data[field]
                        solutions = []
                        
                        # Try to split by newlines or periods
                        if '\n' in solutions_text:
                            # Split by newlines and clean up
                            solutions = [s.strip() for s in solutions_text.split('\n') if s.strip()]
                        else:
                            # Split by periods
                            solutions = [s.strip() + '.' for s in solutions_text.split('.') if s.strip()]
                            
                        if solutions:
                            rca_data[field] = solutions
                        else:
                            rca_data[field] = [f"No {field.replace('_', ' ')} provided by analysis"]
                    elif not isinstance(rca_data.get(field), list):
                        rca_data[field] = [f"No {field.replace('_', ' ')} provided by analysis"]
                else:
                    rca_data[field] = f"No {field.replace('_', ' ')} provided by analysis"
                
        # Set confidence if not present
        if 'confidence' not in rca_data or not isinstance(rca_data['confidence'], str) or rca_data['confidence'] not in ['HIGH', 'MEDIUM', 'LOW']:
            rca_data['confidence'] = 'MEDIUM'
            
        # Set impact severity if not present or invalid
        valid_severities = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        if 'impact_severity' not in rca_data or not isinstance(rca_data['impact_severity'], str) or rca_data['impact_severity'] not in valid_severities:
            # Default to MEDIUM or infer from context
            rca_data['impact_severity'] = 'MEDIUM'
            
        # Set failure category if not present
        if 'failure_category' not in rca_data or not rca_data['failure_category']:
            # Infer category from context
            if context.get('source_type') == 'chaos_test':
                fault_type = context['chaos_test']['fault_type']
                category_map = {
                    'MISSING_FIELD': 'Validation',
                    'AUTH_FAILURE': 'Authentication',
                    'CORRUPT_PAYLOAD': 'Data Format',
                    'TIMEOUT': 'Performance',
                    'MISSING_DB': 'Database',
                    'INVALID_PARAM': 'Validation',
                }
                rca_data['failure_category'] = category_map.get(fault_type, 'Other')
            else:
                # Infer from status code for API responses
                status_code = context['response']['status_code']
                rca_data['failure_category'] = cls._infer_category_from_status_code(status_code)
            
        # Ensure affected_components and tags are lists
        if 'affected_components' not in rca_data or not isinstance(rca_data['affected_components'], list):
            rca_data['affected_components'] = ["API Client"]
            
        if 'tags' not in rca_data or not isinstance(rca_data['tags'], list):
            rca_data['tags'] = ["auto-generated"]
            
        return rca_data
    
    @classmethod
    def _extract_structured_data_from_text(cls, text, context):
        """Extract structured RCA data from unstructured text when JSON parsing fails."""
        # Clean up the text first to remove unwanted sections
        cleaned_text = cls._clean_response_text(text)
        
        # Initialize our structured data with defaults
        rca_data = {
            'root_cause': '',
            'detailed_analysis': '',
            'potential_solutions': [],
            'confidence': 'MEDIUM',
            'impact_severity': 'MEDIUM',
            'failure_category': '',
            'affected_components': [],
            'tags': []
        }
        
        # Extract root cause - look for sections or paragraphs that mention root cause
        root_cause_patterns = [
            r'(?:Root Cause|ROOT CAUSE)[:]\s*(.*?)(?:\n\n|\n#)',
            r'The root cause (?:is|appears to be|was)\s*(.*?)(?:\.|$)',
            r'(?:cause|reason)(?:s)? (?:of|for) the failure\s*(?:is|are|was|were)[:]*\s*(.*?)(?:\.|$)'
        ]
        
        for pattern in root_cause_patterns:
            matches = re.search(pattern, cleaned_text, re.IGNORECASE | re.DOTALL)
            if matches:
                rca_data['root_cause'] = matches.group(1).strip()
                break
        
        # If no specific section found, use the first paragraph as a fallback for root cause
        if not rca_data['root_cause'] and '\n\n' in cleaned_text:
            first_para = cleaned_text.split('\n\n')[0]
            if 10 < len(first_para) < 200:  # Reasonable length for a root cause
                rca_data['root_cause'] = first_para.strip()
        
        # If still no root cause, create a simple one based on context
        if not rca_data['root_cause']:
            if context.get('source_type') == 'chaos_test':
                fault_type = context['chaos_test']['fault_type']
                rca_data['root_cause'] = f"API failure caused by {fault_type.lower().replace('_', ' ')} issue"
            elif context.get('source_type') == 'api_response':
                status_code = context['response']['status_code']
                if 400 <= status_code < 500:
                    rca_data['root_cause'] = f"Client error ({status_code}) in API request"
                elif 500 <= status_code < 600:
                    rca_data['root_cause'] = f"Server error ({status_code}) in API response"
                else:
                    rca_data['root_cause'] = f"Unexpected status code ({status_code}) in API response"
            else:
                rca_data['root_cause'] = "API failure with undetermined cause"
        
        # Extract detailed analysis - use the entire cleaned text if no specific section
        analysis_patterns = [
            r'(?:Detailed Analysis|DETAILED ANALYSIS)[:]\s*(.*?)(?:\n#|\n\n\n)',
            r'(?:Analysis|ANALYSIS)[:]\s*(.*?)(?:\n#|\n\n\n)'
        ]
        
        for pattern in analysis_patterns:
            matches = re.search(pattern, cleaned_text, re.IGNORECASE | re.DOTALL)
            if matches:
                rca_data['detailed_analysis'] = matches.group(1).strip()
                break
        
        # If no specific analysis section found, use the cleaned text as the detailed analysis
        if not rca_data['detailed_analysis']:
            rca_data['detailed_analysis'] = cleaned_text
        
        # Extract potential solutions
        solution_patterns = [
            r'(?:Potential Solutions|POTENTIAL SOLUTIONS|Recommendations|RECOMMENDATIONS)[:]\s*(.*?)(?:\n#|\n\n\n|$)',
            r'(?:Solution|SOLUTION)[:]\s*(.*?)(?:\n#|\n\n\n|$)',
            r'(?:To fix|To resolve) this issue[,]?\s*(.*?)(?:\n#|\n\n\n|$)'
        ]
        
        for pattern in solution_patterns:
            matches = re.search(pattern, cleaned_text, re.IGNORECASE | re.DOTALL)
            if matches:
                solutions_text = matches.group(1).strip()
                # Split into list items if they're formatted with numbers or bullets
                solutions = re.findall(r'(?:^|\n)(?:\d+\.|\*|\-)\s*(.*?)(?=\n\d+\.|\n\*|\n\-|$)', solutions_text, re.DOTALL)
                if solutions:
                    rca_data['potential_solutions'] = [s.strip() for s in solutions]
                else:
                    # If no list format, split by periods or newlines
                    sentences = re.split(r'(?<=[.!?])\s+', solutions_text)
                    rca_data['potential_solutions'] = [s.strip() for s in sentences if len(s.strip()) > 10]
                break
        
        # If no solutions found, add generic solutions based on context
        if not rca_data['potential_solutions']:
            if context.get('source_type') == 'chaos_test':
                fault_type = context['chaos_test']['fault_type']
                if fault_type == 'MISSING_FIELD':
                    rca_data['potential_solutions'] = ["Ensure all required fields are included in the request",
                                                     "Validate requests before sending to the API"]
                elif fault_type == 'AUTH_FAILURE':
                    rca_data['potential_solutions'] = ["Verify authentication credentials are correct",
                                                     "Check that tokens are not expired"]
                elif fault_type == 'CORRUPT_PAYLOAD':
                    rca_data['potential_solutions'] = ["Validate JSON format before sending",
                                                     "Implement proper error handling for malformed data"]
                elif fault_type == 'TIMEOUT':
                    rca_data['potential_solutions'] = ["Implement retry logic with exponential backoff",
                                                     "Optimize API requests to reduce response times"]
                else:
                    rca_data['potential_solutions'] = ["Review API documentation for proper request formats",
                                                     "Implement comprehensive error handling"]
            else:
                status_code = context['response']['status_code'] if context.get('response', {}).get('status_code') else 0
                if 400 <= status_code < 500:
                    rca_data['potential_solutions'] = ["Verify request format matches API documentation",
                                                     "Check for missing or invalid parameters",
                                                     "Verify correct data types are being sent"]
                elif 500 <= status_code < 600:
                    rca_data['potential_solutions'] = ["Implement retry logic for server errors",
                                                     "Contact API provider about server issues"]
                else:
                    rca_data['potential_solutions'] = ["Implement more robust error handling",
                                                     "Add logging to capture detailed request/response information"]
        
        # Infer failure category from the text or context
        category_keywords = {
            'Authentication': ['auth', 'authentication', 'credential', 'permission', 'access denied'],
            'Authorization': ['authoriz', 'permission', 'access control', 'forbidden'],
            'Validation': ['validation', 'invalid', 'missing field', 'required field', 'input error'],
            'Data Format': ['format', 'malformed', 'corrupt', 'json', 'xml', 'payload'],
            'Database': ['database', 'db', 'query', 'sql', 'data store', 'record'],
            'Performance': ['timeout', 'slow', 'performance', 'latency', 'response time'],
            'Network': ['network', 'connection', 'dns', 'routing', 'timeout'],
            'Configuration': ['config', 'setting', 'environment', 'parameter']
        }
        
        # Try to infer category from the text
        text_lower = cleaned_text.lower()
        for category, keywords in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                rca_data['failure_category'] = category
                break
        
        # If still no category, infer from context
        if not rca_data['failure_category']:
            if context.get('source_type') == 'chaos_test' and 'chaos_test' in context:
                fault_type = context['chaos_test'].get('fault_type', '')
                category_map = {
                    'MISSING_FIELD': 'Validation',
                    'AUTH_FAILURE': 'Authentication',
                    'CORRUPT_PAYLOAD': 'Data Format',
                    'TIMEOUT': 'Performance',
                    'MISSING_DB': 'Database',
                    'INVALID_PARAM': 'Validation',
                }
                rca_data['failure_category'] = category_map.get(fault_type, 'Other')
            elif context.get('source_type') == 'api_response' and 'response' in context:
                status_code = context['response'].get('status_code', 0)
                rca_data['failure_category'] = cls._infer_category_from_status_code(status_code)
        
        # Extract affected components (if any are mentioned)
        component_patterns = [
            r'(?:Affected Components|Components)[:]\s*(.*?)(?:\n#|\n\n|$)',
            r'(?:affected|impacted)(?:\s+the)?\s+(\w+\s+\w+(?:\s+\w+)?)'
        ]
        
        for pattern in component_patterns:
            matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple):
                    matches = [m[0] for m in matches]
                components = []
                for match in matches:
                    # Split by commas or "and" if present
                    parts = re.split(r',|\sand\s', match)
                    components.extend([p.strip() for p in parts if p.strip()])
                rca_data['affected_components'] = components
                break
        
        # Set fallback components if none found
        if not rca_data['affected_components']:
            rca_data['affected_components'] = ["API Client", "Request Processing"]
        
        # Set confidence based on the specificity of our findings
        if rca_data['root_cause'] and rca_data['potential_solutions']:
            rca_data['confidence'] = 'MEDIUM'
        elif not rca_data['root_cause'] or not rca_data['potential_solutions']:
            rca_data['confidence'] = 'LOW'
        
        # Add tags based on context and findings
        if context.get('source_type') == 'chaos_test':
            rca_data['tags'].append(context['chaos_test']['fault_type'].lower())
            
        if rca_data['failure_category']:
            rca_data['tags'].append(rca_data['failure_category'].lower())
            
        # Add tags for status code range
        if context.get('source_type') == 'api_response':
            status_code = context['response'].get('status_code', 0)
            if 400 <= status_code < 500:
                rca_data['tags'].append('client-error')
            elif 500 <= status_code < 600:
                rca_data['tags'].append('server-error')
                
        # Add tag for extraction method
        rca_data['tags'].append('text-extracted')
        
        return rca_data
    
    @classmethod
    def _clean_response_text(cls, text):
        """Clean up response text by removing markdown formatting and unwanted sections."""
        # Remove code blocks
        text = re.sub(r'```json\s*.*?\s*```', '', text, flags=re.DOTALL)
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        
        # Remove unwanted sections
        unwanted_sections = [
            "Table of Contents", "Executive Summary", 
            "JSON FORMAT", "INSTRUCTIONS", "RESPONSE FORMAT"
        ]
        
        for section in unwanted_sections:
            # Pattern to match a section header and its content until the next section
            pattern = re.compile(rf'##\s*{section}.*?(?=##\s*\w+:|$)', re.DOTALL | re.IGNORECASE)
            text = re.sub(pattern, '', text)
            
            # Also try without the ## format
            pattern = re.compile(rf'{section}:.*?(?=\w+:|$)', re.DOTALL | re.IGNORECASE)
            text = re.sub(pattern, '', text)
        
        # Clean up remaining markdown and extra whitespace
        text = re.sub(r'##\s+', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
        
    @classmethod
    def _infer_category_from_status_code(cls, status_code):
        """Infer the failure category based on the HTTP status code."""
        if 400 <= status_code < 500:
            if status_code == 400:
                return "Validation"
            elif status_code == 401:
                return "Authentication"
            elif status_code == 403:
                return "Authorization"
            elif status_code == 404:
                return "Resource Not Found"
            elif status_code == 405:
                return "Method Not Allowed"
            elif status_code == 413:
                return "Request Size Limit"
            elif status_code == 429:
                return "Rate Limiting"
            else:
                return "Client Error"
        elif 500 <= status_code < 600:
            if status_code == 500:
                return "Server Error"
            elif status_code == 502:
                return "Gateway Error"
            elif status_code == 503:
                return "Service Unavailability"
            elif status_code == 504:
                return "Timeout"
            else:
                return "Server Error"
        else:
            return "Other"
            
    @classmethod
    def _generate_analysis_from_status_code(cls, status_code, context):
        """Generate a basic analysis based on the HTTP status code when other methods fail."""
        url = context['request']['url'] if 'request' in context else "unknown URL"
        method = context['request']['method'] if 'request' in context else "unknown method"
        
        analysis = f"Analysis of the {method} request to {url} that resulted in a {status_code} status code:\n\n"
        
        if 400 <= status_code < 500:
            if status_code == 400:
                analysis += "The API returned a 400 Bad Request error, indicating that the server could not understand the request due to invalid syntax. "
                analysis += "This typically happens when the request body or parameters don't match what the API expects. "
                analysis += "Common causes include missing required fields, invalid data formats, or incompatible data types."
            elif status_code == 401:
                analysis += "The API returned a 401 Unauthorized error, indicating that authentication is required but was either missing or invalid. "
                analysis += "This typically happens when no authentication credentials are provided, or when the provided credentials (like API keys or tokens) are expired or incorrect."
            elif status_code == 403:
                analysis += "The API returned a 403 Forbidden error, indicating that the server understood the request but refuses to authorize it. "
                analysis += "This typically happens when the authenticated user doesn't have sufficient permissions to access the requested resource or perform the requested action."
            elif status_code == 404:
                analysis += "The API returned a 404 Not Found error, indicating that the requested resource could not be found on the server. "
                analysis += "This typically happens when the URL path is incorrect, when trying to access a resource that doesn't exist, or when a resource has been deleted."
            elif status_code == 405:
                analysis += "The API returned a 405 Method Not Allowed error, indicating that the HTTP method used is not supported for the requested resource. "
                analysis += f"This typically happens when trying to use {method} on an endpoint that doesn't support this method."
            elif status_code == 429:
                analysis += "The API returned a 429 Too Many Requests error, indicating that you've exceeded the rate limits for this API. "
                analysis += "This typically happens when sending too many requests in a short period of time."
            else:
                analysis += f"The API returned a {status_code} client error, indicating an issue with the request rather than the server. "
                analysis += "Client errors in the 4xx range typically indicate that there's something wrong with the request format, parameters, or permissions."
        elif 500 <= status_code < 600:
            if status_code == 500:
                analysis += "The API returned a 500 Internal Server Error, indicating that the server encountered an unexpected condition that prevented it from fulfilling the request. "
                analysis += "This typically happens when there's an unhandled exception or runtime error on the server side."
            elif status_code == 502:
                analysis += "The API returned a 502 Bad Gateway error, indicating that the server, while acting as a gateway or proxy, received an invalid response from an upstream server. "
                analysis += "This typically happens when there are network issues between servers or when an upstream service is malfunctioning."
            elif status_code == 503:
                analysis += "The API returned a 503 Service Unavailable error, indicating that the server is temporarily unable to handle the request due to maintenance or overloading. "
                analysis += "This typically happens during scheduled maintenance periods or when the server is experiencing high load."
            elif status_code == 504:
                analysis += "The API returned a 504 Gateway Timeout error, indicating that the server, while acting as a gateway or proxy, did not receive a timely response from an upstream server. "
                analysis += "This typically happens when an upstream service is taking too long to respond or is unreachable."
            else:
                analysis += f"The API returned a {status_code} server error, indicating an issue with the server rather than your request. "
                analysis += "Server errors in the 5xx range typically indicate that there's a problem with the API's infrastructure or code."
        else:
            analysis += f"The API returned an unusual status code {status_code}, which is outside the standard HTTP status code ranges. "
            analysis += "This might indicate a custom status code used by the API or a misconfiguration in the API server."
            
        # Add response body analysis if available
        if 'response' in context and 'body' in context['response'] and context['response']['body']:
            response_body = context['response']['body']
            if isinstance(response_body, dict) and 'error' in response_body:
                error_msg = response_body['error']
                analysis += f"\n\nThe API returned an error message: '{error_msg}'. "
                analysis += "This error message provides more specific information about what went wrong."
            elif isinstance(response_body, str) and len(response_body) > 0 and len(response_body) < 1000:
                analysis += f"\n\nThe API returned a response body: '{response_body}'. "
                analysis += "This response might contain more specific information about what went wrong."
        
        return analysis