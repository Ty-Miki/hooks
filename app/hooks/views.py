import logging
import tempfile
import os

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, FileResponse

from .forms import HookForm

from .tools.utils import generate_task_id
from .tools.processor import process_files

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import Task

import threading

import zipfile
import io

import requests
from .tools.spreadsheet_extractor import fetch_google_sheet_data



logging.basicConfig(level=logging.DEBUG)

def background_processing(task_id, user_profile):

    try:
        temp_dir = tempfile.mkdtemp(prefix=f"task_{task_id}_")
        logging.info(f'temp_dir ->, {temp_dir}')

        # Process the files and get video links and credits used
        video_links, credits_used = process_files(temp_dir, task_id)
        logging.info(f"{video_links}: Video Links")
        logging.info(f'{credits_used} Credits Used.')

        # Reduce user credits and save profile
        user_profile.credits -= credits_used
        user_profile.save()

        # Update the task status
        task = Task.objects.get(task_id=task_id)
        task.status = 'completed'
        task.video_links = video_links
        task.save()

    except Exception as e:
        logging.error(f"Error during background processing: {e}")

@login_required
def upload_hook(request):
    
    hook = None
    if request.method == 'POST':
        task_id = generate_task_id()
        logging.info(f'Task ID generated --> {task_id}')

        Task.objects.create(task_id=task_id, status='processing')
        logging.info(f'A Task object created for task id --> {task_id}')

        parallel_processing = True

        form = HookForm(request.POST, request.FILES)
        if form.is_valid():
            hook = form.save(commit=False)
            hook.task_id = task_id
            hook.parallel_processing = parallel_processing
            hook.save()
            
            return redirect('hooks:processing', task_id=task_id)  # Redirect to a processing page after form submission
    else:
        form = HookForm()

    return render(request, 'upload_hook.html', {'form': form, 'hook': hook})


@login_required
def processing(request, task_id):

     # Check if the user has enough credits
    user_profile = request.user.profile
    if user_profile.credits <= 0:
        # You can change the url below to the stripe URL
        # return redirect('hooks:no_credits')  # Redirect to an error page or appropriate view
        return HttpResponse("You don't have enough credits, buy and try again!", status=404)
    
    thread = threading.Thread(target=background_processing,
                              args=(task_id, user_profile))
    thread.start()
    
    return render(request, 
                'processing.html', 
                {'task_id': task_id,})
    

@login_required
def check_task_status(request, task_id):
    task = get_object_or_404(Task, task_id=task_id)
    
    # Return task status and video links (if processing is completed)
    return JsonResponse({
        'status': task.status,
        'video_links': task.video_links if task.status == 'completed' else None
    })

def processing_successful(request, task_id):
     task = get_object_or_404(Task, task_id=task_id)

     return render(request, 
                'processing_successful.html', 
                {'task_id': task_id,
                'video_links': task.video_links})    

def download_video(request, videopath):
    # Decode the path
    # videopath = os.path.join(settings.BASE_DIR.parent, videopath)

    
    # Check if the video file exists
    if not os.path.exists(videopath):
        return HttpResponse("Video not found", status=404)

    # Return the file as a download
    response = FileResponse(open(videopath, 'rb'), content_type='video/mp4')
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(videopath)}"'
    
    return response

def download_zip(request, task_id):

    task = get_object_or_404(Task, task_id=task_id)
    videos = task.video_links

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        for idx, video in enumerate(videos):
            if os.path.exists(video['video_link']):
                file_name = os.path.basename(video['video_link'])

                # Add the file to the zip archive
                zip_file.write(video['video_link'], file_name)

    zip_buffer.seek(0)

    # Create a response with the zip file for downloading
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="hook_videos.zip"'

    return response

@login_required
def validate_google_sheet_link(request):
    if request.method == 'POST':
        google_sheets_link = request.POST.get('google_sheets_link')
        
        try:
            # Attempt to fetch the Google Sheets data for validation
            fetch_google_sheet_data(google_sheets_link)
            return JsonResponse({'valid': True})
        except ValueError as ve:
            return JsonResponse({'valid': False, 'error': str(ve)})
        except Exception as e:
            return JsonResponse({'valid': False, 'error': str(e)})
    
    return JsonResponse({'valid': False, 'error': 'Invalid request method.'})

def validate_api_key(request):
    if request.method == 'POST':
        api_key = request.POST.get('eleven_labs_api_key', '')
        voice_id = request.POST.get('voice_id') # Replace with a valid default voice ID to test the API key

        # Try making a request to Eleven Labs API to validate the key
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": api_key}
        data = {
            "text": "Test voice synthesis",  # Small test text to avoid large requests
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        try:
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                return JsonResponse({'valid': True})
            elif response.status_code == 401:
                error_detail = response.json().get('detail', {})
                if 'status' in error_detail and error_detail['status'] == 'quota_exceeded':
                    return JsonResponse({
                        'valid': False, 
                        'error': f"Quota Exceeded: {error_detail.get('message', 'Insufficient credits')}"
                    })
                else:
                    return JsonResponse({'valid': False, 'error': "Invalid API Key"})
            else:
                return JsonResponse({'valid': False, 'error': f"API Request Failed With Status Code {response.status_code}"})
        except requests.exceptions.RequestException as e:
            return JsonResponse({'valid': False, 'error': 'Error Connecting To Eleven Labs API'})