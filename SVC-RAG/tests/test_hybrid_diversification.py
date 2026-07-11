import unittest

from app.database.models import DocumentVector
from app.services.rag_search_helpers import diversify_hybrid_rrf_hits


def _hit(document_id: int, chunk_index: int, score: float):
    return (
        DocumentVector(
            document_id=document_id,
            chunk_index=chunk_index,
            embedding=[],
            content=f"doc={document_id}, chunk={chunk_index}",
        ),
        score,
    )


class TestHybridRrfDiversification(unittest.TestCase):
    def test_limits_dominant_document_after_rrf(self):
        hits = [
            _hit(1, 0, 0.020),
            _hit(1, 1, 0.019),
            _hit(1, 2, 0.018),
            _hit(2, 0, 0.017),
            _hit(3, 0, 0.016),
        ]

        result = diversify_hybrid_rrf_hits(
            hits,
            candidate_limit=5,
            max_chunks_per_document=1,
            min_results=3,
        )

        self.assertEqual([item[0].document_id for item in result], [1, 2, 3])
        self.assertEqual([item[1] for item in result], [0.020, 0.017, 0.016])

    def test_relaxes_limit_only_to_fill_requested_top_k(self):
        hits = [
            _hit(1, 0, 0.020),
            _hit(1, 1, 0.019),
            _hit(1, 2, 0.018),
            _hit(2, 0, 0.017),
        ]

        result = diversify_hybrid_rrf_hits(
            hits,
            candidate_limit=4,
            max_chunks_per_document=1,
            min_results=4,
        )

        self.assertEqual(len(result), 4)
        self.assertEqual([item[0].document_id for item in result[:2]], [1, 2])

    def test_single_document_preserves_rrf_order(self):
        hits = [_hit(1, 0, 0.020), _hit(1, 1, 0.019), _hit(1, 2, 0.018)]

        result = diversify_hybrid_rrf_hits(
            hits,
            candidate_limit=3,
            max_chunks_per_document=1,
            min_results=3,
        )

        self.assertEqual([item[1] for item in result], [0.020, 0.019, 0.018])


if __name__ == "__main__":
    unittest.main()
