
# Written by Jan Zbirovsky

import os
import time
import pandas as pd
from pdf2image import convert_from_path
import ollama
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import io
import json
import traceback

# image description relevant libs
import logging
import fitz # This one we install as 'pip install PyMuPDF'
import base64
from pathlib import Path
from PIL import Image

from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional


# Set params
SIZE_LIMIT = 1 # Not used yet
WATCH_FOLDER = r'<folder_path>'
CSV_FILE = r'<full_path_to_csv_file>' # File will be created, if not existing
OLLAMA_HOST = 'http://localhost:11434'  # Update with the correct IP when running remotely

# Ollama models
# image analysis = 'llava' or 'llava-llama3:latest'
MODEL = 'llava:7b'
#MODEL = 'gemma3:1b'
#MODEL = 'llava-llama3' #not pulled yet
#MODEL = 'gemma3:4b'
#MODEL = 'qwen3:0.6b'

def check_models(OLLAMA_HOST):
    client = ollama.Client(host=OLLAMA_HOST)
    available_models = client.list()
    available_models_lst =  available_models
    print("Available models:")
    print(available_models_lst)
    print('')
        
    return client

def _extract_images_from_pdf(pdf_path: Path) -> List[Dict]:
    """
    Extract images from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of dictionaries containing image data and page numbers
    """
    logging.basicConfig(level=logging.DEBUG)
    #logging.basicConfig(level=logging.ERROR)
    
    logger = logging.getLogger(__name__)
    
    extracted_images = []
    
    try:
        # Validate file existence
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file does not exist: {pdf_path}")
            return []

        # Check file permissions
        if not os.access(pdf_path, os.R_OK):
            logger.error(f"No read permissions for PDF: {pdf_path}")
            return []

        # File size check
        file_size = os.path.getsize(pdf_path)
        logger.info(f"PDF file size: {file_size} bytes")
        
        if file_size == 0:
            logger.error("PDF file is empty")
            return []

        # Attempt to open PDF
        try:
            doc = fitz.open(pdf_path)
            logger.info(f"Successfully opened PDF: {pdf_path}")
            logger.info(f"Total pages: {len(doc)}")

            # Image extraction diagnostics
            total_images = 0
            for page_num, page in enumerate(doc, 1):
                
                try:
                    image_list = page.get_images(full=True)
                    page_images = len(image_list)
                    total_images += page_images
                    
                    if page_images > 0:
                        logger.info(f"Page {page_num}: {page_images} images found")
                        
                        # Optional: Additional image diagnostics
                        for img_index, img_info in enumerate(image_list, 1):
                            xref = img_info[0]
                            try:
                                base_image = doc.extract_image(xref)
                                
                                # Get image data
                                image_bytes = base_image.get("image")
                                image_ext = base_image.get("ext", "png")
                                                
                                # Convert to PIL Image for consistent handling
                                pil_image = Image.open(io.BytesIO(image_bytes))
                                
                                # Convert to PNG for consistent format
                                png_buffer = io.BytesIO()
                                pil_image.save(png_buffer, format="PNG")
                                png_data = png_buffer.getvalue()
                                    
                                # Base64 encode for debugging and transmission
                                base64_image = base64.b64encode(png_data).decode('utf-8')
                                
                                try:
                                    extracted_images.append({
                                        'page_number': page_num + 1,
                                        'image_number': img_index + 1,
                                        'base64_image': base64_image,
                                        'image_format': image_ext
                                    })
                                except Exception as e:
                                    logger.error(f"Error processing image {img_index} on page {page_num + 1}: {str(e)}")
                                    continue
                                
                                
                                logger.info(f"  Image {img_index}: {len(base_image['image'])} bytes")
                            except Exception as img_extract_err:
                                logger.error(f"  Failed to extract image {img_index}: {img_extract_err}")
                    
                except Exception as page_err:
                    logger.error(f"Error processing page {page_num}: {page_err}")

            logger.info(f"Total images found: {total_images}")
            doc.close()
            return extracted_images

        except Exception as open_err:
            logger.error(f"Error opening PDF: {open_err}")
            logger.error(traceback.format_exc())
            return []

    except Exception as general_err:
        logger.error(f"Unexpected error: {general_err}")
        logger.error(traceback.format_exc())
        return []


def image_description(images_arr, client):
    
    
    # REMOTELY RUNNING SERVER
    # Check available models (debugging step)   
    #client = ollama.Client(host=OLLAMA_HOST)
    
    #if len(images_arr) == 0:
    #    return ['No images found in the PDF']
    
    #print('Image array:')
    #print(type(images_arr))
    #print(images_arr)
    
    image_desc = []
    
    if (len(images_arr) == 0):
        images_arr.append('No images found in the PDF')    
    #    return images_arr
        
    for image in images_arr:
        
        # Convert image to bytes what's expected by 'llava' - HEX coversion comes later
        #img_byte_arr = io.BytesIO()
        #img.save(img_byte_arr, format='PNG')
        #img_byte_arr = img_byte_arr.getvalue()
        #print(img_byte_arr)
        
        prompt = """
                    Provide simply a precise, concise description of this image. Focus on key visual elements and main subject. Think twice before you reply. 
                    Use ten words without commas. Don't add any other comment than requested.
                """

        messages = [
            {"role": "system", 
            "content": "You are an image description assistant. Describe images directly and concisely. No thinking process, no <think> tags, just the description."
            },
            {'role': 'user',
            'content': prompt, 
            'images': [image['base64_image']]
            }
        ]

        response = client.chat( model=MODEL, 
                                messages=messages)
        
        image_desc.append(response['message']['content'].strip())
        
        
    return image_desc

def log_to_csv(pdf_path, summary_lst):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    print(timestamp)

    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=['timestamp', 'document', 'image', 'summary'])
        df.to_csv(CSV_FILE, index=False)
    
    df = pd.read_csv(CSV_FILE)
    if 'document' not in df.columns:
        df = pd.DataFrame(columns=['timestamp', 'document', 'image', 'summary'])
    
    for idx, summary in enumerate(summary_lst):
        df.loc[len(df)] = [timestamp, os.path.basename(pdf_path), idx+1, summary]
        
    # save all to our CSV file
    df.to_csv(CSV_FILE, index=False)
    pass

# Check the folder for new coming PDF's
class PDFImageHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith('.pdf'):
            return
        
        pdf_path = event.src_path
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
            if 'document' in df.columns and os.path.basename(pdf_path) in df['document'].values:
                return
                
        print(f"Processing new PDF: {pdf_path}")
        images = _extract_images_from_pdf(pdf_path)
        #print(images)
        
        summary = image_description(images, client)

        # post-processing & debugging
        #summary_lst = summary.split('\n')
        print(summary)
        print('\n\n')
        
        # save to CSV
        log_to_csv(pdf_path, summary)
        print(f"Logged: {pdf_path}")

if __name__ == '__main__':
    
    # list available models
    print('Checking available models ...')
    client = check_models(OLLAMA_HOST)
    
    event_handler = PDFImageHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=False)
    observer.start()
    print(f"Watching folder: {WATCH_FOLDER}")
    try:
        while True:
            time.sleep(200)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()






















