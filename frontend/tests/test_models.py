from frontend.models import Source, prepare_sources


def make_source(chunk_id: str, page: int) -> Source:
    return Source(
        chunk_id=chunk_id,
        document_id="doc",
        title="Document",
        page=page,
        url="https://example.test/doc.pdf",
        similarity=0.7,
        text_preview="A short passage.",
    )


def test_duplicate_source_ids_are_removed_in_original_order() -> None:
    sources = [make_source("chunk-a", 1), make_source("chunk-b", 2), make_source("chunk-a", 3)]

    prepared = prepare_sources(sources)

    assert [source.chunk_id for source in prepared] == ["chunk-a", "chunk-b"]
    assert prepared[0].page == 1
