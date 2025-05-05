import boto3
import os
import base64
import uuid
import json
import requests

# Initialize libraries
s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')

IS_LIVE = os.environ.get('IS_LIVE', 'false').lower() == 'true'
suffix = '_LIVE' if IS_LIVE else ''

# Get environment variables safely
try:
    API_KEY = os.environ[f'OPENAI_API_KEY{suffix}']
    API_URL = os.environ[f'OPENAI_API_URL{suffix}']
    API_MODEL = os.environ[f'OPENAI_MODEL{suffix}']
    S3_BUCKET = os.environ['BUCKET_NAME']
except KeyError as e:
    print(f"Missing environment variable: {e}")
    raise

# Feed CORS headers
CORS_HEADERS = {
    "Content-Type": "text/plain",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,POST"
}

def lambda_handler(event, context):
    try:
        # Parse and validate input
        try:
            if 'body' not in event:
                raise ValueError("Missing 'body' in event.")
            body = json.loads(event['body'])
        except Exception as e:
            print(f"Error parsing JSON body: {e}")
            raise

        file_name = body.get("filename", f"{uuid.uuid4()}.jpg")
        content_type = body.get("content_type", "image/jpeg")
        image_base64 = body.get("image_base64")
        tone = body.get("tone", "casual")  # Default to casual tone if not provided

        if not image_base64:
            raise ValueError("Missing image data in request.")

        # Decode base64 image
        try:
            file_data = base64.b64decode(image_base64)
        except Exception as e:
            print(f"Error decoding base64 image: {e}")
            raise

        # Upload image to S3
        try:
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=file_name,
                Body=file_data,
                ContentType=content_type
            )
        except Exception as e:
            print(f"Error uploading to S3: {e}")
            raise

        # Run Rekognition
        try:
            rekog_result = rekognition.detect_labels(
                Image={'S3Object': {'Bucket': S3_BUCKET, 'Name': file_name}},
                MaxLabels=10
            )
            labels = [label['Name'] for label in rekog_result['Labels']]
            label_text = ', '.join(labels)
        except Exception as e:
            print(f"Error with Rekognition: {e}")
            raise

        # Prepare payload for OpenAI
        payload = {
            "model": API_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                         "Hi chat, you are either an elementary school news writer, highschool or college campus journalist, OR a veteran journalist and has been in the industry already for more than half of your life. You are a decorated news writer, skilled creative writer, and a documentarian. With this experience and credibility, you are tasked to write news articles or editorials based on an image. You are expected follow the news writing structure, and cite credible links or resources. With editorial you can do that as well. Always output a news article by default."
                        "Additionally, your task is to generate your writing in clean HTML format, blog post like, based on visual labels from an image."
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
                    "content": f"Remember, you are either an elementary, a high school, a college campus journalist OR veteran journalist and writer. Please write a good news article using the following labels as inspiration: {label_text}. If you are {tone}, the story should be written in a {tone} tone."
                }
            ]
        }

        # Call OpenAI API
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}"
            }
            response = requests.post(API_URL, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            result = response.json()

            if 'choices' not in result or not result['choices']:
                raise ValueError("Invalid response from OpenAI API.")

            blog_story = result['choices'][0]['message']['content']
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            raise

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": blog_story
        }

    except Exception as e:
        print(f"Unhandled error: {e}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": f"Error: {str(e)}"
        }

# ENVIRONMENT VARIABLE IN LAMBDA

# OPENAI_API_KEY=
# OPENAI_API_URL=https://is215-openai.upou.io/v1/chat/completions
# OPENAI_MODEL=gpt-3.5-turbo
# BUCKET_NAME=blog-generator-storage
# IS_LIVE=false|true
# OPENAI_API_KEY_LIVE=
# OPENAI_API_URL_LIVE=https://api.openai.com/v1/chat/completions
# OPENAI_MODEL_LIVE=gpt-4-turbo-2024-04-09
        
# LAMBDA LAYER

# arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p312-requests:4
# Python 3.12
