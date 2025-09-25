# lambda_handler.py

import json
from core import process_geospatial_job

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

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(result)
        }

    except Exception as e:
        print("Exception occurred:", str(e))
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({"error": str(e)})
        }