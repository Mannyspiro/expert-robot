"""Offline Obsidian second-brain fixtures: normal notes, authority and defects."""
from __future__ import annotations
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from merlin.obsidian_vault_bridge import ObsidianVaultBridge, _safe_relative


class ObsidianVaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'vault'
        self.root.mkdir()

    def write(self, relative, text):
        file = self.root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding='utf-8')

    def test_backlinks_wikilinks_markdown_links_tags_and_frontmatter(self):
        self.write('01 Projects/Merlin.md', '''---
tags:
  - ai
aliases:
  - Wizard Project
---
# Merlin
See [[Research/Local models|models]] and [Evidence](../08%20Decisions/Deploy.md).
Tag #in-progress
''' + chr(96) * 3 + '''md
[[Fake source]]
''' + chr(96) * 3 + '''
''')
        self.write('Research/Local models.md', '# Local models\n[[Wizard Project]]\n')
        self.write('08 Decisions/Deploy.md', '# Decision\n')
        report = ObsidianVaultBridge(self.root).read()
        self.assertEqual(report['status'], 'indexed')
        self.assertEqual(report['notes_scanned'], 3)
        self.assertEqual(len(report['links']), 3)
        self.assertEqual(report['unresolved'], [])
        notes = {n['path']: n for n in report['notes']}
        self.assertEqual(notes['01 Projects/Merlin.md']['tags'], ['ai', 'in-progress'])
        self.assertEqual(notes['01 Projects/Merlin.md']['aliases'], ['Wizard Project'])
        self.assertEqual(notes['01 Projects/Merlin.md']['outlinks'], ['08 Decisions/Deploy.md', 'Research/Local models.md'])
        self.assertEqual(notes['01 Projects/Merlin.md']['backlinks'], ['Research/Local models.md'])
        self.assertFalse(report['source_content_emitted'])
        self.assertFalse(report['persistent_memory_changed'])

    def test_search_has_hash_and_line_but_no_snippet_by_default(self):
        self.write('00 Inbox/Ram.md', '# RAM\nLocal model paging reduces peak RAM.\n')
        bridge = ObsidianVaultBridge(self.root)
        results = bridge.search('model paging')['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['path'], '00 Inbox/Ram.md')
        self.assertEqual(results[0]['line'], 2)
        self.assertEqual(len(results[0]['sha256']), 64)
        self.assertNotIn('snippet', results[0])
        self.assertIn('Local model paging', bridge.search('model paging', include_snippets=True)['results'][0]['snippet'])

    def test_hidden_settings_and_symlinks_never_read(self):
        self.write('.obsidian/private.md', 'SECRET .obsidian')
        self.write('good.md', '# Public\n')
        outside = Path(self.tmp.name) / 'secret.md'
        outside.write_text('SECRET OUTSIDE', encoding='utf-8')
        (self.root / 'escape.md').symlink_to(outside)
        (self.root / 'alias').symlink_to(outside.parent, target_is_directory=True)
        report = ObsidianVaultBridge(self.root).read()
        self.assertEqual([x['path'] for x in report['notes']], ['good.md'])
        self.assertEqual(report['status'], 'partial')
        self.assertEqual({x['reason'] for x in report['omissions']},
                         {'symlink_directory_disallowed', 'symlink_disallowed'})
        self.assertNotIn('SECRET', str(report))

    def test_hardlink_alias_and_nonutf8_bytes_fail_closed(self):
        external = Path(self.tmp.name) / 'external.md'
        external.write_text('some data', encoding='utf-8')
        os.link(external, self.root / 'hardlink.md')
        (self.root / 'bad.md').write_bytes(b'\xff\xfe')
        report = ObsidianVaultBridge(self.root).read()
        self.assertEqual(report['notes_scanned'], 0)
        self.assertEqual(len(report['omissions']), 2)
        self.assertEqual(report['status'], 'partial')

    def test_oversize_and_note_count_ceiling(self):
        self.write('a.md', 'X' * 110)
        self.write('b.md', 'tiny')
        x = ObsidianVaultBridge(self.root, max_notes=1, max_note_bytes=100).read()
        self.assertEqual(len(x['omissions']), 2)
        y = ObsidianVaultBridge(self.root, max_total_bytes=4).read()
        self.assertEqual(y['notes_scanned'], 1)
        self.assertEqual(y['status'], 'partial')

    def test_aggregate_read_budget_rejects_oversized_note_before_reading(self):
        self.write('Large.md', 'L' * 1000)
        self.write('Small.md', '# OK')
        bridge = ObsidianVaultBridge(self.root, max_total_bytes=4)
        with self.assertRaises(ValueError):
            bridge._read('Large.md', budget_bytes=4)
        report = bridge.read()
        self.assertEqual(report['notes_scanned'], 1)
        self.assertEqual(report['source_bytes_scanned'], 4)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual([x['path'] for x in report['notes']], ['Small.md'])

    def test_incomplete_vault_search_propagates_omissions(self):
        self.write('Note.md', '# searchable')
        (self.root / 'bad.md').symlink_to(self.root / 'Note.md')
        result = ObsidianVaultBridge(self.root).search('searchable')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['results'][0]['path'], 'Note.md')
        self.assertEqual(result['omissions'][0]['reason'], 'symlink_disallowed')

    def test_ambiguous_titles_never_auto_resolve(self):
        self.write('A/Duplicate.md', '# A')
        self.write('B/Duplicate.md', '# B')
        self.write('Home.md', '[[Duplicate]]')
        r = ObsidianVaultBridge(self.root).read()
        self.assertEqual(r['links'], [])
        self.assertEqual(r['unresolved'][0]['reason'], 'ambiguous')

    def test_unsupported_external_links_and_path_traversal_not_followed(self):
        self.write('Home.md', '[[https://example.com]]\n[other](../../outside.md)\n[link](file:///etc/passwd)\n')
        r = ObsidianVaultBridge(self.root).read()
        self.assertEqual(r['links'], [])
        self.assertEqual(len(r['unresolved']), 3)
        with self.assertRaises(ValueError):
            _safe_relative('../outside.md')
        with self.assertRaises(ValueError):
            _safe_relative('.obsidian/secret.md')

    def test_opt_in_only_and_no_vault_writes(self):
        self.write('Note.md', '# source')
        before = (self.root / 'Note.md').read_bytes()
        r = ObsidianVaultBridge(self.root).read()
        self.assertFalse(r['persistent_memory_changed'])
        self.assertEqual(before, (self.root / 'Note.md').read_bytes())
        self.assertEqual(list(self.root.rglob('*')), [self.root / 'Note.md'])

    def test_source_mutation_between_index_and_snippet_fails_closed(self):
        self.write('Note.md', 'Original text\n')
        bridge = ObsidianVaultBridge(self.root)
        real_read = bridge._read
        calls = 0

        def changed_on_second_read(path, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.write('Note.md', 'Replaced text\n')
            return real_read(path, **kwargs)

        with patch.object(bridge, '_read', side_effect=changed_on_second_read):
            with self.assertRaisesRegex(RuntimeError, 'changed during search'):
                bridge.search('text', include_snippets=True)

    def test_invalid_budgets_and_query(self):
        with self.assertRaises(ValueError):
            ObsidianVaultBridge(self.root, max_notes=True)
        bridge = ObsidianVaultBridge(self.root)
        for query in ('', ' ' * 161):
            with self.assertRaises(ValueError):
                bridge.search(query)
        with self.assertRaises(ValueError):
            bridge.search('hi', limit=0)


if __name__ == '__main__':
    unittest.main()
