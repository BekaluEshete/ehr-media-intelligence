"""Tests for the vector store and search pipeline."""
from __future__ import annotations


import numpy as np
import pytest

from app.search.embedder import embed_texts, embed_query
from app.search.vector_store import VectorStore
from app.config import settings


@pytest.fixture
def tmp_store(tmp_path):
    """VectorStore backed by a temp directory — cleaned up after each test."""
    return VectorStore(index_dir=tmp_path / "faiss")


class TestEmbedder:
    def test_returns_correct_dimension(self):
        vecs = embed_texts(["hello world"])
        assert len(vecs) == 1
        assert len(vecs[0]) == settings.embedding_dim

    def test_batch_embed(self):
        texts = ["foo", "bar", "baz"]
        vecs = embed_texts(texts)
        assert len(vecs) == 3

    def test_unit_vectors(self):
        vecs = embed_texts(["normalize me"])
        norm = np.linalg.norm(vecs[0])
        assert abs(norm - 1.0) < 0.01

    def test_empty_list(self):
        assert embed_texts([]) == []

    def test_query_embed_returns_flat_vector(self):
        vec = embed_query("chest pain")
        assert isinstance(vec, list)
        assert len(vec) == settings.embedding_dim


class TestVectorStore:
    def test_add_and_count(self, tmp_store):
        vecs = embed_texts(["doc one", "doc two"])
        meta = [
            {"doc_id": "d1", "mrn": "MRN1", "patient_name": "A",
             "resource_type": "DocumentReference", "date": "2024-01-01",
             "title": "T1", "summary_snippet": "doc one"},
            {"doc_id": "d2", "mrn": "MRN2", "patient_name": "B",
             "resource_type": "DiagnosticReport", "date": "2024-02-01",
             "title": "T2", "summary_snippet": "doc two"},
        ]
        tmp_store.add(vecs, meta)
        assert tmp_store.count() == 2

    def test_search_returns_top_k(self, tmp_store):
        texts = [f"document number {i}" for i in range(10)]
        vecs = embed_texts(texts)
        meta = [{"doc_id": f"d{i}", "mrn": f"MRN{i}", "patient_name": f"P{i}",
                 "resource_type": "DocumentReference", "date": "2024-01-01",
                 "title": f"T{i}", "summary_snippet": texts[i]} for i in range(10)]
        tmp_store.add(vecs, meta)
        results = tmp_store.search(embed_query("document number"), top_k=5)
        assert len(results) <= 5

    def test_search_filter_by_resource_type(self, tmp_store):
        vecs = embed_texts(["lab report text", "imaging report text"])
        meta = [
            {"doc_id": "d1", "mrn": "M1", "patient_name": "P1",
             "resource_type": "DocumentReference", "date": "2024-01-01",
             "title": "Lab", "summary_snippet": "lab"},
            {"doc_id": "d2", "mrn": "M2", "patient_name": "P2",
             "resource_type": "DiagnosticReport", "date": "2024-01-01",
             "title": "Img", "summary_snippet": "imaging"},
        ]
        tmp_store.add(vecs, meta)
        results = tmp_store.search(
            embed_query("report"), top_k=5,
            resource_type="DiagnosticReport"
        )
        assert all(r["resource_type"] == "DiagnosticReport" for r in results)

    def test_search_filter_by_date_range(self, tmp_store):
        vecs = embed_texts(["old doc", "new doc"])
        meta = [
            {"doc_id": "d1", "mrn": "M1", "patient_name": "P1",
             "resource_type": "DocumentReference", "date": "2020-01-01",
             "title": "Old", "summary_snippet": "old"},
            {"doc_id": "d2", "mrn": "M2", "patient_name": "P2",
             "resource_type": "DocumentReference", "date": "2024-06-01",
             "title": "New", "summary_snippet": "new"},
        ]
        tmp_store.add(vecs, meta)
        results = tmp_store.search(
            embed_query("document"), top_k=5,
            date_from="2024-01-01"
        )
        assert all(r["date"] >= "2024-01-01" for r in results)

    def test_persistence(self, tmp_path):
        store1 = VectorStore(index_dir=tmp_path / "faiss")
        vecs = embed_texts(["persisted document"])
        store1.add(vecs, [{"doc_id": "d1", "mrn": "M1", "patient_name": "P",
                            "resource_type": "DocumentReference", "date": "2024-01-01",
                            "title": "T", "summary_snippet": "persisted"}])
        store1.save()

        store2 = VectorStore(index_dir=tmp_path / "faiss")
        assert store2.count() == 1

    def test_empty_store_returns_empty(self, tmp_store):
        results = tmp_store.search(embed_query("anything"), top_k=5)
        assert results == []
