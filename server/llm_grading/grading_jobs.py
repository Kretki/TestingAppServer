"""In-memory store of LLM checks and their results."""

import threading
import uuid
from dataclasses import dataclass, replace
from enum import StrEnum

from server.contracts.domain_errors import GradingQueueFullError, GradingRequestMissingError


class GradingStatus(StrEnum):
    """Lifecycle state of an LLM check."""

    STATUS_PENDING = "pending"
    STATUS_READY = "ready"
    STATUS_FAILED = "failed"


@dataclass(frozen=True)
class GradingJob:
    """Snapshot of one LLM check.

    Usage:
        Returned by `GradingJobStore.find_job`.

    Attributes:
        request_id: Id given to the user.
        request_status: Current state.
        llm_answer: Reply of the LLM when ready.
        error_detail: Reason of the failure when failed.
    """

    request_id: str
    request_status: GradingStatus = GradingStatus.STATUS_PENDING
    llm_answer: str | None = None
    error_detail: str | None = None


class GradingJobStore:
    """Thread-safe, bounded store of LLM checks.

    Usage:
        Create once at start-up. The oldest finished results are dropped when
        the store is full; pending checks are never dropped.
    """

    def __init__(self, max_pending_requests: int, max_stored_results: int) -> None:
        """Create an empty store.

        Usage:
            Call at start-up.

        Args:
            max_pending_requests: Largest number of unfinished checks, >= 1.
            max_stored_results: Largest number of kept checks, >= 1.
        """
        self._max_pending_requests = max_pending_requests
        self._max_stored_results = max_stored_results
        self._grading_jobs: dict[str, GradingJob] = {}
        self._pending_count = 0
        self._store_lock = threading.Lock()

    def create_job(self) -> str:
        """Register a new pending check.

        Usage:
            Call when an answer is accepted.

        Returns:
            The generated request id.

        Raises:
            GradingQueueFullError: If too many checks are pending.
        """
        with self._store_lock:
            if self._pending_count >= self._max_pending_requests:
                raise GradingQueueFullError("Too many answers are being checked, retry later")
            request_id = str(uuid.uuid4())
            self._grading_jobs[request_id] = GradingJob(request_id=request_id)
            self._pending_count += 1
            self._drop_oldest_results()
            return request_id

    def complete_job(self, request_id: str, llm_answer: str) -> None:
        """Mark a pending check as ready.

        Usage:
            Call when the LLM has replied.

        Args:
            request_id: Id of the check.
            llm_answer: Reply of the LLM.
        """
        self._finish_job(request_id, GradingStatus.STATUS_READY, llm_answer, None)

    def fail_job(self, request_id: str, error_detail: str) -> None:
        """Mark a pending check as failed.

        Usage:
            Call when the LLM call has failed.

        Args:
            request_id: Id of the check.
            error_detail: Reason shown to the user.
        """
        self._finish_job(request_id, GradingStatus.STATUS_FAILED, None, error_detail)

    def find_job(self, request_id: str) -> GradingJob:
        """Read the state of a check.

        Usage:
            Call when the user polls for a result.

        Args:
            request_id: Id of the check.

        Returns:
            The current snapshot.

        Raises:
            GradingRequestMissingError: If the id is unknown or expired.
        """
        with self._store_lock:
            grading_job = self._grading_jobs.get(request_id)
        if grading_job is None:
            raise GradingRequestMissingError(f"Unknown request id: {request_id}")
        return grading_job

    def _finish_job(
        self, request_id: str, request_status: GradingStatus, llm_answer: str | None, error_detail: str | None
    ) -> None:
        """Store the final state of a pending check.

        Usage:
            Internal step of `complete_job` and `fail_job`.

        Args:
            request_id: Id of the check.
            request_status: Final state.
            llm_answer: Reply of the LLM, or None.
            error_detail: Reason of the failure, or None.
        """
        with self._store_lock:
            self._grading_jobs[request_id] = replace(
                self._grading_jobs[request_id],
                request_status=request_status,
                llm_answer=llm_answer,
                error_detail=error_detail,
            )
            self._pending_count -= 1

    def _drop_oldest_results(self) -> None:
        """Remove the oldest finished checks beyond the storage limit.

        Usage:
            Internal step of `create_job`; the lock must be held.
        """
        excess_count = len(self._grading_jobs) - self._max_stored_results
        finished_ids = [
            grading_job.request_id
            for grading_job in self._grading_jobs.values()
            if grading_job.request_status is not GradingStatus.STATUS_PENDING
        ]
        for request_id in finished_ids[: max(excess_count, 0)]:
            del self._grading_jobs[request_id]
