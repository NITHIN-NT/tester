"""
Vercel serverless function handler for Django application.
This file wraps the Django WSGI application to work with Vercel's serverless functions.
"""

import os
import sys
from pathlib import Path
from io import BytesIO

# Add the project root to Python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'review_dashboard.settings')

# Import Django WSGI application
from django.core.wsgi import get_wsgi_application

# Get the WSGI application
application = get_wsgi_application()

# Export handler for Vercel
def handler(request):
    """
    Vercel serverless function handler.
    Converts Vercel request to WSGI and calls Django application.
    """
    # Vercel Python runtime provides request as an object with specific attributes
    # Extract request details
    method = getattr(request, 'method', 'GET')
    
    # Get headers first (needed for path extraction)
    headers = {}
    if hasattr(request, 'headers'):
        headers = dict(request.headers) if hasattr(request.headers, 'items') else request.headers
    elif hasattr(request, 'get'):
        # If request is dict-like
        headers = request.get('headers', {})
    
    # Get path - Vercel provides this in the request
    # The rewrite sends all requests to /api/index.py, but we need the original path
    path = getattr(request, 'path', '/')
    
    # Vercel passes the original path in the request, but if it's /api/index.py, 
    # we need to extract it from the URL or use a default
    if path == '/api/index.py' or path == '/api' or not path or path == '':
        # Try to get original path from various sources
        # Check for x-vercel-rewrite-original-path or similar headers
        original_path = (
            headers.get('x-vercel-rewrite-original-path') or
            headers.get('x-invoke-path') or
            headers.get('x-original-path')
        )
        if original_path:
            path = original_path
        elif hasattr(request, 'url'):
            # Extract from URL
            from urllib.parse import urlparse
            url_str = str(request.url)
            parsed = urlparse(url_str)
            path = parsed.path or '/'
            # Remove /api/index.py if it's in the path
            if path.startswith('/api/index.py'):
                path = path[13:] or '/'  # Remove '/api/index.py' (13 chars)
        else:
            # Default to root if we can't determine
            path = '/'
    
    # Ensure path starts with /
    if not path or not path.startswith('/'):
        path = '/' + (path if path else '')
    
    # Get query string
    query_string = ''
    if hasattr(request, 'query_string'):
        query_string = request.query_string or ''
    elif hasattr(request, 'queryStringParameters'):
        # Vercel format
        query_params = request.queryStringParameters or {}
        if query_params:
            from urllib.parse import urlencode
            query_string = urlencode(query_params)
    elif hasattr(request, 'url') and '?' in str(request.url):
        query_string = str(request.url).split('?', 1)[1]
    
    # Get body
    body = b''
    if hasattr(request, 'body'):
        req_body = request.body
        if isinstance(req_body, bytes):
            body = req_body
        elif isinstance(req_body, str):
            body = req_body.encode('utf-8')
    elif hasattr(request, 'get'):
        # If request is dict-like
        req_body = request.get('body', '')
        if isinstance(req_body, bytes):
            body = req_body
        elif isinstance(req_body, str):
            body = req_body.encode('utf-8')
    
    # Convert Vercel request to WSGI environment
    host = headers.get('host', 'localhost')
    server_name = host.split(':')[0] if ':' in host else host
    server_port = host.split(':')[1] if ':' in host else '80'
    
    environ = {
        'REQUEST_METHOD': method,
        'SCRIPT_NAME': '',
        'PATH_INFO': path,
        'QUERY_STRING': query_string,
        'CONTENT_TYPE': headers.get('content-type', ''),
        'CONTENT_LENGTH': str(len(body)) if body else '',
        'SERVER_NAME': server_name,
        'SERVER_PORT': server_port,
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': headers.get('x-forwarded-proto', 'https'),
        'wsgi.input': BytesIO(body),
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': False,
        'wsgi.multiprocess': True,
        'wsgi.run_once': False,
    }
    
    # Add headers to environ
    for key, value in headers.items():
        key = key.upper().replace('-', '_')
        if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            key = f'HTTP_{key}'
        environ[key] = value
    
    # Call Django WSGI application
    status_code = [200]
    response_headers = []
    
    def start_response(status, headers_list):
        status_code[0] = int(status.split()[0])
        response_headers.extend(headers_list)
    
    response_body = application(environ, start_response)
    
    # Collect response body
    body_parts = []
    for part in response_body:
        if isinstance(part, bytes):
            body_parts.append(part)
        else:
            body_parts.append(part.encode('utf-8'))
    body_result = b''.join(body_parts)
    
    # Create response
    response_headers_dict = {key: value for key, value in response_headers}
    
    # Return dictionary format (works with Vercel Python runtime)
    return {
        'statusCode': status_code[0],
        'headers': response_headers_dict,
        'body': body_result.decode('utf-8', errors='replace')
    }
