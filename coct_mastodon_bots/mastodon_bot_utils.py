import functools
import os

from mastodon import Mastodon


@functools.lru_cache(1)
def init_mastodon_client() -> Mastodon:
    return Mastodon(
        access_token=os.environ["MASTODON_ACCESS_TOKEN"],
        api_base_url='https://botsin.space/'
    )
