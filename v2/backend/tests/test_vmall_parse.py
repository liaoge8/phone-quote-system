# -*- coding: utf-8 -*-
import json

from app.routers.products import _parse_vmall_html


def _sbom(name, price, color, version, prom):
    return {
        "name": name, "price": price, "sbomPromWord": prom,
        "gbomAttrList": [
            {"attrName": "\u989c\u8272", "attrValue": color},
            {"attrName": "\u7248\u672c", "attrValue": version}],
        "majorAttrList": [
            {"attrName": "CPU\u578b\u53f7", "attrValue": "\u9e92\u9e9f8020A"},
            {"attrName": "\u7535\u6c60\u5bb9\u91cf", "attrValue": "8800mAh"}]}


def _sample_html():
    sbom_list = {
        "A1": _sbom("\u534e\u4e3a\u7545\u4eab\u6d4b\u8bd5\u673a 128GB \u66dc\u91d1\u9ed1", 1999,
                    "\u66dc\u91d1\u9ed1", "128GB", "\u5356\u70b9A"),
        "A2": _sbom("\u534e\u4e3a\u7545\u4eab\u6d4b\u8bd5\u673a 256GB \u96ea\u57df\u767d", 2399,
                    "\u96ea\u57df\u767d", "256GB", "\u5356\u70b9B")}
    current = {
        "name": "\u534e\u4e3a\u7545\u4eab\u6d4b\u8bd5\u673a",
        "brandName": "\u534e\u4e3a",
        "currentSbomCode": "A2",
        "colorSelectItem": [
            {"attrValue": "\u66dc\u91d1\u9ed1", "sbomCode": "A1"},
            {"attrValue": "\u96ea\u57df\u767d", "sbomCode": "A2"}],
        "productOptions": {"sbomList": sbom_list}}
    main_data = {"current": current}
    page_props = {"mainData": main_data}
    next_data = json.dumps({"props": {"pageProps": page_props}}, ensure_ascii=False)
    return ('<html><head><meta name="description" content="official channel"></head><body>'
            '<script id="__NEXT_DATA__" type="application/json">' + next_data + '</script></body></html>')


def test_parse_vmall_html_structure():
    parsed = _parse_vmall_html(_sample_html())
    assert parsed["name"] == "\u534e\u4e3a\u7545\u4eab\u6d4b\u8bd5\u673a"
    assert parsed["brand"] == "\u534e\u4e3a"
    assert parsed["model"] == "\u7545\u4eab\u6d4b\u8bd5\u673a"
    assert parsed["tagline"] in ("\u5356\u70b9A", "\u5356\u70b9B")
    assert "CPU\uff1a\u9e92\u9e9f8020A" in parsed["selling_points"][0] or "\u9e92\u9e9f8020A" in parsed["selling_points"][0]
    assert parsed["intro"].endswith("\u3002")
    assert parsed["official_price"] == 2399.0
    assert parsed["colors"] == ["\u66dc\u91d1\u9ed1", "\u96ea\u57df\u767d"]
    first = parsed["variants"][0]
    assert first["display_name"] == "128GB \u66dc\u91d1\u9ed1"
    assert first["version"] == "128GB"
    assert first["color"] == "\u66dc\u91d1\u9ed1"
    assert first["price"] == 1999.0


def test_parse_vmall_html_rejects_non_product_page():
    import pytest
    with pytest.raises(Exception):
        _parse_vmall_html("<html><head></head><body>no data</body></html>")