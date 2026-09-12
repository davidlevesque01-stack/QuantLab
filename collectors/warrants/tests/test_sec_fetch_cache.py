from collectors.warrants.src.sec_fetch_cache import SharedFetchCache


def test_get_index_documents_calls_fetch_fn_only_once_per_url():
    cache = SharedFetchCache()
    calls = []

    def fetch_fn(url):
        calls.append(url)
        return [f"documents for {url}"]

    first = cache.get_index_documents("https://example.com/a", fetch_fn)
    second = cache.get_index_documents("https://example.com/a", fetch_fn)

    assert first == ["documents for https://example.com/a"]
    assert second == first
    assert calls == ["https://example.com/a"]


def test_get_index_documents_calls_fetch_fn_separately_per_distinct_url():
    cache = SharedFetchCache()
    calls = []

    def fetch_fn(url):
        calls.append(url)
        return url

    cache.get_index_documents("https://example.com/a", fetch_fn)
    cache.get_index_documents("https://example.com/b", fetch_fn)

    assert calls == ["https://example.com/a", "https://example.com/b"]


def test_get_document_text_calls_fetch_fn_only_once_per_url():
    cache = SharedFetchCache()
    calls = []

    def fetch_fn(url):
        calls.append(url)
        return f"text for {url}"

    first = cache.get_document_text("https://example.com/doc.htm", fetch_fn)
    second = cache.get_document_text("https://example.com/doc.htm", fetch_fn)

    assert first == "text for https://example.com/doc.htm"
    assert second == first
    assert calls == ["https://example.com/doc.htm"]


def test_index_documents_and_document_text_caches_are_independent():
    """
    The same URL used as both an index URL and a document URL (not a
    realistic case, but confirms the two caches don't collide) should
    be tracked separately.
    """

    cache = SharedFetchCache()
    index_calls = []
    text_calls = []

    cache.get_index_documents("https://example.com/x", lambda url: index_calls.append(url))
    cache.get_document_text("https://example.com/x", lambda url: text_calls.append(url))

    assert index_calls == ["https://example.com/x"]
    assert text_calls == ["https://example.com/x"]
