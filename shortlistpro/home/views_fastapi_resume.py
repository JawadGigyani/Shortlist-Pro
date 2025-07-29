import requests
from django.shortcuts import render
from django.contrib import messages

def upload_resumes(request):
    """
    View to handle resume uploads, send them to FastAPI for parsing,
    and display the parsed results.
    """
    from .models import JobDescription
    job_descriptions = JobDescription.objects.filter(user=request.user).order_by('-created_at')
    
    if request.method == 'POST':
        files = request.FILES.getlist('resume_files')
        fastapi_url = 'http://127.0.0.1:8000/parse-resumes'
        
        # Prepare files for FastAPI
        files_payload = []
        for f in files:
            files_payload.append(('files', (f.name, f.read(), f.content_type)))
        
        try:
            response = requests.post(fastapi_url, files=files_payload)
            response.raise_for_status()
            api_response = response.json()
            parsed_data = api_response.get('results', [])
            
            # Check for any errors
            successful_parses = [result for result in parsed_data if result.get('status') == 'success']
            failed_parses = [result for result in parsed_data if result.get('status') == 'error']
            
            if successful_parses:
                messages.success(request, f'Successfully parsed {len(successful_parses)} resume(s)!')
            if failed_parses:
                for failed in failed_parses:
                    messages.error(request, f"Failed to parse {failed.get('filename', 'unknown file')}: {failed.get('message', 'Unknown error')}")
            
        except requests.exceptions.ConnectionError:
            parsed_data = []
            messages.error(request, "Cannot connect to resume parser service. Please make sure the FastAPI server is running.")
        except Exception as e:
            parsed_data = []
            messages.error(request, f"Error communicating with resume parser: {str(e)}")
        
        return render(request, 'home/resumes.html', {
            'parsed_data': parsed_data, 
            'job_descriptions': job_descriptions
        })
    
    # For GET requests, just render the upload form
    return render(request, 'home/resumes.html', {'job_descriptions': job_descriptions})
