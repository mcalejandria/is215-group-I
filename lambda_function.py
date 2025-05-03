import boto3
import os
import base64
import uuid
import json
import requests

s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')

IS_LIVE = os.environ.get('IS_LIVE', 'false').lower() == 'true'

suffix = '_LIVE' if IS_LIVE else ''

API_KEY = os.environ[f'OPENAI_API_KEY{suffix}']
API_URL = os.environ[f'OPENAI_API_URL{suffix}']
API_MODEL = os.environ[f'OPENAI_API_MODEL{suffix}']
S3_BUCKET = os.environ[f'BUCKET_NAME{suffix}']

# Enable CORS
CORS_HEADERS = {
    "Content-Type": "text/plain",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,POST"
}

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
        file_name = body.get("filename", f"{uuid.uuid4()}.jpg")
        content_type = body.get("content_type", "image/jpeg")
        image_base64 = body.get("image_base64")

        if not image_base64:
            raise Exception("Missing image data")
        
        #Decode image from form request
        file_data = base64.b64decode(image_base64)

        # Upload to S3 Bucket
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=file_name,
            Body=file_data,
            ContentType=content_type
        )

        # Run AWS Rekognition
        rekog_result = rekognition.detect_labels(
            Image={'S3Object': {'Bucket': S3_BUCKET, 'Name': file_name}},
            MaxLabels=10
        )
        labels = [label['Name'] for label in rekog_result['Labels']]
        label_text = ', '.join(labels)

        # Generate ChatGPT API Payload
        payload = {
            "model": API_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a skilled creative writer, journalist, and documentarian. "
                        "Your task is to generate a blog post in clean HTML format, based on visual labels from an image."
                    )
                },
                {
                    "role": "system",
                    "content": (
                        "Respond only with well-formatted HTML content. "
                        "Do not include explanations, markdown, or any non-HTML elements. "
                        "Avoid using <img> tags — the content should be entirely text-based."
                    )
                },
                {
                    "role": "system",
                    "content": (
                        "The HTML should include a <h1> title, multiple <p> paragraphs, and optionally <h2>/<h3> subheadings "
                        "if appropriate to structure the story."
                    )
                },
                {
                    "role": "user",
                    "content": f"Please write a fun, creative blog story using the following labels as inspiration: {label_text}"
                }
            ]
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        
        response = requests.post(API_URL, headers=headers, json=payload, timeout=20)
        response.raise_for_status() 
        result = response.json()
        blog_story = result['choices'][0]['message']['content']

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": blog_story
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": f"Error: {str(e)}"
        }


# ENVIRONMENT VARIABLE IN LAMBDA

# OPENAI_API_KEY=
# OPENAI_API_URL=https://is215-openai.upou.io/v1/chat/completions
# OPENAI_API_MODEL=gpt-3.5-turbo
# BUCKET_NAME=blog-generator-storage
# IS_LIVE=false|true
# OPENAI_API_KEY_LIVE=
# OPENAI_API_URL_LIVE=https://api.openai.com/v1/chat/completions
# OPENAI_API_MODEL_LIVE=gpt-4-turbo-2024-04-09
        
# LAMBDA LAYER

# arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p312-requests:4
# Python 3.12
