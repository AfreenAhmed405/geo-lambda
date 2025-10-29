# lambda_handler.py

import json
import boto3
from core import process_geospatial_job

sns = boto3.client("sns")
TOPIC_ARN = "arn:aws:sns:us-east-1:721308714000:processGeoDataComplete"

def lambda_handler(event, context):
    print("==> Lambda function started")

    try:
        body = event.get("body")
        if isinstance(body, str):
            job_input = json.loads(body)
        elif isinstance(body, dict):
            job_input = body
        else:
            job_input = event

        print("Parsed body:", json.dumps(job_input))

        result = process_geospatial_job(job_input)

        message = {
            "status": "COMPLETED",
            "request_id": job_input.get("request_id"),
            "results": result
        }
        
        sns.publish(
            TopicArn=TOPIC_ARN,
            Message=json.dumps(message),
            Subject=f"Geo Job {job_input.get('request_id')} Completed"
        )

        print("==> Published SNS notification successfully")

    except Exception as e:
        print("Exception occurred:", str(e))