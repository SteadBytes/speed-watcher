import speedtest
import json
import time
import csv
import os
import threading
import queue
import tweepy

exitFlag = 0
tweetFlag = 0

config = json.load(open('config.json'))


class SpeedTestThread(threading.Thread):
    def __init__(self, thread_id, name):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.name = name
        self.targetSpeeds = config['internetSpeeds']
        self.s = speedtest.Speedtest()
        self.s.get_best_server()

    def run(self):
        global exitFlag
        while exitFlag == 0:
            try:
                # self.s.upload()
                # self.s.download()
                # results = self.s.results.dict()
                results = json.load(open('results.json'))
            except:
                print("Could not retrieve speedtest data")
                self.exit()

            self.checkSpeeds(results)

            with open('results.csv', 'a') as f:
                writer = csv.DictWriter(f, fieldnames=results.keys())
                if os.stat('results.csv').st_size == 0:
                    writer.writeheader()
                writer.writerow(results)
            time.sleep(5)

        self.exit()

    def checkSpeeds(self, results):
        global tweetFlag
        if (results['download'] / (2**20) < self.targetSpeeds['download'] or
            results['upload'] / (2**20) < self.targetSpeeds['upload'] or
                results['ping'] > self.targetSpeeds['ping']):

            tweetFlag = 1
            q.put(results)


class TwitterThread(threading.Thread):
    def __init__(self, thread_id, name):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.name = name
        self.apiData = config['twitterAPI']
        auth = tweepy.OAuthHandler(
            self.apiData['apiKey'], self.apiData['apiSecret'])
        auth.set_access_token(self.apiData['accessToken'],
                              self.apiData['accessTokenSecret'])
        self.twitterAPI = tweepy.API(auth)

    def run(self):
        global exitFlag
        global tweetFlag
        while True:
            if tweetFlag == 1:
                results = q.get()
                print("Unnaceptable speed results:")
                print('Download: %s' % results['download'])
                print('Upload: %s' % results['upload'])
                print('Ping: %s' % results['ping'])
                download = round(results['download'] / (2**20), 2)
                upload = round(results['upload'] / (2**20), 2)
                content = ("%s! I'm meant to get 52 mb/s down and 10mb/s"
                           " up.I got %smb/s down and %smb/s up!"
                           % (config['ispTwitter'], download, upload))
                try:
                    self.twitterAPI.update_status(content)
                except Exception as e:
                    print(e)

                tweetFlag = 0


q = queue.Queue()

test_thread = SpeedTestThread(1, "SpeedTestThread1")
tweet_thread = TwitterThread(2, "TwitterThread1")
test_thread.start()
tweet_thread.start()
