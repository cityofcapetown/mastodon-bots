from coct_mastodon_bots.mastodon_bot_utils import init_mastodon_client


def lambda_handler(event, context):
    record, *_ = event['Records']
    sns_message = record['Sns']['Message']

    mastodon = init_mastodon_client()

    mastodon.status_post(sns_message)

    return {
        'statusCode': 200,
    }