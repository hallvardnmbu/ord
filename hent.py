import os
import re

import pymongo
import requests
from deep_translator import GoogleTranslator


_URL = "https://phrontistery.info/{}.html"
_PATTERN = re.compile(r"\r\n<tr><td>(.*?)<td>", re.DOTALL)

_TRANSLATOR = GoogleTranslator(source='en', target='no')
_DICTIONARY = "https://ord.uib.no/api/articles?w={}&dict=bm"
_DESCRIPTION = "https://ord.uib.no/bm/article/{}.json"

_CLIENT = pymongo.mongo_client.MongoClient(
    f'mongodb+srv://{os.environ.get("MONGO_USR")}:{os.environ.get("MONGO_PWD")}'
    f'@ord.c8trc.mongodb.net/'
    f'?retryWrites=true&w=majority&appName=ord'
)
_DATABASE = _CLIENT['ord']['ord']


def words(letter: str):
    response = requests.get(_URL.format(letter))
    return re.findall(_PATTERN, response.text) if response.ok else []


def fetch(letters: str = "abcdefghijklmnopqrstuvwxyz"):
    vocabulary = []
    for letter in letters:
        vocabulary.extend([word for word in words(letter) if "<" not in word and "&" not in word])
    return vocabulary


def translate(vocabulary):
    return [{
        'engelsk': word,
        'norsk': _TRANSLATOR.translate(text=word)
    } for word in vocabulary]


def save(vocabulary):
    _DATABASE.bulk_write([
        pymongo.UpdateOne(
            {'engelsk': word['engelsk']},
            {'$set': word},
            upsert=True
        )
        for word in vocabulary
    ])


def clean():
    words = _DATABASE.find({}, {'norsk': 1, '_id': 0})
    operations = []
    for word in words:
        response = requests.get(_DICTIONARY.format(word))
        if not response.ok:
            operations.append(
                pymongo.DeleteOne({'norsk': word['norsk']})
            )
        response = response.json()
        if response['meta']['bm']['total'] == 0:
            operations.append(
                pymongo.DeleteOne({'norsk': word['norsk']})
            )
        operations.append(
            pymongo.UpdateOne(
                {'norsk': word['norsk']},
                {'$set': {
                    'ids': response['articles']
                }}
            )
        )


def describe(word):
    words = _DATABASE.find({'norsk': word}, {'norsk': 1, 'ids': 1, '_id': 0})
    operations = []
    for word in words:
        for id in word['ids']:
            response = requests.get(_DESCRIPTION.format(id))
            if not response.ok:
                operations.append(
                    pymongo.DeleteOne({'norsk': word['norsk']})
                )
            response = response.json()['body']

            operations.append(
                pymongo.UpdateOne(
                    {'norsk': word['norsk']},
                    {'$set': {
                        'uttalelse': response['pronunciation'],
                        'etymologi': response['etymology'],
                        'definisjoner': {

                        }
                    }}
                )
            )



if __name__ == "__main__":
    # vocabulary = fetch("abcdefghijklmnopqrstuvwxyz")
    # vocabulary = translate(vocabulary)
    # save(vocabulary)
    clean()
