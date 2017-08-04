import speedtest
import json
import time
import threading
import queue
import tweepy
import random
import app.loggers as loggers

# Load app config from file
config = json.load(open('config.json'))


def main():
    """ App entry point

    Creates and starts required threads. Initialises error logging and queues.
    """
    error_logger = loggers.ErrorLogger(config['errorFilePath'])
    # Queue for tweet data, shared between threads
    tweet_data_queue = queue.Queue()
    test_thread = SpeedTestThread(
        1, "SpeedTestThread1", error_logger, tweet_data_queue)
    test_thread.start()


class SpeedTestThread(threading.Thread):
    """ Thread class for measuring internet speeds.

    Will run until exit flag is true. Retrieves speed test data at a set
    interval. Checks data against configured thresholds and pipes data to
    tweet thread if under threshold.
    """

    def __init__(self, thread_id, name, error_logger, tweet_data_queue):
        threading.Thread.__init__(self)
        self.name = name
        self.thread_id = thread_id
        self.tweet_data_queue = tweet_data_queue
        self.s = speedtest.Speedtest()
        self.targetSpeeds = config['internetSpeeds']
        self.dataLogger = loggers.Logger(config['logFilePath'])
        self.error_logger = error_logger
        self.twitter_handler = TwitterHandler(
            self.error_logger, self.tweet_data_queue)
        self.exit_flag = False

    def run(self):
        """ Main thread loop. Calls class methods to get and check speeds.
        """
        prevError = False  # Used to track consecutive errors
        while not self.exit_flag:
            try:
                results = self.getSpeeds()
            except Exception as e:
                error = {"time": time.ctime(),
                         "error": "Unable to retrieve results",
                         "exception": e}
                self.error_logger.logError(error)
                prevError = True
            self.checkSpeeds(results)
            if self.dataLogger.logCsv(results):  # Returns exit_flag bool
                self.exit_flag = True

            # Reset ErrorLogger counter on successful execution without error
            if prevError:
                prevError = False
                self.error_logger.counter = 0
            time.sleep(config['testFreq'])
        return

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

        If results are under threshold, adds data to queue and calls
        twitter_handler.sendTweet().
        Args:
            results: Dictionary of speedtest results as returned by getSpeeds()
        """
        down = results['download']
        up = results['upload']
        ping = results['ping']
        if (down / (10**6) < self.targetSpeeds['download'] or
            up / (10**6) < self.targetSpeeds['upload'] or
                ping > self.targetSpeeds['ping']):
            print("Unnaceptable speed results:\n"
                  "Download: %s\n"
                  "Upload: %s\n"
                  "Ping: %s\n" % (down, up, ping))
            self.tweet_data_queue.put(results)
            print("Results queued for tweet")
            self.twitter_handler.sendTweet()


class TwitterHandler(object):
    def __init__(self, error_logger, tweet_data_queue):
        self.tweet_data_queue = tweet_data_queue
        self.error_logger = error_logger

        # Set up tweepy with twitter API authentication
        self.apiData = config['twitterAPI']
        auth = tweepy.OAuthHandler(
            self.apiData['apiKey'], self.apiData['apiSecret'])
        auth.set_access_token(self.apiData['accessToken'],
                              self.apiData['accessTokenSecret'])
        self.twitterAPI = tweepy.API(auth)

    def sendTweet(self):
        """ Creates and sends tweets using data from queue

        Will run until queue is empty in case of a backlog
        """
        prevError = False
        while self.tweet_data_queue.qsize() > 0:
            tweet = self.getTweet()
            try:
                self.twitterAPI.update_status(tweet)
                print("Tweet successful")
            except Exception as e:
                error = {"time": time.ctime(),
                         "error": "Unable to send tweet",
                         "exception": e}
                prevError = True
                self.error_logger.logError(error)

            if prevError:
                self.error_logger.counter = 0
                prevError = False
        print("Tweet queue empty, new data needed")

    def getTweet(self):
        """ Creates a tweet using data from speedtests

        Uses pre-configured message templates from config file and inserts data
        from speedtest by retrieving from queue.

        Returns:
            String: complete tweet ready to send.
        """
        data = self.tweet_data_queue.get()
        down = round(data['download'] / (10**6), 2)
        up = round(data['upload'] / (10**6), 2)
        content = random.choice(config['tweetContent'])
        return content.format(config['ispTwitter'], down, up)


if __name__ == "__main__":
    main()
