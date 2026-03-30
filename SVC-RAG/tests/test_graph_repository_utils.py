import unittest

from app.database.graph_repository import _jaccard, _tokenize


class TestGraphRepositoryUtils(unittest.TestCase):
    def test_tokenize_extracts_words(self):
        tokens = _tokenize("Graph-RAG: Test, test! 123")
        self.assertIn("graph", tokens)
        self.assertIn("rag", tokens)
        self.assertIn("test", tokens)

    def test_jaccard_overlap_positive_for_shared_terms(self):
        a = ["graph", "rag", "search"]
        b = ["rag", "search", "context"]
        self.assertGreater(_jaccard(a, b), 0.0)


if __name__ == "__main__":
    unittest.main()

