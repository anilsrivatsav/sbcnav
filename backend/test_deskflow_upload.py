import asyncio
import os
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
import deskflow_router as api


class UploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_workbook_processing_keeps_the_event_loop_responsive(self):
        loop = asyncio.get_running_loop()
        started = asyncio.Event()
        release = threading.Event()

        class Request:
            headers = {'content-type': 'application/zip', 'content-length': '4'}

            async def stream(self):
                yield b'test'

        def save(bundle):
            self.assertEqual(bundle, b'test')
            loop.call_soon_threadsafe(started.set)
            release.wait(timeout=2)
            return {'changed': True}

        with patch.object(api, '_save_workbook_archive', save):
            task = asyncio.create_task(api.agent_workbook_archive(Request()))
            try:
                await asyncio.wait_for(started.wait(), timeout=3)
                # The request is processing while the async loop can still
                # serve heartbeats and relay requests.
                self.assertFalse(task.done())
            finally:
                release.set()
                result = await task
        self.assertEqual(result, {'changed': True})


if __name__ == '__main__':
    unittest.main()
