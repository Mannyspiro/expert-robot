import tempfile
import unittest
from pathlib import Path

from merlin.academic_graph import AcademicGraphStore
from merlin.openalex_public import OpenAlexAuthor, OpenAlexTopic, OpenAlexWork


def sample_work():
    return OpenAlexWork(
        openalex_id="https://openalex.org/W123",
        doi="https://doi.org/10.1234/example",
        title="Graph embeddings and geometry",
        publication_year=2025,
        work_type="article",
        landing_page_url="https://journal.example.org/paper",
        is_oa=True,
        cited_by_count=4,
        authors=(
            OpenAlexAuthor(
                openalex_id="https://openalex.org/A456",
                display_name="Ada Example",
                orcid="https://orcid.org/0000-0000-0000-0000",
                institutions=("Example University",),
            ),
        ),
        topics=(OpenAlexTopic("https://openalex.org/T123", "Graph theory", 0.91),),
    )


class AcademicGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = AcademicGraphStore(Path(self.temp.name) / "graph.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_ingests_nodes_and_relationships(self):
        self.store.ingest(sample_work())
        stats = self.store.stats()
        self.assertEqual(stats.works, 1)
        self.assertEqual(stats.researchers, 1)
        self.assertEqual(stats.institutions, 1)
        self.assertEqual(stats.authorship_edges, 1)
        self.assertEqual(stats.topics, 1)
        self.assertEqual(stats.work_topic_edges, 1)
        self.assertEqual(self.store.topic_works("https://openalex.org/T123")[0]["topic"], "Graph theory")
        self.assertEqual(len(self.store.researcher_works("https://openalex.org/A456")), 1)

    def test_ingest_is_idempotent(self):
        self.store.ingest(sample_work())
        self.store.ingest(sample_work())
        self.assertEqual(self.store.stats().works, 1)
        self.assertEqual(self.store.stats().authorship_edges, 1)
        self.assertEqual(self.store.stats().work_topic_edges, 1)

    def test_does_not_merge_researchers_by_display_name(self):
        first = sample_work()
        self.store.ingest(first)
        second_author = OpenAlexAuthor(
            openalex_id="https://openalex.org/A999",
            display_name="Ada Example",
            orcid="",
            institutions=(),
        )
        second = OpenAlexWork(
            openalex_id="https://openalex.org/W999",
            doi="",
            title="Another paper",
            publication_year=2024,
            work_type="article",
            landing_page_url="",
            is_oa=None,
            cited_by_count=0,
            authors=(second_author,),
        )
        self.store.ingest(second)
        self.assertEqual(self.store.stats().researchers, 2)

    def test_reingest_replaces_stale_topic_edges(self):
        from dataclasses import replace
        self.store.ingest(sample_work())
        updated = replace(sample_work(), topics=(OpenAlexTopic("https://openalex.org/T999", "Topology", 0.7),))
        self.store.ingest(updated)
        self.assertEqual(self.store.stats().work_topic_edges, 1)
        self.assertEqual(self.store.topic_works("https://openalex.org/T123"), [])
        self.assertEqual(self.store.topic_works("https://openalex.org/T999")[0]["topic"], "Topology")

    def test_rejects_out_of_range_topic_score(self):
        from dataclasses import replace
        bad = replace(sample_work(), topics=(OpenAlexTopic("https://openalex.org/T123", "Graph theory", 1.5),))
        with self.assertRaises(ValueError):
            self.store.ingest(bad)

    def test_rejects_invalid_work_identifier_and_doi_collision(self):
        work = sample_work()
        bad = OpenAlexWork(
            openalex_id="not-an-openalex-id", doi=work.doi, title=work.title,
            publication_year=work.publication_year, work_type=work.work_type,
            landing_page_url=work.landing_page_url, is_oa=work.is_oa,
            cited_by_count=work.cited_by_count, authors=work.authors,
        )
        with self.assertRaises(ValueError):
            self.store.ingest(bad)


if __name__ == "__main__":
    unittest.main()
