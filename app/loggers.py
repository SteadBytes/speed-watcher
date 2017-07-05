import csv
import os


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

        If too many consecutive errors, will set exit_flag to stop execution.

        Args:
            errorData: Dictof error data with keys {"time","error","exception"}
        Returns:
            exit_flag: Bool, when true SpeedTestThread will terminate
        """
        if self.counter >= config['testAttempts']:
            errorData['error'] = "10 Failed test attempts, exiting."
            self.counter = 0
            exit_flag = True
        print(errorData['error'])
        self.logCsv(errorData)
        self.counter += 1
        return exit_flag
