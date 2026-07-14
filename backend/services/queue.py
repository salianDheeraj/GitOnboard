import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models.repository import AnalysisJob

logger = logging.getLogger(__name__)

class WorkerInterface(ABC):
    @abstractmethod
    async def process(self, job_id: int):
        pass

class QueueInterface(ABC):
    @abstractmethod
    async def enqueue(self, job_id: int):
        pass

class InMemoryQueue(QueueInterface):
    def __init__(self, worker: WorkerInterface):
        self.queue = asyncio.Queue()
        self.worker = worker
        self._task = None

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._process_loop())

    async def enqueue(self, job_id: int):
        await self.queue.put(job_id)

    async def _process_loop(self):
        while True:
            job_id = await self.queue.get()
            try:
                await self.worker.process(job_id)
            except Exception as e:
                logger.error(f"Error processing job {job_id}: {e}")
            finally:
                self.queue.task_done()

# We will instantiate the queue and worker in main.py
