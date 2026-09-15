# Dataset Card: NIST AI Risk Management Corpus

## Purpose

This corpus supports a grounded RAG assistant that answers questions about the
NIST AI Risk Management Framework (AI RMF), its Generative AI Profile, and its
implementation Playbook.

## Corpus summary

| Metric | Value |
|---|---:|
| Documents | 3 PDFs |
| Pages | 259 |
| Extracted words (approx.) | 81,689 |
| OCR required | No |
| Source authority | U.S. National Institute of Standards and Technology |
| Retrieval language | English |

The corpus is deliberately narrow. The documents share terminology, which
makes the dataset useful for testing source discrimination, while remaining
small enough to ingest and evaluate on a laptop in one session.

## Files

| Local file | Document | Pages | Approx. words |
|---|---|---:|---:|
| `raw/nist_ai_rmf_1_0.pdf` | NIST AI 100-1, AI RMF 1.0 | 48 | 15,689 |
| `raw/nist_genai_profile.pdf` | NIST AI 600-1, Generative AI Profile | 64 | 20,976 |
| `raw/nist_ai_rmf_playbook.pdf` | NIST AI RMF Playbook | 147 | 45,024 |

Full provenance and SHA-256 checksums are stored in `metadata/sources.json`.

## Recommended ingestion contract

Create one record per page before chunking. Preserve these fields on every
chunk:

```json
{
  "chunk_id": "nist_ai_rmf_1_0-p0006-c00",
  "document_id": "nist_ai_rmf_1_0",
  "title": "Artificial Intelligence Risk Management Framework (AI RMF 1.0)",
  "page": 6,
  "source_url": "https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf",
  "text": "..."
}
```

Use token-aware chunks of **450 tokens with 80-token overlap**. Split within a
page, not across page boundaries, so citations can always resolve to one PDF
page. Remove repeated headers and footers, but do not remove section names,
table labels, function identifiers such as `GOVERN 1.1`, or list bullets.

## Evaluation

`evaluation_questions.csv` contains ten answerable questions and two negative
controls. During evaluation, record:

- whether any expected document appears in the retrieved top 4;
- whether the answer contains the expected facts;
- whether every factual claim is supported by a returned chunk;
- whether the model abstains on the negative controls.

Do not use the evaluation questions as documents in the vector store.

## Limitations

- The corpus covers NIST guidance, not binding legal requirements.
- The Playbook is implementation guidance and is not a checklist that every
  organization must follow.
- NIST is revising AI RMF 1.0; the dataset must be versioned rather than silently
  replacing source files.
- PDF tables may lose layout under plain text extraction. Keep page metadata and
  inspect table-heavy retrieval failures during evaluation.

