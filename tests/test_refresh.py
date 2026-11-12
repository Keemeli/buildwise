"""Refresh stage planning, category selection and failure propagation."""
import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.pipeline.refresh import RefreshPipeline


def options(**updates):
    values = dict(skip_scrape=False, skip_specs=False, cold=False, pages=1, delay=1.0,
                  jimms_input=None, jimms_category_url=None)
    values.update(updates)
    return argparse.Namespace(**values)


class RefreshPipelineTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.ExitStack()
        self.output.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.output.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def tearDown(self):
        self.output.close()

    def test_pipeline_cold_and_jimms_stage_planning(self):
        pipeline = RefreshPipeline(options(cold=True, jimms_category_url='https://www.jimms.fi/fi/Product/List/gpu'),
                                   ['gpu'], ['datatronic', 'jimms'])
        stages = pipeline.build_stages()
        self.assertEqual([name for name, _ in stages], [
            'datatronic-collect', 'jimms-collect', 'datatronic-specs', 'normalise', 'export'])
        self.assertIn('--force', dict(stages)['datatronic-specs'])

    def test_pipeline_stops_before_export_on_worker_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = Mock(return_value={'ok': False, 'last_lines': ['failed']})
            pipeline = RefreshPipeline(options(skip_specs=True), ['gpu'], ['datatronic'],
                stage_runner=runner, project_root=root, log_path=root / 'refresh.jsonl')
            self.assertEqual(pipeline.run(), 1)
            self.assertEqual(runner.call_count, 1)
            self.assertEqual(json.loads((root / 'refresh.jsonl').read_text())['status'], 'failed at datatronic-collect')


class RefreshCategoryTests(unittest.TestCase):
    def test_refresh_selects_requested_categories(self):
        from unittest.mock import patch
        from scraper.pipeline import refresh
        from scraper import cli as command
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(sys, 'argv', ['scraper', 'refresh', '--categories', 'gpu,cpu', '--skip-specs', '--data-dir', directory]), \
                 patch.object(refresh, 'PROJECT_ROOT', Path(directory)), \
                 patch.object(refresh, 'LOG_PATH', Path(directory) / 'refresh.jsonl'), \
                 patch.object(refresh, 'run_stage', return_value={'ok': True}) as stage:
                self.assertEqual(command.main(), 0)
                names = [call.args[0] for call in stage.call_args_list]
                self.assertEqual(names, ['datatronic-collect', 'normalise', 'export'])
                collection_args = stage.call_args_list[0].args[1]
                self.assertEqual([collection_args[i + 1] for i, arg in enumerate(collection_args) if arg == '--category'], ['gpu', 'cpu'])


if __name__ == '__main__':
    unittest.main()
