# Written by Jan Zbirovsky

import os
import time
import pandas as pd
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import ollama
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def check_models(OLLAMA_HOST):
    client = ollama.Client(host=OLLAMA_HOST)
    available_models = client.list()
    print("Available models:", available_models)
    return client

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
    
    if not text:
        text = extract_text_with_ocr(pdf_path)
    
    return text

def extract_text_with_ocr(pdf_path):
    text = ""
    try:
        images = convert_from_path(pdf_path)
        for image in images:
            text += pytesseract.image_to_string(image) + "\n"
    except Exception as e:
        print(f"Error extracting text with OCR from {pdf_path}: {e}")
    
    return text

def summarize_text(text, client):
    prompt = f"""
    You are an AI that extracts tasks and due dates from text. 
    
    ## Instructions:
    - Translate everything into Czech language
    - Identify all tasks and their due dates from the given text.
    - The output format must strictly follow this pattern: 
      **"YYYY-MM-DD, Task description"**
    - Each task must be on a new line.
    - Avoid any other unnecessary comments, spaces, quotes, brackets, etc.
    - If there is no specified day in the month use always the first day of the month.
    
    ## Examples:
    
    ### **Example 1:**
    #### **Input:**
    "We need to submit the financial report by March 15, 2024. Also, don't forget the team meeting on April 2, 2024."
    
    #### **Output:**
    ```
    2024-03-15, Submit the financial report
    2024-04-02, Attend the team meeting
    ```
    
    ### **Example 2:**
    #### **Input:**
    "The software release is scheduled for June 10, 2024, and the security audit must be completed by June 5, 2024."
    
    #### **Output:**
    ```
    2024-06-05, Complete the security audit
    2024-06-10, Release the software
    ```
    
    ### **Example 3:**
    #### **Input:**
    "I have to organize team building in March 14 2026. Summer camp is planned in August 10 2025."
    
    #### **Output:**
    ```
    2026-03-14, Team building
    2025-08-10, Summer camp
    ```
    ---
    
    ### **Now process the following text:**
    {text[:SIZE_LIMIT]}
    """
    
    # REMOTELY RUNNING SERVER
    #client = ollama.Client(host=OLLAMA_HOST)
    response = client.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
    
    # LOCALLY RUNNING SERVER
    #response = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
    
    return response['message']['content']

def log_document(pdf_path, summary_lst):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    print(timestamp)
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=['timestamp', 'document', 'summary'])
        df.to_csv(CSV_FILE, index=False)
    
    df = pd.read_csv(CSV_FILE)
    if 'document' not in df.columns:
        df = pd.DataFrame(columns=['timestamp', 'document', 'summary'])
    
    for summary in summary_lst:
        df.loc[len(df)] = [timestamp, os.path.basename(pdf_path), summary]
    
    # save all to our CSV file
    df.to_csv(CSV_FILE, index=False)
    pass

# Check the folder for new coming PDF's
class PDFHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith('.pdf'):
            return
        
        pdf_path = event.src_path
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
            if 'document' in df.columns and os.path.basename(pdf_path) in df['document'].values:
                return
        
        client = check_models(OLLAMA_HOST)
        
        print(f"Processing new PDF: {pdf_path}")
        text = extract_text_from_pdf(pdf_path)
        summary = summarize_text(text, client)
        
        # post-processing & debugging
        summary_lst = summary.split('\n')
        # print(summary_lst)
        
        log_document(pdf_path, summary_lst)
        print(f"Logged: {pdf_path}")

if __name__ == '__main__':
    event_handler = PDFHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=False)
    observer.start()
    print(f"Watching folder: {WATCH_FOLDER}")
    try:
        while True:
            time.sleep(1000)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# Set params
SIZE_LIMIT = 10000
WATCH_FOLDER = r'<folder_path>'
CSV_FILE = r'<full_path_to_csv>' # FIle will be created, if not existing
OLLAMA_HOST = 'http://localhost:11434'  # Update with the correct IP when running remotely

