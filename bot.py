# Built-in imports
import logging
import os
import random
import time

import tweepy
from ttp import ttp

from dadatelekom import gen_gif

# Custom imports
try:
    import config
except:
    import config_example as config


# Global variable init
TWEET_LENGTH = 140
IMAGE_URL_LENGTH = 23
MAX_TWEET_TEXT_LENGTH = TWEET_LENGTH - IMAGE_URL_LENGTH - 1
DOTS = '...'
BACKOFF = 0.5 # Initial wait time before attempting to reconnect
MAX_BACKOFF = 300 # Maximum wait time between connection attempts
MAX_IMAGE_SIZE = 3072 * 1024 # bytes
USERNAME = config.twitter['user']

# BLACKLIST
# Do not respond to queries by these accounts
BLACKLIST = [
    'pixelsorter',
    'Lowpolybot'
]


logging.basicConfig(filename='logger.log',
                    level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Twitter client
auth = tweepy.OAuthHandler(config.twitter['key'], config.twitter['secret'])
auth.set_access_token(config.twitter['access_token'],
    config.twitter['access_token_secret'])
api = tweepy.API(auth)
# Tweet parser
parser = ttp.Parser()
# backoff time
backoff = BACKOFF

def parse_tweet(tweet_from, tweet_text):
    query = tweet_text[tweet_text.index('@%s' % USERNAME) + len('@%s' % USERNAME) + 1:]
    if query is None: query = ""

    result = parser.parse(tweet_text)
    tagged_users = result.users + [tweet_from]
    tagged_hashtags = result.tags
    tagged_urls = result.urls

    for user in tagged_users:
        query = query.replace('@%s' % user, '')
    for tag in tagged_hashtags:
        query = query.replace('#%s' % tag, '')
    for url in tagged_urls:
        query = query.replace('%s' % url, '')

    logging.info('parse_tweet: %s--%s' % (tagged_users, query))
    return tagged_users, query.strip()


def generate_reply_tweet(users, search_term):
    reply = '%s %s' % (search_term, ' '.join(['@%s' % user for user in users if user != USERNAME]))
    if len(reply) > MAX_TWEET_TEXT_LENGTH:
        reply = reply[:MAX_TWEET_TEXT_LENGTH - len(DOTS) - 1] + DOTS

    logging.info('generate_reply_tweet: %s' % reply)
    return reply


class StreamListener(tweepy.StreamListener):

    def on_status(self, status):
        global backoff

        backoff = BACKOFF
        # Collect logging and debugging data
        tweet_id = status.id
        tweet_text = status.text
        tweet_from = status.user.screen_name

        if tweet_from != USERNAME and tweet_from not in BLACKLIST and not hasattr(status, 'retweeted_status'):
            logging.info('on_status: %s--%s' % (tweet_id, tweet_text))

            # Parse tweet for search term
            tagged_users, search_term = parse_tweet(tweet_from, tweet_text)

            if search_term:
                # Search and save the image
                search_term = gen_gif(search_term)
                filename = 'output.gif'
                if filename:
                    # Generate and send the the reply tweet
                    reply_tweet = generate_reply_tweet(tagged_users, search_term)
                    reply_status = api.update_with_media(filename=filename,
                        status=reply_tweet, in_reply_to_status_id=tweet_id)

                    logging.info('on_status_sent: %s %s' % (
                        reply_status.id_str, reply_status.text))
                else:
                    logging.info('on_status_failed: No images for %s' % search_term)
            else:
                logging.info('on_status_failed: No search terms')

    def on_error(self, status_code):
        global backoff
        logging.info('on_error: %d' % status_code)

        if status_code == 420:
            backoff = backoff * 2
            logging.info('on_error: backoff %s seconds' % backoff)
            time.sleep(backoff)
            return True

stream_listener = StreamListener()
stream = tweepy.Stream(auth=api.auth, listener=stream_listener)
try:
    stream.userstream(_with='user', replies='all')
except Exception as e:
    logging.warn('stream_exception', e)
    raise e
