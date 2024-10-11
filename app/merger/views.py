import os
import subprocess
import zipfile
import shutil
import io
from django.conf import settings
from django.http import HttpResponse, FileResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import logging
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from .forms import VideoUploadForm
import threading
from hooks.tools.utils import generate_task_id
from .models import MergeTask

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def preprocess_video(input_file, output_file, reference_resolution=None):
    logging.info(f"Preprocessing video: {input_file}")
    command = ["ffmpeg", "-y", "-i", input_file]
    
    # If reference resolution is provided, scale the video to match it
    if reference_resolution:
        command += ["-vf", f"scale={reference_resolution[0]}:{reference_resolution[1]}:force_original_aspect_ratio=decrease,pad={reference_resolution[0]}:{reference_resolution[1]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p,scale=flags=lanczos"]
    
    # Output to the same format for consistency
    command += ["-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", output_file]
    
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logging.info(result.stdout.decode())
    logging.error(result.stderr.decode())
    logging.info(f"Finished preprocessing: {output_file}")

# Function to concatenate videos using FFmpeg with re-encoding
def concatenate_videos(input_files, output_file):
    logging.info(f"Concatenating videos into: {output_file}")
    
    # Create the concat protocol command
    input_args = []
    for input_file in input_files:
        input_args.extend(["-i", input_file])
    
    # Create FFmpeg command with concat protocol
    command = ["ffmpeg", "-y", "-vsync", "2"] + input_args + [
        "-filter_complex", "concat=n={}:v=1:a=1".format(len(input_files)),
        "-c:v", "libx264", "-preset", "superfast", "-c:a", "aac", output_file
    ]
        
    # Run the command and log stdout/stderr
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logging.info(f"Finished concatenating: {output_file}")

# Function to check the format and resolution of a video file
def check_video_format_resolution(video_file):
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height", "-of", "csv=p=0:s=x", video_file]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode().strip().split('\n')

    # Filter out any empty strings or invalid lines
    resolutions = [line.strip() for line in output if 'x' in line and line.strip()]
    
    # Return the first valid resolution found, split into width and height
    if resolutions:
        try:
            width, height = resolutions[0].split('x')[:2]  # Split and only take the first two values
            return width.strip(), height.strip()
        except ValueError as e:
            logging.error(f"Error parsing resolution: {resolutions[0]} - {e}")
            return None, None
    else:
        logging.error(f"Could not determine resolution for video: {video_file}")
        return None, None  # Or handle the case where no resolution is found

def process_videos(task_id):
    logging.info("Starting video processing...")
    
    # Load short video and large video form merge task
    merge_task = MergeTask.objects.get(task_id=task_id)
    short_videos = merge_task.short_video_path
    large_videos =merge_task.large_video_paths

    # Use the resolution of the first large video as the reference
    reference_resolution = check_video_format_resolution(large_videos[0])
    logging.info(f"Reference resolution for preprocessing: {reference_resolution}")

    # Preprocess short videos to match the large video resolution
    preprocessed_short_files = []
    short_video_names = []
    with ThreadPoolExecutor() as executor:
        futures = []
        for video in short_videos:
            # Extract the name of the short video without extension
            short_name = os.path.splitext(os.path.basename(video))[0]
            short_video_names.append(short_name)
            output_file = os.path.join(settings.OUTPUT_FOLDER, f"preprocessed_{short_name}.mp4")
            futures.append(executor.submit(preprocess_video, video, output_file, reference_resolution))
            preprocessed_short_files.append(output_file)
        for future in futures:
            future.result()  # wait for all threads to complete

    final_output_files = []

    # Concatenate each large video with each preprocessed short video
    with ThreadPoolExecutor() as executor:
        concat_futures = []
        for large_video in tqdm(large_videos, desc="Concatenating with large videos"):
            large_name = os.path.splitext(os.path.basename(large_video))[0]  # Extract the name of the large video without extension
            for short_video, short_name in zip(preprocessed_short_files, short_video_names):
                temp_dict = {}
                final_output_name = f"{short_name}_{large_name}.mp4"
                final_output = os.path.join(settings.OUTPUT_FOLDER, final_output_name)

                # Submit concatenation task to thread pool
                concat_futures.append(executor.submit(concatenate_videos, [short_video, large_video], final_output))

                # Store video details
                video_name = os.path.basename(final_output)
                temp_dict['video_link'] = final_output
                temp_dict['file_name'] = video_name

                final_output_files.append(temp_dict)
        
        # Wait for all concatenation tasks to complete
        for future in concat_futures:
            future.result()  # ensure each concatenation is completed
    
    logging.info("Video processing complete!")
    
    # Update the merge task status
    merge_task.status = 'completed'
    merge_task.video_links = final_output_files
    merge_task.save()

