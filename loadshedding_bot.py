from coct_mastodon_bots.mastodon_bot_utils import init_mastodon_client, TOOT_MAX_LENGTH


def lambda_handler(event, context):
    record, *_ = event['Records']
    sns_message = record['Sns']['Message']

    mastodon = init_mastodon_client()

    if len(sns_message) < TOOT_MAX_LENGTH:
        mastodon.status_post(sns_message)
    else:
        print("Toot not sent - too long!")

    return {
        'statusCode': 200,
    }