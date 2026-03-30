from __future__ import annotations

import io
import threading
import time
from contextlib import contextmanager

from app.config import Config
from app.jobs.queue import JOB_TYPE_CRN, JOB_TYPE_PDF, RedisJobQueue
from app.routes.schedules.schedules_service import (
    add_courses_by_pdf,
    add_resolved_courses_by_crn,
    extract_schedule_identifiers_from_pdf,
    resolve_courses_from_uiuc,
    serialize_courses_for_response,
)
from app.utils.logger import get_logger
from app.utils.supabase_admin import delete_file, download_private_file

logger = get_logger(__name__)


class ScheduleImportWorker:
    def __init__(self, worker_id: str | None = None, queue: RedisJobQueue | None = None):
        self.worker_id = worker_id or f"worker-{__import__('uuid').uuid4().hex}"
        self.queue = queue or RedisJobQueue()

    def run_forever(self):
        logger.info("Schedule import worker started", extra={"worker_id": self.worker_id})
        while True:
            try:
                self.queue.requeue_expired_jobs()
                job = self.queue.claim_next_job(self.worker_id)
                if not job:
                    time.sleep(Config.REDIS_JOB_POLL_INTERVAL_SECONDS)
                    continue
                self.process_job(job)
            except Exception as exc:
                logger.exception("Worker loop failure", extra={"worker_id": self.worker_id, "error": str(exc)})
                time.sleep(Config.REDIS_JOB_POLL_INTERVAL_SECONDS)

    def process_job(self, job: dict):
        lease = self.queue.build_lease(job)
        stop_event = threading.Event()
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, args=(lease, stop_event), daemon=True)
        heartbeat_thread.start()
        try:
            if job["job_type"] == JOB_TYPE_PDF:
                result_payload = self._process_pdf_job(job)
            elif job["job_type"] == JOB_TYPE_CRN:
                result_payload = self._process_crn_job(job)
            else:
                raise ValueError(f"Unsupported job type: {job['job_type']}")

            status = self.queue.complete_job(lease, job, result_payload)
            if status in {"completed", "superseded"} and job.get("object_path"):
                delete_file(job["object_path"], Config.SUPABASE_SCHEDULE_PDF_BUCKET)
        except Exception as exc:
            logger.exception("Failed to process schedule import job", extra={"job_id": job["job_id"], "error": str(exc)})
            status = self.queue.fail_or_retry_job(lease, job, str(exc))
            if status in {"failed", "superseded"} and job.get("object_path"):
                delete_file(job["object_path"], Config.SUPABASE_SCHEDULE_PDF_BUCKET)
        finally:
            stop_event.set()
            heartbeat_thread.join(timeout=1)

    def _heartbeat_loop(self, lease, stop_event: threading.Event):
        while not stop_event.wait(Config.REDIS_JOB_HEARTBEAT_SECONDS):
            if not self.queue.heartbeat(lease):
                return

    def _process_pdf_job(self, job: dict) -> dict:
        pdf_bytes = download_private_file(job["object_path"], Config.SUPABASE_SCHEDULE_PDF_BUCKET)
        pdf_buffer = io.BytesIO(pdf_bytes)
        pdf_buffer.name = job.get("original_filename") or "schedule.pdf"
        course_identifiers, schedule_info = extract_schedule_identifiers_from_pdf(pdf_buffer)
        current_job = self.queue.get_job(job["job_id"])
        if not current_job or current_job.get("status") != "processing":
            raise RuntimeError("Job is no longer active.")
        courses = resolve_courses_from_uiuc(schedule_info["year"], schedule_info["term"], course_identifiers)
        add_courses_by_pdf(job["user_id"], schedule_info["year"], schedule_info["term"], courses)
        return {
            "year": schedule_info["year"],
            "term": schedule_info["term"],
            "courses": serialize_courses_for_response(courses),
        }

    def _process_crn_job(self, job: dict) -> dict:
        payload = job.get("payload") or {}
        courses = resolve_courses_from_uiuc(job["year"], job["term"], payload.get("courses", []))
        add_resolved_courses_by_crn(job["user_id"], job["year"], job["term"], courses)
        return {
            "year": job["year"],
            "term": job["term"],
            "courses": serialize_courses_for_response(courses),
        }