@login_required
def index(request):
    form = VideoUploadForm()
    return render(request, 'merger/index.html', {'form': form})


@require_POST
def upload_files(request):

    task_id = generate_task_id()
    logging.info(f'Merge Task ID generated --> {task_id}')
    
    MergeTask.objects.create(task_id=task_id, status='processing')
    logging.info(f'A Merge Task object created for merge task id --> {task_id}')

    short_videos = request.FILES.getlist('short_videos')
    logging.info(f'Short vids uploaded: {short_videos}')
    large_videos = request.FILES.getlist('large_videos')

    short_video_paths = []
    large_video_paths = []
    
    # Save uploaded short videos
    for file in short_videos:
        filename = file.name
        file_path = os.path.join(settings.UPLOAD_FOLDER, filename)
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        short_video_paths.append(file_path)
    
    logging.info(f'Short video paths: {short_video_paths}')
    # Save uploaded large videos
    for file in large_videos:
        filename = file.name
        file_path = os.path.join(settings.UPLOAD_FOLDER, filename)
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        large_video_paths.append(file_path)

     # Update the merge task video paths

    merge_task = MergeTask.objects.get(task_id=task_id)
    merge_task.short_video_path = short_video_paths
    merge_task.large_video_paths = large_video_paths
    merge_task.save()

    return redirect('merger:processing',
                    task_id=task_id, 
                    )  # Redirect to a processing page after form submission
    

@login_required    
def processing(request, task_id):

     # Check if the user has enough merge credits
    merge_task = MergeTask.objects.get(task_id=task_id)
    user_profile = request.user.profile
    merge_credits_used = len(merge_task.short_video_path)

    if user_profile.merge_credits < merge_credits_used:
        # You can change the url below to the stripe URL
        # return redirect('hooks:no_credits')  # Redirect to an error page or appropriate view
        return HttpResponse("You don't have enough merge credits, buy and try again!", status=404)
    
    thread = threading.Thread(target=process_videos, args=(task_id,))
    thread.start()

    user_profile.merge_credits -= merge_credits_used
    user_profile.save()
    logging.info(f"Used {merge_credits_used} merge credits")

    return render(request, 
                'merger/processing.html',
                {'task_id': task_id})

@login_required
def check_task_status(request, task_id):
    task = get_object_or_404(MergeTask, task_id=task_id)
    
    # Return task status and video links (if processing is completed)
    return JsonResponse({
        'status': task.status,
        'video_links': task.video_links if task.status == 'completed' else None
    })

@login_required 
def processing_successful(request, task_id):
     task = get_object_or_404(MergeTask, task_id=task_id)

     return render(request, 
                'merger/processing_successful.html', 
                {'task_id': task_id,
                'video_links': task.video_links})

@login_required 
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

@login_required 
def download_zip(request, task_id):

    task = get_object_or_404(MergeTask, task_id=task_id)
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
    response['Content-Disposition'] = f'attachment; filename="final_videos.zip"'
    
    # Cleanup: Remove uploaded and output files after sending the response
    shutil.rmtree(settings.UPLOAD_FOLDER, ignore_errors=True)
    os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
    shutil.rmtree(settings.OUTPUT_FOLDER, ignore_errors=True)
    os.makedirs(settings.OUTPUT_FOLDER, exist_ok=True)
            
    logging.info("Temporary files cleaned up successfully.")
    return response