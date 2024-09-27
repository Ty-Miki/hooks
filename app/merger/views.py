import os
import subprocess
import zipfile
import shutil
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.shortcuts import render
from werkzeug.utils import secure_filename
import logging
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from .forms import VideoUploadForm

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

def process_videos(short_videos, large_videos):
    logging.info("Starting video processing...")
    
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
    for large_video in tqdm(large_videos, desc="Concatenating with large videos"):
        large_name = os.path.splitext(os.path.basename(large_video))[0]  # Extract the name of the large video without extension
        for short_video, short_name in zip(preprocessed_short_files, short_video_names):
            final_output_name = f"{short_name}_{large_name}.mp4"
            final_output = os.path.join(settings.OUTPUT_FOLDER, final_output_name)
            concatenate_videos([short_video, large_video], final_output)
            final_output_files.append(final_output)
    
    # Clean up temporary files
    for file in preprocessed_short_files:
        os.remove(file)
    
    logging.info("Video processing complete!")
    return final_output_files

def index(request):
    form = VideoUploadForm()
    return render(request, 'merger/index.html', {'form': form})


@require_POST
def upload_files(request):

     # Check if the user has enough credits
    user_profile = request.user.profile
    if user_profile.merge_credits <= 0:
        # You can change the url below to the stripe URL
        # return redirect('hooks:no_credits')  # Redirect to an error page or appropriate view
        return HttpResponse("You don't have enough merge credits, buy and try again!", status=404)
    
    short_videos = request.FILES.getlist('short_videos')
    large_videos = request.FILES.getlist('large_videos')
    
    if not short_videos or not large_videos:
        messages.error(request, 'No selected file')
        print("No selected file")
        return redirect('merger:index')

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
    
    # Save uploaded large videos
    for file in large_videos:
        filename = file.name
        file_path = os.path.join(settings.UPLOAD_FOLDER, filename)
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        large_video_paths.append(file_path)
    # Process videos
    output_files = process_videos(short_video_paths, large_video_paths)

    merge_credits_used = len(short_video_paths)
    if user_profile.merge_credits < merge_credits_used:
        # You can change the url below to the stripe URL
        # return redirect('hooks:no_credits')  # Redirect to an error page or appropriate view
        return HttpResponse("You don't have enough merge credits, buy and try again!", status=404)
    
    user_profile.merge_credits -= merge_credits_used
    user_profile.save()
    logging.info(f"Used {merge_credits_used} merge credits")
    
    if not output_files:
        logging.error("No output files were generated by the video processing function.")
        messages.error(request, 'No output files to zip')
        return redirect('merge:index')

    logging.info(f"Output files to be zipped: {output_files}")

    # Create a zip file of the output videos
    zip_filename = os.path.join(settings.OUTPUT_FOLDER, 'final_videos.zip')

    try:
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for file in output_files:
                if os.path.exists(file):
                    logging.info(f"Adding {file} to zip file.")
                    zipf.write(file, os.path.basename(file))
                else:
                    logging.warning(f"File {file} does not exist and will not be added to the zip file.")
        
        logging.info(f"Zip file created successfully: {zip_filename}")
        
        # Return the zip file for download
        if os.path.exists(zip_filename):
            with open(zip_filename, 'rb') as zip_file:
                response = HttpResponse(zip_file.read(), content_type='application/zip')
                response['Content-Disposition'] = f'attachment; filename={os.path.basename(zip_filename)}'

            # Cleanup: Remove uploaded and output files after sending the response
            shutil.rmtree(settings.UPLOAD_FOLDER, ignore_errors=True)
            os.makedirs(settings.UPLOAD_FOLDER)
            shutil.rmtree(settings.OUTPUT_FOLDER, ignore_errors=True)
            os.makedirs(settings.OUTPUT_FOLDER)
            
            logging.info("Temporary files cleaned up successfully.")
            return response
        else:
            logging.error("Zip file was not created successfully.")
            messages.error(request, 'Failed to create zip file')
            return redirect('merger:index')

    except Exception as e:
        logging.error(f"Failed to create zip file: {e}")
        messages.error(request, 'An error occurred while creating the zip file')
        return redirect('merger:index')