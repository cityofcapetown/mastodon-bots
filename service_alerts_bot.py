from datetime import datetime, timedelta
import json
import typing

import boto3
import openai
import requests

from coct_mastodon_bots.mastodon_bot_utils import init_mastodon_client, TOOT_MAX_LENGTH

SERVICE_ALERT_BUCKET = "coct-service-alerts-bot"
SERVICE_ALERT_PREFIX = "alerts"

CHATGPT_TEMPLATE = """
Please draft a toot about a potential City of Cape Town service outage or update on an outage in a concerned and 
helpful tone, using the details in the following JSON. The "service_area" field refers to the responsible department.

{json_str}

Keep it strictly under {toot_length} chars in length. Only return the content of the toot.
"""

REQUEST_RETRIES = 3
REQUEST_TIMEOUT = 60

ALERTS_TEMPLATE = "https://service-alerts.cct-datascience.xyz/alerts/{alert_id}.json"
TOOT_TEMPLATE = """{answer_str}

Content generated automatically from {link_str}"""

s3 = boto3.client('s3')
http_session = requests.Session()


def _convert_to_sast_str(utc_str: str) -> str:
    return (
            datetime.strptime(utc_str[:-5], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=2)
    ).strftime("%Y-%m-%dT%H:%M:%S") + "+02:00"


def _chatgpt_wrapper(message: str, max_response_length: int) -> str:
    rough_token_count = len(message) // 4 + 256
    temperature = 0.2

    last_error = None
    for t in range(REQUEST_RETRIES):
        response_message = None
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": message},
                ],
                temperature=temperature,
                max_tokens=4097 - rough_token_count,
                timeout=REQUEST_TIMEOUT
            )
            response_message = response['choices'][0]['message']['content']

            # Checking response length is right
            assert len(response_message) <= max_response_length, "message is too long!"

            return response_message

        except Exception as e:
            print(f"Got {e.__class__.__name__}: {e}")
            print(f"try: {t + 1}/3")
            print(f"{response_message=}")

            if isinstance(e, openai.error.InvalidRequestError):
                print("increasing token count")
                rough_token_count *= 1.2
                rough_token_count = int(rough_token_count)
            else:
                temperature += 0.2

            last_error = e
    else:
        raise last_error


def _generate_toot_from_chatgpt(alert: typing.Dict, alert_id: str, alert_filename: str) -> str:
    # Removing a few fields which often confuse ChatGPT
    for field in ('Id', 'publish_date', 'effective_date', 'expiry_date', 'tweet_text', 'toot_text'):
        del alert[field]

    # Also, removing any null items
    keys_to_delete = [
        k for k, v in alert.items()
        if v is None
    ]

    for k in keys_to_delete:
        del alert[k]

    # converting the timezone values to SAST
    for ts in ("start_timestamp", "forecast_end_timestamp"):
        alert[ts] = _convert_to_sast_str(alert[ts])

    # Trying to get text from ChatGPT
    try:
        gpt_template = CHATGPT_TEMPLATE.format(json_str=json.dumps(alert), )
        gpt_template += (
            " . Encourage the use of the request_number value when contacting the City"
            if "request_number" in alert else ""
        )

        # Getting tweet text from ChatGPT
        message = _chatgpt_wrapper(gpt_template, TOOT_MAX_LENGTH)

    except Exception as e:
        # Failing with a sensible message
        print(f"Failed to generate toot text for '{alert_id}' because {e.__class__.__name__}")
        message = None

    return message


def lambda_handler(event, context):
    record, *_ = event['Records']
    sns_message = record['Sns']['Message']
    data = json.loads(sns_message)
    print(f"{len(data)=}")

    mastodon = init_mastodon_client()

    for service_alert in data:
        service_alert_id = service_alert['Id']
        service_alert_filename = f"{service_alert_id}.json"

        # try load message from v1 endpoint
        message = None
        service_alert_path = ALERTS_TEMPLATE.format(alert_id=service_alert_id)
        if requests.head(service_alert_path).status_code == 200:
            service_alert_data = http_session.get(service_alert_path).json()
            message = service_alert_data.get("toot_text", None)
            if message:
                print("Using cptgpt text")

        # Falling back to ChatGPT if there isn't anything from CPTGPT
        if message is None:
            message = _generate_toot_from_chatgpt(service_alert, service_alert_id, service_alert_filename)

        # Generating final toot
        toot = TOOT_TEMPLATE.format(
            answer_str=message if message else "Content failed to generate. Please consult link below",
            link_str=service_alert_path
        )

        # All done, posting to Mastodon
        mastodon.status_post(toot)

    return {
        'statusCode': 200,
    }
