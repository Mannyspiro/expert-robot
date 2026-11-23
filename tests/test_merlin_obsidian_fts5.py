"""Memory-only second brain search acceptance and negative controls."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from merlin.obsidian_vault_bridge import ObsidianVaultBridge
from merlin.obsidian_fts5 import local_fts5_search


class FTS5Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'models.md').write_text('# Models\nLightweight RAM usage.\nQwen inference benchmarks.\n')
        (self.root / 'math.md').write_text('# Mathematics\nDimensional simplex.\n', encoding='utf-8')
        self.vault = ObsidianVaultBridge(self.root)

    def test_multi_paragraph_retrieval_adds_coverage_vs_line_only_baseline(self):
        self.assertEqual(self.vault.search('RAM Qwen')['results'], [])
        results = local_fts5_search(self.vault, 'RAM Qwen')
        self.assertEqual([x['path'] for x in results['results']], ['models.md'])
        self.assertEqual(results['index'], 'SQLite FTS5 memory-only')
        self.assertFalse(results['source_content_emitted'])
        self.assertFalse(results['persistent_memory_changed'])
        self.assertFalse(results['production_qualified'])

    def test_notes_remain_unchanged_and_no_db_files_created(self):
        before = sorted(path.name for path in self.root.iterdir())
        original = (self.root / 'models.md').read_bytes()
        local_fts5_search(self.vault, 'Qwen')
        self.assertEqual(original, (self.root / 'models.md').read_bytes())
        self.assertEqual(before, sorted(path.name for path in self.root.iterdir()))

    def test_fts_query_syntax_is_never_executed(self):
        self.assertEqual(local_fts5_search(self.vault, 'Qwen OR secrets')['results'], [])
        self.assertEqual(local_fts5_search(self.vault, 'title:math OR Qwen')['results'], [])

    def test_invalid_queries_rejected(self):
        for query in ('', 'word ' * 12):
            with self.assertRaises(ValueError):
                local_fts5_search(self.vault, query)
        with self.assertRaises(ValueError):
            local_fts5_search(self.vault, 'model', limit=0)

    def test_source_mutation_during_index_is_rejected(self):
        original = self.vault._read
        counter = 0
        def changing(path, **kwargs):
            nonlocal counter
            counter += 1
            if counter == 3:
                (self.root / 'models.md').write_text('# corrupted note')
            return original(path, **kwargs)
        with patch.object(self.vault, '_read', side_effect=changing):
            with self.assertRaises(RuntimeError):
                local_fts5_search(self.vault, 'Qwen')

    def test_explicit_snippets_have_line_numbers(self):
        result = local_fts5_search(self.vault, 'Qwen inference', include_snippets=True)
        self.assertEqual(result['results'][0]['line'], 3)
        self.assertIn('Qwen inference', result['results'][0]['snippet'])
        self.assertTrue(result['source_content_emitted'])

    def test_partial_inventory_keeps_omissions(self):
        (self.root / 'alias.md').symlink_to(self.root / 'models.md')
        result = local_fts5_search(self.vault, 'Qwen')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['omissions'][0]['path'], 'alias.md')

    def test_opt_in_source_size_budget(self):
        with patch('merlin.obsidian_fts5.MAX_FTS_SOURCE_BYTES', 8):
            with self.assertRaises(ValueError):
                local_fts5_search(self.vault, 'Qwen')


if __name__ == '__main__':
    unittest.main()
