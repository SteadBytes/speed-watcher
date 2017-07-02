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
tweet_data_queue = queue.Queue()


def main():
    error_logger = Logger(config['errorFilePath'])
    test_thread = SpeedTestThread(1, "SpeedTestThread1", error_logger)
    tweet_thread = TwitterThread(2, "TwitterThread1", error_logger)
    test_thread.start()
    tweet_thread.start()


class Logger(object):
    def __init__(self, filepath):
        self.filepath = filepath

    def logCsv(self, data):
        print("Logging data...")
        with open(self.filepath, 'a') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            if os.stat(self.filepath).st_size == 0:
                writer.writeheader()
            writer.writerow(data)
        print("Done -> '%s'" % self.filepath)


class SpeedTestThread(threading.Thread):
    def __init__(self, thread_id, name, error_logger):
        threading.Thread.__init__(self)
        self.name = name
        self.thread_id = thread_id
        self.targetSpeeds = config['internetSpeeds']
        self.s = speedtest.Speedtest()
        self.dataLogger = Logger(config['logFilePath'])
        self.error_logger = error_logger

    def run(self):
        global exitFlag
        counter = 0
        while exitFlag == 0:
            try:
                results = self.getSpeeds()
                # results = json.load(open('results.json'))
                self.checkSpeeds(results)
                self.dataLogger.logCsv(results)
            except Exception as e:
                counter += 1
                error = {"time": time.ctime(),
                         "error": "Unable to retrieve results",
                         "exception": e}
                print("Unable to retrieve results")
                self.error_logger.logCsv(error)
                if counter >= config['testAttempts']:
                    exitFlag = 1
                    error = "10 Failed test attemtps, exiting."
                    print(error)
                    error = {"time": time.ctime(),
                             "error": error}
                    self.error_logger.logCsv(error)

            time.sleep(config['testFreq'])

    def getSpeeds(self):
        self.s.get_best_server()
        self.s.upload()
        self.s.download()
        return self.s.results.dict()

    def checkSpeeds(self, results):
        global tweetFlag
        if (results['download'] / (2**20) < self.targetSpeeds['download'] or
            results['upload'] / (2**20) < self.targetSpeeds['upload'] or
                results['ping'] > self.targetSpeeds['ping']):
            print("Unnaceptable speed results")
            tweetFlag = 1
            tweet_data_queue.put(results)
            print("Results queued for tweet")

        print('Download: %s' % results['download'])
        print('Upload: %s' % results['upload'])
        print('Ping: %s' % results['ping'])


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
        counter = 0
        while exitFlag == 0 and tweetFlag == 1:
            if tweetFlag == 1:
                results = tweet_data_queue.get()
                download = round(results['download'] / (2**20), 2)
                upload = round(results['upload'] / (2**20), 2)
                content = ("%s! I'm meant to get 52 mb/s down and 10mb/s"
                           " up.I got %smb/s down and %smb/s up!"
                           % (config['ispTwitter'], download, upload))
                try:
                    self.twitterAPI.update_status(content)
                except Exception as e:
                    counter += 1
                    errorMsg = "Unable to send tweet"
                    error = {"time": time.ctime(),
                             "error": errorMsg,
                             "exception": e}
                    print(errorMsg)
                    self.error_logger.logCsv(error)
                    if counter >= config['testAttempts']:
                        exitFlag = 1
                        errorMsg = "10 Failed tweet attempts, exiting."
                        print(errorMsg)
                        error = {"time": time.ctime(),
                                 "error": errorMsg}
                        self.error_logger.logCsv(error)
                    if tweet_data_queue.qsize() == 0:
                        tweetFlag = 0


if __name__ == "__main__":
    main()
