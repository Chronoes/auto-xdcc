import threading


class ThreadRunner:
    def __init__(self, logger):
        self._thread = self.create_thread()
        self.logger = logger

    def __del__(self):
        self.terminate(force=True)

    def create_thread(self):
        return threading.Thread(target=self._wrapped_run)

    def start(self):
        if not self._thread.is_alive():
            self.logger.debug("Creating and starting thread")
            self._thread = self.create_thread()
            self._thread.start()
            return True
        return False

    def terminate(self, force=False):
        if self._thread.is_alive():
            self.logger.debug("Terminating running thread")
            self._thread_stop = True
            return True
        return False

    def is_stopping(self):
        return self._thread_stop

    def _wrapped_run(self):
        self._thread_stop = False
        self._run()

    def _run(self):
        raise NotImplementedError('Must be implemented for using the thread')
