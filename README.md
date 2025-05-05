# FixIt.AI - API Testing & Root Cause Analysis Platform

FixIt.AI is a Django-based application that provides a comprehensive platform for API testing, chaos engineering, and automated root cause analysis. It helps developers test, break, and fix their APIs in a controlled environment.

## Screenshots


![FixIt.AI Dashboard](https://github.com/Dibae101/Fixit.AI/raw/main/images/fixit_dashboard.png)


![API Tester](https://github.com/Dibae101/Fixit.AI/raw/main/images/api_tester.png)


![Break the App](https://github.com/Dibae101/Fixit.AI/raw/main/images/break_app.png)


![Root Cause Analysis](https://github.com/Dibae101/Fixit.AI/raw/main/images/root_cause_analysis.png)


![API Documentation](https://github.com/Dibae101/Fixit.AI/raw/main/images/api_documentation.png)

## Features

### 1. API Testing
- **API Tester:** Send API requests with custom headers and body payloads
- **Response Analysis:** View detailed API responses with formatted JSON
- **Request History:** Access and reuse previous API requests

### 2. Chaos Engineering
- **Chaos Test Framework:** Apply predefined fault scenarios to your APIs
- **Custom Fault Injection:** Create your own chaos tests with specific failure modes
- **Failure Categories:**
  - Missing Required Fields
  - Authentication Failures
  - Corrupted JSON Payloads
  - Request Timeouts
  - Missing Database Records
  - And more...

### 3. Root Cause Analysis (RCA)
- **AI-Powered Analysis:** Automated root cause analysis using Gemini API
- **Detailed Reports:** Comprehensive reports with:
  - Root cause identification
  - Detailed analysis
  - Potential solutions
  - Confidence ratings
  - Severity assessment
- **Categorization:** Classify failures by type and affected components

### 4. Internal APIs for Testing
- **Todo Items API:** CRUD operations with rate limiting
- **Product API:** Inventory management and product operations
- **Built-in Failure Modes:** For testing the chaos engineering framework

## Dashboard & Analytics
- **API Success Rates:** Track overall API performance
- **Recent Activity:** View recent tests and analyses
- **Categorized Issues:** Group and analyze failures by type

## Modules & Pages

### 1. Dashboard (`/`)
The main dashboard provides an overview of system statistics, recent activity, and quick access to all tools.

### 2. API Tester (`/api-tester/`)
A tool for sending and testing API requests with:
- Method selection (GET, POST, PUT, DELETE, etc.)
- URL input
- Custom headers
- Request body
- Response visualization

### 3. API Response Detail (`/api-response/<uuid:response_id>/`)
Detailed view of API responses showing:
- Request details
- Response status code
- Response headers
- Formatted response body
- Option to generate RCA for failed responses

### 4. Break the App (`/break-app/`)
Chaos engineering dashboard for:
- Selecting API requests to inject faults into
- Choosing chaos test types
- Viewing test results
- Creating custom chaos tests

### 5. Chaos Test Runs (`/chaos-test-runs/`)
History and details of chaos tests including:
- Original requests
- Modified requests
- Failed responses
- Test outcomes

### 6. RCA Generator (`/rca-generator/`)
Tool for generating root cause analysis from:
- Failed API responses
- Chaos test runs

### 7. RCA Detail (`/rca-detail/<uuid:rca_id>/`)
Comprehensive view of a root cause analysis:
- Root cause summary
- Detailed analysis
- Potential solutions
- Related failures
- Categorization data

## REST API Endpoints

### Todo Items API
- `GET /api/todos/` - List all todo items
- `POST /api/todos/` - Create a new todo item
- `GET /api/todos/{id}/` - Retrieve a specific todo item
- `PUT/PATCH /api/todos/{id}/` - Update a todo item
- `DELETE /api/todos/{id}/` - Delete a todo item
- `DELETE /api/todos/delete_completed/` - Delete all completed todos

### Products API
- `GET /api/products/` - List all products
- `POST /api/products/` - Create a new product
- `GET /api/products/{id}/` - Retrieve a specific product
- `PUT/PATCH /api/products/{id}/` - Update a product
- `DELETE /api/products/{id}/` - Delete a product
- `GET /api/products/available/` - List only available products
- `POST /api/products/{id}/update_inventory/` - Update product inventory

## How It Works

FixIt.AI is designed as an end-to-end platform for API debugging and quality assurance:

1. **Testing Your APIs:**
   - Use the API Tester to send requests to your APIs
   - Specify URL, method, headers, and request body
   - View formatted responses and store the request/response pair for future reference
   - All requests are logged and can be reused or modified for future tests

2. **Breaking Your APIs (Chaos Engineering):**
   - Select a previously executed API request
   - Choose a chaos test type to apply (e.g., missing fields, authentication failures)
   - The system injects faults into your request based on the selected test
   - Observe how your API handles the failure case
   - All results are stored for analysis and comparison

3. **Fixing Your APIs (Root Cause Analysis):**
   - For failed responses (either from normal testing or chaos engineering)
   - The system uses AI (Gemini API) to analyze the failure
   - It generates detailed reports with:
     - Root cause identification
     - Suggested fixes
     - Prevention measures
   - The analysis is categorized and stored for knowledge base building

4. **Learning & Improvement:**
   - Dashboard metrics show overall API health
   - Failure patterns are identified across multiple tests
   - Categorized issues help prioritize fixes
   - Historical data helps track improvement over time

## Running the Application

### Option 1: Using the Development Server

1. Clone the repository:
```bash
git clone https://github.com/yourusername/fixit.ai.git
cd fixit.ai
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Create a superuser (for admin access):
```bash
python manage.py createsuperuser
```

6. Start the development server:
```bash
python manage.py runserver
```

7. Access the application at http://127.0.0.1:8000/

### Option 2: Using Gunicorn (Production)

For production deployment, the application includes a start script:

1. Make the start script executable:
```bash
chmod +x start_server.sh
```

2. Run the start script:
```bash
./start_server.sh
```

This will:
- Activate the virtual environment
- Start Gunicorn with 3 worker processes
- Bind to 0.0.0.0:8000 (accessible on all network interfaces)
- Log access and errors to the logs directory
- Run the process in the background (using nohup)

3. Access the application at http://your-server-ip:8000/

4. To stop the server:
```bash
ps aux | grep gunicorn
kill <PID>  # Replace <PID> with the process ID from the output above
```

### Option 3: Using Docker

1. Make sure Docker and Docker Compose are installed

2. Build and start the containers:
```bash
docker-compose up -d
```

3. Run migrations and create a superuser:
```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

4. Access the application at http://localhost:8000/

5. To stop the containers:
```bash
docker-compose down
```

## Using the Application

### Walkthrough: Testing an API

1. Navigate to the API Tester page
2. Enter the API endpoint (e.g., `https://api.example.com/users`)
3. Select the HTTP method (GET, POST, PUT, DELETE)
4. Add any required headers (e.g., `Content-Type: application/json`)
5. For POST/PUT requests, add the request body as JSON
6. Click "Send Request"
7. View the formatted response, including status code, headers, and body
8. For failed responses, click "Generate RCA" to analyze the failure

### Walkthrough: Breaking an API

1. Navigate to the "Break the App" page
2. Select a previously executed API request from the list
3. Choose a chaos test type:
   - Missing Required Fields - removes mandatory fields
   - Authentication Failures - corrupts authentication tokens
   - Malformed JSON - introduces syntax errors in JSON
   - Timeout Simulation - adds artificial latency
   - Invalid Values - replaces valid values with invalid ones
4. Click "Apply Chaos"
5. Review the results showing:
   - Original request
   - Modified request (with injected faults)
   - API response to the faulty request
6. Click "Generate RCA" to analyze why the failure occurred

### Walkthrough: Analyzing Root Causes

1. Navigate to the RCA Generator page
2. Select a failed API response from the list
3. Click "Generate Analysis"
4. Review the comprehensive analysis:
   - Summary of the issue
   - Root cause identification
   - Detailed explanation
   - Suggested fixes and prevention measures
   - Confidence rating of the analysis
   - Severity assessment
5. Save the analysis for future reference
6. Use the insights to fix your API implementation

## API Documentation

### Internal APIs for Testing

- **Todo Items API:** `/api/todos/`
- **Product API:** `/api/products/`

## Configuration

### Environment Variables
- `GEMINI_API_KEY` - Your Google Gemini API key for AI-powered analysis
- `DEBUG` - Set to True for development, False for production
- `DATABASE_URL` - Database connection string (if using PostgreSQL)

## Project Structure

```
fixit.ai/
├── fixit_ai/                  # Main Django project folder
│   ├── settings.py            # Project settings
│   ├── urls.py                # Main URL routing
│   ├── wsgi.py                # WSGI configuration
│   └── asgi.py                # ASGI configuration
├── playground/                # Main application
│   ├── migrations/            # Database migrations
│   ├── templates/             # HTML templates
│   │   └── playground/        # App-specific templates
│   ├── utils/                 # Utility modules
│   │   ├── api_client.py      # API client for making requests
│   │   ├── chaos_injector.py  # Chaos test injection
│   │   ├── rate_limiter.py    # API rate limiting
│   │   └── rca_engine.py      # Root cause analysis engine
│   ├── models.py              # Database models
│   ├── views.py               # View controllers
│   ├── urls.py                # App URL routing
│   ├── forms.py               # Form definitions
│   └── serializers.py         # REST API serializers
├── media/                     # User uploaded files
├── static/                    # Static files (CSS, JS)
├── staticfiles/               # Collected static files
├── logs/                      # Application logs
├── manage.py                  # Django management script
├── requirements.txt           # Python dependencies
├── docker-compose.yml         # Docker Compose config
└── Dockerfile                 # Docker build file
```

## Development

### Adding New Chaos Tests

You can add new chaos tests by:
1. Adding a new entry in the `ChaosTest` model
2. Implementing the failure mode in `chaos_injector.py`

### Extending RCA Capabilities

To enhance the root cause analysis:
1. Modify the `RcaEngine` class in `rca_engine.py`
2. Update the RCA templates in the `templates/playground/` directory

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check your database settings in `fixit_ai/settings.py`
   - Ensure the database service is running
   - Verify credentials are correct

2. **Missing Gemini API Key**
   - Ensure the `GEMINI_API_KEY` environment variable is set
   - Alternatively, add it directly in `settings.py`

3. **Server Won't Start**
   - Check logs in the `logs/` directory
   - Ensure required ports are available
   - Verify all dependencies are installed

4. **API Requests Fail**
   - Check network connectivity
   - Verify endpoint URLs are correct
   - Ensure proper authentication is provided

### Logs

Application logs are stored in:
- `logs/access.log` - HTTP request logs
- `logs/error.log` - Application errors and exceptions

Use these logs to diagnose issues with the application.

## License

[MIT License](LICENSE)

## Contributors

- Dibya Darshan Khanal - Initial development

## Acknowledgments

- [Django](https://www.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Google Gemini API](https://ai.google.dev/)
