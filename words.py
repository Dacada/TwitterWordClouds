#!/bin/env python3
# -*- coding: utf-8 -*-

import random
import string
import time
from datetime import datetime
import json
import argparse
import traceback
import tweepy
import numpy as np
from PIL import Image
import nltk
from nltk.corpus import words, stopwords
from wordcloud import WordCloud, ImageColorGenerator


class MyStreamListener(tweepy.StreamListener):
    def __init__(self, target_word, time_limit, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_word = target_word
        self.words = {}
        self.start = None
        self.time_limit = time_limit

    def on_connect(self):
        print('Connected')
        if self.start is None:
            self.start = time.time()
            print(f"Started collecting Tweeter data on: {str(datetime.now())}")

    def on_status(self, status):
        if not status.truncated:
            text = status.text
        else:
            text = status.extended_tweet['full_text']
        if text is not None:
            all_tokens = nltk.word_tokenize(text)
            filter_tokens = set(
                word
                for word in (word.lower() for word in all_tokens)
                if word != self.target_word and
                word in words.words() and
                word not in stopwords.words('english') and
                word not in stopwords.words('french') and
                word not in stopwords.words('spanish') and
                word != 'like'  # nltk doesn't think this is a stopword?
            )

            for token in filter_tokens:
                v = self.words.setdefault(token, 0)
                self.words[token] = v + 1

        self.print_status()
        finished = self.finished()
        if finished:
            print("Finished collecting Tweeter data on: "
                  f"{str(datetime.now())}")
        return not finished

    def on_error(self, status_code):
        if status_code == 420:
            return True
        return False

    def finished(self):
        if self.start is None:
            return False
        time_passed = time.time() - self.start
        return time_passed >= self.time_limit

    def print_status(self):
        time_passed = time.time() - self.start
        progress = time_passed/self.time_limit
        percent = progress * 100
        print(f'{percent:.2f}%')


def get_api(config_file):
    config = json.load(config_file)

    auth = tweepy.OAuthHandler(
        config['api-key'], config['api-secret'])
    auth.set_access_token(
        config['access-token'], config['access-token-secret'])

    return tweepy.API(auth)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a word map, with the shape and colors given by "
        "a file, from live Twitter data.",
        epilog="The configuration file should be a JSON file containing just "
        "the keys 'api-keys', 'api-secret', 'access-token' and "
        "'access-token-secret' for access to the Twitter API.")

    parser.add_argument('base_image', type=argparse.FileType('rb'),
                        help="The image to use as the base of the word cloud.")
    parser.add_argument('target_word', help="Tweets containing this word "
                        "will be searched and their text used for the word "
                        "cloud. This word will be omitted from the cloud.")
    parser.add_argument('out_file', type=argparse.FileType('wb'),
                        help="The file where the final resulting image will "
                        "be written to.")
    parser.add_argument('--background-color',
                        help="The background color of the word cloud. "
                        "White by default. Can use color names.",
                        default='white')
    parser.add_argument('--time-limit', type=float, help="Time (in seconds) "
                        "to spend gathering live tweets containing the target "
                        "word. The script will spend this much time gathering "
                        "live tweets, then generate the word map. Default is "
                        "an hour.", default=60.0*60.0)
    parser.add_argument('--config-file', type=argparse.FileType('r'),
                        help="A file with API keys for Twitter.",
                        default=open("config.json"))
    parser.add_argument('--random-words', action='store_true',
                        help="Passing this flag makes it so it won't access "
                        "Twitter at all. Instead it will generate the word "
                        "cloud from completely random words and frequencies. "
                        "Useful for testing an image to see if it looks good.")

    return parser.parse_args()


def main():
    args = parse_args()

    # this downloads stuff into ~/nltk_data !!
    nltk.download('punkt')
    nltk.download('words')
    nltk.download('stopwords')

    if args.random_words:
        words = {}
        for w in range(1000):
            wordlen = max(int(random.gauss(5, 3)), 1)
            word = ''.join(random.choices(string.ascii_lowercase, k=wordlen))
            count = max(random.gauss(200, 100), 0.0)
            words[word] = count
    else:
        api = get_api(args.config_file)
        streamListener = MyStreamListener(
            args.target_word, args.time_limit, api)
        stream = tweepy.Stream(auth=api.auth, listener=streamListener)
        while not streamListener.finished():
            try:
                stream.filter(track=[args.target_word])
            except Exception:
                print(traceback.format_exc())
            print("Exception occurred, continuing...")
        words = streamListener.words

    image = np.array(Image.open(args.base_image))
    wc = WordCloud(mask=image, background_color=args.background_color)
    wc.generate_from_frequencies(words)
    colors = ImageColorGenerator(image)
    wc.recolor(color_func=colors)
    wc.to_file(args.out_file)


if __name__ == '__main__':
    main()
