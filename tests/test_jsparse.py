from fedstat.jsparse import js_lines_to_json, parse_js1, parse_js2

JS = """filters: {
0: { title: 'Показатель', values: { 31452: { title: 'Цена' } } },
3: { title: 'Год', values: { 2022: { title: '2022' }, 2023: { title: '2023' } } }
},
left_columns: [ 3 ],
top_columns: [ ],
groups: [],
grid.init();"""


def test_js_lines_to_json_quotes_bare_words():
    # JS-хак закавычивает всё, включая числа (как в оригинале R) -> id становятся строками
    obj = js_lines_to_json(["a: 1, b: 'x'"])
    assert obj == {"a": "1", "b": "x"}


def test_js_lines_to_json_strips_trailing_comma():
    assert js_lines_to_json(["a: 1,"]) == {"a": "1"}


def test_parse_js1_fields_and_values():
    filters = parse_js1(JS.split("\n"))
    assert set(filters) == {"0", "3"}
    assert filters["3"]["title"] == "Год"
    assert [v["title"] for v in filters["3"]["values"].values()] == ["2022", "2023"]


def test_parse_js2_object_lists():
    objects = parse_js2(JS.split("\n"))
    assert objects["left_columns"] == ["3"]
