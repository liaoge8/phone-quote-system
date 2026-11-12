# -*- coding: utf-8 -*-
import json

from app.routers.products import _parse_vmall_html


def _sample_html():
    current = {}
    current["name"] = "\u534e\u4e3a\u7545\u4eab\u6d4b\u8bd5\u673a"
    current["brandName"] = "\u534e\u4e3a"
    current["currentSbomCode"] = "A2"
    current["colorSelectItem"] = [
        {"attrValue": "\u66dc\u91d1\u9ed1", "sbomCode": "A1"},
        {"attrValue": "\u96ea\u57df\u767d", "sbomCode": "A2"}]
    sbom_list = {
        "A1": {"name": "\u534e\u4e3a 128GB \u66dc\u91d1\u9ed1", "price": 1999},
        "A2": {"name": "\u534e\u4e3a 256GB \u96ea\u57df\u767d", "price": 2399}}
    current["productOptions"] = {"sbomList": sbom_list}
    main_data = {"current": current}
    page_props = {"mainData": main_data}
    next_data = json.dumps({"props": {"pageProps": page_props}}, ensure_ascii=False)
    return ('<html><head><meta name="description" content="official channel"></head><body>'
            '<script id="__NEXT_DATA__" type="application/json">' + next_data + '</script></body></html>')


def test_parse_vmall_html_structure():
    parsed = _parse_vmall_html(_sample_html())
    assert parsed["name"] == "\u534e\u4e3a\u7545\u4eab\u6d4b\u8bd5\u673a"
    assert parsed["brand"] == "\u534e\u4e3a"
    assert parsed["official_price"] == 2399.0
    assert parsed["colors"] == ["\u66dc\u91d1\u9ed1", "\u96ea\u57df\u767d"]
    assert len(parsed["variants"]) == 2
    assert parsed["description"].startswith("official channel")


def test_parse_vmall_html_rejects_non_product_page():
    import pytest
    with pytest.raises(Exception):
        _parse_vmall_html("<html><head></head><body>no data</body></html>")