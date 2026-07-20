import pytest
from version_resolver import _cache_get

def test_cache_get_malformed_provider_data():
    cache = {
        "github_releases": None,  # corrupted cache
        "npm": [],                # corrupted cache
        "sqlite_org_page": "bad string"
    }
    
    # These should return empty dicts, but currently crash with AttributeError
    res1 = _cache_get(cache, "github_releases", "foo/bar")
    assert res1 == {}

    res2 = _cache_get(cache, "npm", "baz")
    assert res2 == {}
    
    res3 = _cache_get(cache, "sqlite_org_page", "sqlite-tools-win-x64")
    assert res3 == {}
