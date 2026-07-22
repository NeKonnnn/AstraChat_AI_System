import unittest

from app.services.retrieval_eval import (
    compute_retrieval_metrics,
    mrr,
    reciprocal_rank,
)


def _hit(document_id, chunk_index, score=0.5, content="x"):
    return (content, score, document_id, chunk_index)


class TestReciprocalRank(unittest.TestCase):
    def test_rr_first_position_doc(self):
        hits = [_hit(1, 0), _hit(2, 1), _hit(3, 2)]
        self.assertEqual(reciprocal_rank(hits, gold_document_ids=[1]), 1.0)

    def test_rr_third_position_doc(self):
        hits = [_hit(9, 0), _hit(8, 1), _hit(3, 2)]
        self.assertAlmostEqual(reciprocal_rank(hits, gold_document_ids=[3]), 1.0 / 3)

    def test_rr_zero_when_absent(self):
        hits = [_hit(9, 0), _hit(8, 1)]
        self.assertEqual(reciprocal_rank(hits, gold_document_ids=[3]), 0.0)

    def test_rr_by_gold_chunk(self):
        hits = [_hit(1, 5), _hit(1, 3), _hit(2, 0)]
        # первый релевантный чанк (1,3) на позиции 2
        self.assertAlmostEqual(reciprocal_rank(hits, gold_chunks=[(1, 3)]), 0.5)


class TestMrr(unittest.TestCase):
    def test_mrr_mean(self):
        self.assertAlmostEqual(mrr([1.0, 1.0 / 3, 0.5]), (1.0 + 1.0 / 3 + 0.5) / 3)

    def test_mrr_empty(self):
        self.assertEqual(mrr([]), 0.0)


class TestComputeRetrievalMetrics(unittest.TestCase):
    def test_gold_chunks_priority_and_values(self):
        hits = [_hit(1, 0), _hit(2, 1), _hit(1, 3), _hit(5, 9)]
        m = compute_retrieval_metrics(
            hits,
            k=4,
            gold_document_ids=[99],  # должен игнорироваться в пользу gold_chunks
            gold_chunks=[(1, 0), (1, 3)],
        )
        self.assertEqual(m["basis"], "gold_chunks")
        self.assertEqual(m["hit_rate_at_k"], 1.0)
        self.assertEqual(m["first_relevant_rank"], 1)
        self.assertEqual(m["reciprocal_rank"], 1.0)
        self.assertAlmostEqual(m["precision_at_k"], 2 / 4)
        self.assertAlmostEqual(m["recall_at_k"], 2 / 2)

    def test_gold_docs(self):
        hits = [_hit(7, 0), _hit(3, 1), _hit(3, 2)]
        m = compute_retrieval_metrics(hits, k=3, gold_document_ids=[3])
        self.assertEqual(m["basis"], "gold_document_ids")
        self.assertEqual(m["hit_rate_at_k"], 1.0)
        self.assertEqual(m["first_relevant_rank"], 2)
        self.assertAlmostEqual(m["reciprocal_rank"], 0.5)
        # два хита док=3 в top-k → precision = 2/3
        self.assertAlmostEqual(m["precision_at_k"], 2 / 3)
        self.assertAlmostEqual(m["recall_at_k"], 1.0)

    def test_no_gold_returns_none_metrics(self):
        hits = [_hit(1, 0)]
        m = compute_retrieval_metrics(hits, k=3)
        self.assertIsNone(m["reciprocal_rank"])
        self.assertIsNone(m["precision_at_k"])


if __name__ == "__main__":
    unittest.main()
