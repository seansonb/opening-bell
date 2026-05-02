import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class BaseScheduledJob(ABC):
    def __init__(self, job_id: str, **kwargs):
        self.job_id = job_id

    def execute(self):
        """Entry point called by APScheduler. Do not override."""
        try:
            self._before_run()
            result = self.run()
            self._after_run(result)
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    @abstractmethod
    def run(self): ...

    def _before_run(self): pass

    def _after_run(self, result): pass

    def _on_failure(self, error: Exception):
        log.error(f"[{self.__class__.__name__}] job_id={self.job_id} failed: {error}")
