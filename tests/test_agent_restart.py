"""Real PTY regression: restarting retains the selected project directory."""
import asyncio
import tempfile
import unittest
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from backend.agent_pty import SessionManager


class RestartTests(unittest.IsolatedAsyncioTestCase):
    async def test_restart_preserves_project_and_executes_in_it(self):
        manager = SessionManager()
        # Use a local test command, not a model provider or external agent.
        manager.get_command_for_agent = lambda agent_id: ['/bin/sh', '-c', 'pwd; read answer']
        with tempfile.TemporaryDirectory() as project:
            try:
                manager.get_or_create_session('test', cwd=project)
                session = manager.restart_session('test')
                self.assertEqual(Path(session.cwd), Path(project))
                for _ in range(50):
                    if project in ''.join(session.history):
                        break
                    await asyncio.sleep(0.02)
                self.assertIn(project, ''.join(session.history))
            finally:
                manager.stop_session('test')


if __name__ == '__main__':
    unittest.main()
