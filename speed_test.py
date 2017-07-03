import speedtest
import json
import time
import csv
import os
import threading
import queue
import tweepy
import random

exitFlag = 0
tweetFlag = 0
config = json.load(open('config.json'))
tweet_data_queue = queue.Queue()


def main():
    error_logger = ErrorLogger(config['errorFilePath'])
    test_thread = SpeedTestThread(1, "SpeedTestThread1", error_logger)
    tweet_thread = TwitterThread(2, "TwitterThread1", error_logger)
    test_thread.start()
    tweet_thread.start()


class SpeedTestThread(threading.Thread):
    def __init__(self, thread_id, name, error_logger):
        threading.Thread.__init__(self)
        self.name = name
        self.thread_id = thread_id
        self.targetSpeeds = config['internetSpeeds']
        self.s = speedtest.Speedtest()
        self.dataLogger = ErrorLogger(config['logFilePath'])
        self.error_logger = error_logger

    def run(self):
        global exitFlag
        while exitFlag == 0:
            try:
                # results = self.getSpeeds()
                results = json.load(open('results.json'))
                self.checkSpeeds(results)
                self.dataLogger.logCsv(results)
            except Exception as e:
                error = {"time": time.ctime(),
                         "error": "Unable to retrieve results",
                         "exception": e}
                self.error_logger.logError(error)

            time.sleep(config['testFreq'])

    def getSpeeds(self):
        self.s.get_best_server()
        self.s.upload()
        self.s.download()
        return self.s.results.dict()

    def checkSpeeds(self, results):
        global tweetFlag
        down = results['download']
        up = results['upload']
        ping = results['ping']
        if (down / (2**20) < self.targetSpeeds['download'] or
            up / (2**20) < self.targetSpeeds['upload'] or
                ping > self.targetSpeeds['ping']):
            print("Unnaceptable speed results:\n"
                  "Download: %s\n"
                  "Upload: %s\n"
                  "Ping: %s\n" % (down, up, ping))
            tweetFlag = 1
            tweet_data_queue.put(results)
            print("Results queued for tweet")


class TwitterThread(threading.Thread):
    def __init__(self, thread_id, name, error_logger):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.name = name
        self.apiData = config['twitterAPI']
        auth = tweepy.OAuthHandler(
            self.apiData['apiKey'], self.apiData['apiSecret'])
        auth.set_access_token(self.apiData['accessToken'],
                              self.apiData['accessTokenSecret'])
        self.twitterAPI = tweepy.API(auth)
        self.error_logger = error_logger

    def run(self):
        global exitFlag
        global tweetFlag
        while True:
            if exitFlag == 1:
                break
            if tweetFlag == 1:
                tweet = self.getTweet()
                # content = ("%s! I'm meant to get 52 mb/s down and 10mb/s"
                #            " up.I got %smb/s down and %smb/s up!"
                #            % (config['ispTwitter'], down, up))
                try:
                    self.twitterAPI.update_status(tweet)
                    print("Tweet successful")
                except Exception as e:
                    error = {"time": time.ctime(),
                             "error": "Unable to send tweet",
                             "exception": e}
                    self.error_logger.logError(error)

                    if tweet_data_queue.qsize() == 0:
                        tweetFlag = 0

    def getTweet(self):
        data = tweet_data_queue.get()
        down = round(data['download'] / (2**20), 2)
        up = round(data['upload'] / (2**20), 2)
        content = random.choice(config['tweetContent'])
        return content.format(config['ispTwitter'], down, up)


class Logger(object):
    def __init__(self, filepath):
        self.filepath = filepath

    def logCsv(self, data):
        print("Logging ...")
        with open(self.filepath, 'a') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            if os.stat(self.filepath).st_size == 0:
                writer.writeheader()
            writer.writerow(data)
        print("Done -> '%s'" % self.filepath)


class ErrorLogger(Logger):
    def __init__(self, filepath):
        Logger.__init__(self, filepath)
        self.counter = 0

    def logError(self, errorData):
        global exitFlag
        if self.counter >= config['testAttempts']:
            exitFlag = 1
            errorData['error'] = "10 Failed test attempts, exiting."
            self.counter = 0
        print(errorData['error'])
        self.logCsv(errorData)


if __name__ == "__main__":
    main()
