import json

import boto3
import openai

from coct_mastodon_bots.mastodon_bot_utils import init_mastodon_client, TOOT_MAX_LENGTH

SERVICE_ALERT_BUCKET = "coct-service-alerts-bot"
SERVICE_ALERT_PREFIX = "alerts"

CHATGPT_TEMPLATE = """
Please draft a toot about a potential City of Cape Town service outage in a concerned and helpful tone, 
using the details in the following JSON. The "service_area" field refers to the responsible department.

{json_str}

Please keep it under {toot_length} characters. Convert all of the UTC timestamps to SAST by adding 2 hours, and only 
refer to SAST dates and times. Only use the start and end timestamps.
"""

REQUEST_RETRIES = 3
REQUEST_TIMEOUT = 60

LINK_TEMPLATE = "https://d1ylwyvv9r7kb2.cloudfront.net/{prefix_str}/{service_alert_filename}"
TOOT_TEMPLATE = """
{answer_str}

Above content generated automatically - please confirm using: {link_str} 
"""

s3 = boto3.client('s3')


def _chatgpt_wrapper(message):
    rough_token_count = (len(message) // 4) + 256

    last_error = None
    for t in range(REQUEST_RETRIES):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": message},
                ],
                temperature=0.4,
                max_tokens=4097 - rough_token_count,
                timeout=REQUEST_TIMEOUT
            )
            return response['choices'][0]['message']['content']
        except Exception as e:
            print(f"Get {e.__class__.__name__}: {e}")
            last_error = e
    else:
        raise last_error


def lambda_handler(event, context):
    record, *_ = event['Records']
    sns_message = record['Sns']['Message']
    data = json.loads(sns_message)
    print(f"{len(data)=}")

    mastodon = init_mastodon_client()

    for service_alert in data:
        service_alert_filename = f"{service_alert['Id']}.json"

        # Removing a few fields which often confuse ChatGPT
        for field in ('Id', 'publish_date', 'effective_date', 'expiry_date'):
            del service_alert[field]

        # Also, removing any null items
        keys_to_delete = [
            k for k, v in service_alert.items()
            if v is None
        ]

        for k in keys_to_delete:
            del service_alert[k]

        # Forming content
        link_str = LINK_TEMPLATE.format(prefix_str=SERVICE_ALERT_PREFIX,
                                        service_alert_filename=service_alert_filename)

        # Trying to get text from ChatGPT
        try:
            gpt_template = CHATGPT_TEMPLATE.format(json_str=json.dumps(service_alert),
                                                   toot_length=TOOT_MAX_LENGTH - len(link_str))
            gpt_template += (
                " . Encourage the use of the request_number value when contacting the City"
                if "request_number" in service_alert else ""
            )

            message = _chatgpt_wrapper(gpt_template)

            # Forming the final toot
            toot = TOOT_TEMPLATE.format(answer_str=message,
                                        link_str=link_str)

            assert len(toot) <= TOOT_MAX_LENGTH, "toot is too long!"

        except Exception as e:
            # bail out with a sensible error, so that this can be retried
            return {
                'statusCode': 500,
                'data': {
                    'error': e.__class__.__name__,
                    'message': str(e)
                }
            }

        # Backing up source data and toot to S3
        service_alert["toot"] = toot
        service_alert_json = json.dumps(service_alert)

        s3.put_object(
            Body=service_alert_json,
            Bucket=SERVICE_ALERT_BUCKET,
            Key=SERVICE_ALERT_PREFIX + "/" + service_alert_filename,
            ContentType='application/json'
        )

        # All done, posting to Mastodon
        mastodon.status_post(toot)

    return {
        'statusCode': 200,
    }
