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
    # Parse request - Vercel Python runtime provides request as dict or object
    if isinstance(request, dict):
        # Request is a dictionary (Vercel format)
        method = request.get('method', 'GET')
        path = request.get('path', '/')
        headers = request.get('headers', {})
        body = request.get('body', b'')
        if isinstance(body, str):
            body = body.encode('utf-8')
        query_string = request.get('queryStringParameters', {})
        if query_string:
            from urllib.parse import urlencode
            query_string = urlencode(query_string)
        else:
            query_string = ''
    else:
        # Request is an object
        # Parse request body
        body = b''
        if hasattr(request, 'body'):
            if isinstance(request.body, bytes):
                body = request.body
            elif isinstance(request.body, str):
                body = request.body.encode('utf-8')
        
        # Get query string from URL
        query_string = ''
        if hasattr(request, 'url'):
            if hasattr(request.url, 'query'):
                query_string = request.url.query or ''
            elif '?' in str(request.url):
                query_string = str(request.url).split('?', 1)[1]
        
        # Get path
        path = '/'
        if hasattr(request, 'path'):
            path = request.path
        elif hasattr(request, 'url'):
            if hasattr(request.url, 'path'):
                path = request.url.path
            else:
                url_str = str(request.url)
                if '?' in url_str:
                    path = url_str.split('?')[0]
                else:
                    path = url_str
        
        # Get headers
        headers = {}
        if hasattr(request, 'headers'):
            headers = dict(request.headers)
        
        # Get method
        method = 'GET'
        if hasattr(request, 'method'):
            method = request.method
    
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
