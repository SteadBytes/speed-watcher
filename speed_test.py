import speedtest
import json
import time
import csv
import os
import threading
import queue
import tweepy
import random

# Load app config from file
config = json.load(open('config.json'))

# Globals used for multiple thread control
exitFlag = 0
tweetFlag = 0
# Global queue for tweet data, shared between threads
tweet_data_queue = queue.Queue()


def main():
    """ App entry point

    Creates and starts required threads. Initialises error logging.
    """
    error_logger = ErrorLogger(config['errorFilePath'])
    test_thread = SpeedTestThread(1, "SpeedTestThread1", error_logger)
    tweet_thread = TwitterThread(2, "TwitterThread1", error_logger)
    test_thread.start()
    tweet_thread.start()


class SpeedTestThread(threading.Thread):
    """ Thread class for measuring internet speeds.

    Will run until exit flag is true. Retrieves speed test data at a set
    interval. Checks data against configured thresholds and pipes data to
    tweet thread if under threshold.
    """

    def __init__(self, thread_id, name, error_logger):
        threading.Thread.__init__(self)
        self.name = name
        self.thread_id = thread_id
        self.s = speedtest.Speedtest()
        self.targetSpeeds = config['internetSpeeds']
        self.dataLogger = ErrorLogger(config['logFilePath'])
        self.error_logger = error_logger

    def run(self):
        """ Main thread loop. Calls class methods to get and check speeds.
        """
        global exitFlag
        prevError = False  # Used to track consecutive errors
        while exitFlag == 0:
            try:
                results = self.getSpeeds()
                self.checkSpeeds(results)
                self.dataLogger.logCsv(results)
            except Exception as e:
                error = {"time": time.ctime(),
                         "error": "Unable to retrieve results",
                         "exception": e}
                self.error_logger.logError(error)
                prevError = True

            # Reset ErrorLogger counter on successful execution without error
            if prevError:
                self.error_logger.counter = 0
            time.sleep(config['testFreq'])

    def getSpeeds(self):
        """ Tests upload and download speeds using speedtest-cli

        Returns:
            Dictionary of speedtest results
        """
        self.s.get_best_server()
        self.s.upload()
        self.s.download()
        return self.s.results.dict()

    def checkSpeeds(self, results):
        """ Checks speedtest results against threshold set in config.

        If results are under threshold, adds data to queue and sets tweetFlag.
        Args:
            results: Dictionary of speedtest results as returned by getSpeeds()
        """
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
    """ Thread class for handling tweets.

        Will run until exit flag is true. When tweetflag is set, retrieves data
        from queue and sends a tweet containing the data.
    """

    def __init__(self, thread_id, name, error_logger):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.name = name
        self.error_logger = error_logger

        # Set up tweepy with twitter API authentication
        self.apiData = config['twitterAPI']
        auth = tweepy.OAuthHandler(
            self.apiData['apiKey'], self.apiData['apiSecret'])
        auth.set_access_token(self.apiData['accessToken'],
                              self.apiData['accessTokenSecret'])
        self.twitterAPI = tweepy.API(auth)

    def run(self):
        """ Main thread loop. When tweetFlag set, generates and sends a tweet
            based on data from speedtests.
        """
        global exitFlag
        global tweetFlag
        prevError = False  # Used to track consecutive errors
        while True:
            if exitFlag == 1:
                break
            if tweetFlag == 1:
                tweet = self.getTweet()
                try:
                    self.twitterAPI.update_status(tweet)
                    print("Tweet successful")
                except Exception as e:
                    error = {"time": time.ctime(),
                             "error": "Unable to send tweet",
                             "exception": e}
                    self.error_logger.logError(error)
                    prevError = True

                # Reset ErrorLogger counter on successful execution without
                # error
                if prevError:
                    self.error_logger.counter = 0

                if tweet_data_queue.qsize() == 0:
                    tweetFlag = 0

    def getTweet(self):
        """ Creates a tweet using data from speedtests

        Uses pre-configured message templates from config file and inserts data
        from speedtest by retrieving from queue.

        Returns:
            String: complete tweet ready to send.
        """
        data = tweet_data_queue.get()
        down = round(data['download'] / (2**20), 2)
        up = round(data['upload'] / (2**20), 2)
        content = random.choice(config['tweetContent'])
        return content.format(config['ispTwitter'], down, up)


class Logger(object):
    """ Base logger class for logging data to CSV.
    """

    def __init__(self, filepath):
        self.filepath = filepath

    def logCsv(self, data):
        """ Writes data to CSV file at self.filepath.

        Each logger instance must always write the same data structure, i.e
        the same dictionary but with different data. So that the headers within
        the CSV file are correct.

        Args:
            data: Dictionary of data to log.
        """
        print("Logging ...")
        with open(self.filepath, 'a') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            if os.stat(self.filepath).st_size == 0:
                writer.writeheader()
            writer.writerow(data)
        print("Done -> '%s'" % self.filepath)


class ErrorLogger(Logger):
    """ Subclass of Logger specifically for logging errors.
    """

    def __init__(self, filepath):
        Logger.__init__(self, filepath)
        # Used to limit consecutive errors.
        self.counter = 0

    def logError(self, errorData):
        """ Writes error data to file.

        If too many consecutive errors, will set exitFlag to stop execution.

        Args:
            errorData: Dictof error data with keys {"time","error","exception"}
        """
        global exitFlag
        if self.counter >= config['testAttempts']:
            exitFlag = 1
            errorData['error'] = "10 Failed test attempts, exiting."
            self.counter = 0
        print(errorData['error'])
        self.logCsv(errorData)


if __name__ == "__main__":
    main()