# Ollama models
# Model has to be pulled first ...
#MODEL = 'llama3.2'
#MODEL = 'mistral:latest'
MODEL = 'gemma3:1b'
#MODEL = 'deepseek-r1:14b'

def check_models(OLLAMA_HOST):
    client = ollama.Client(host=OLLAMA_HOST)
    available_models = client.list()
    print("Available models:", available_models)
    
    return client

# Use pdfplumber to get all text information
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
    
    if not text:
        text = extract_text_with_ocr(pdf_path)
    
    return text

# Use pytesseract for OCR
def extract_text_with_ocr(pdf_path):
    text = ""
    try:
        images = convert_from_path(pdf_path)
        for image in images:
            text += pytesseract.image_to_string(image) + "\n"
    except Exception as e:
        print(f"Error extracting text with OCR from {pdf_path}: {e}")
    return text

# Here is the heart of our agent = description of tasks
def summarize_text(text, client):
    prompt = f"""
    You are an AI that extracts tasks and due dates from text. 

    ## Instructions:
    - Translate everything into Czech language
    - Identify all tasks and their due dates from the given text.
    - The output format must strictly follow this pattern:  
      **"YYYY-MM-DD, Task description"**
    - Each task must be on a new line.
    - Avoid any other unnecessary comments, spaces, quotes, brackets, etc.
    - If there is no specified day in the month use always the first day of the month.

    ## Examples:

    ### **Example 1:**
    #### **Input:**
    "We need to submit the financial report by March 15, 2024. Also, don't forget the team meeting on April 2, 2024."

    #### **Output:**
    ```
    2024-03-15, Submit the financial report
    2024-04-02, Attend the team meeting
    ```

    ### **Example 2:**
    #### **Input:**
    "The software release is scheduled for June 10, 2024, and the security audit must be completed by June 5, 2024."

    #### **Output:**
    ```
    2024-06-05, Complete the security audit
    2024-06-10, Release the software
    ```

    ### **Example 3:**
    #### **Input:**
    "I have to organize team building in March 14 2026. Summer camp is planned in August 10 2025."

    #### **Output:**
    ```
    2026-03-14, Team building
    2025-08-10, Summer camp
    ```
    ---

    ### **Now process the following text:**
    {text[:SIZE_LIMIT]}
    """

    # REMOTELY RUNNING SERVER
    #client = ollama.Client(host=OLLAMA_HOST)
    response = client.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])

    # LOCALLY RUNNING SERVER
    #response = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
        
    return response['message']['content']

def log_document(pdf_path, summary_lst):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    print(timestamp)

    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=['timestamp', 'document', 'summary'])
        df.to_csv(CSV_FILE, index=False)
    
    df = pd.read_csv(CSV_FILE)
    if 'document' not in df.columns:
        df = pd.DataFrame(columns=['timestamp', 'document', 'summary'])
    
    for summary in summary_lst:
        df.loc[len(df)] = [timestamp, os.path.basename(pdf_path), summary]
        
    # save all to our CSV file
    df.to_csv(CSV_FILE, index=False)
    pass

# Check the folder for new coming PDF's
class PDFHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith('.pdf'):
            return
        
        pdf_path = event.src_path
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
            if 'document' in df.columns and os.path.basename(pdf_path) in df['document'].values:
                return
        
        client = check_models(OLLAMA_HOST)
        
        print(f"Processing new PDF: {pdf_path}")
        text = extract_text_from_pdf(pdf_path)
        summary = summarize_text(text, client)

        # post-processing & debugging
        summary_lst = summary.split('\n')
        # print(summary_lst)

        log_document(pdf_path, summary_lst)
        print(f"Logged: {pdf_path}")

if __name__ == '__main__':
    event_handler = PDFHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=False)
    observer.start()
    print(f"Watching folder: {WATCH_FOLDER}")
    try:
        while True:
            time.sleep(1000)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
