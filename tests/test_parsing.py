import math
from build_structured_json import parse_eu_number, _post_process_kaek, orient_coverage, COVERAGE_KEYS
from benchmark_evaluation import normalize_owner_component, equivalent_kaek


def test_parse_eu_number_basic():
    assert parse_eu_number('123') == 123.0
    assert parse_eu_number('1.234') == 1234.0  # thousands
    assert parse_eu_number('12.345') == 12345.0
    assert parse_eu_number('1.234,56') == 1234.56
    assert parse_eu_number('-1.234,56') == -1234.56
    assert parse_eu_number('7.5') == 7.5  # decimal heuristic


def test_parse_eu_number_edge_cases():
    # Ambiguous pattern fallback
    assert parse_eu_number('1.000') == 1000.0
    assert parse_eu_number('1.0') == 1.0
    assert parse_eu_number('--') is None
    assert parse_eu_number('') is None


def test_post_process_kaek_reconstruct_suffix():
    raw = '... 50097350003 / 0 / 0  ΚΑΕΚ ...'  # fragmented representation
    fixed = _post_process_kaek(raw, '50097350003')
    assert fixed.endswith('/0/0')


def test_equivalent_kaek_leading_zero():
    assert equivalent_kaek('050097350003', '50097350003')
    assert not equivalent_kaek('0050097350003', '50097350003')  # more than one leading zero difference


def test_owner_normalization():
    s = 'Α.Ε. Παράδειγμα (REG CODE)'  # corporate tokens + parentheses
    norm = normalize_owner_component(s)
    # Corporate tokens removed; accents stripped
    assert 'AE' not in norm
    assert 'ΠΑΡΑΔΕΙΓΜΑ' in norm


def test_orient_coverage_structure():
    # Provide partial coverage map, missing values should become 0.0
    cov_map = {COVERAGE_KEYS[0]: [1.0, 2.0, None, 4.0]}
    oriented = orient_coverage(cov_map)
    assert set(oriented.keys()) == {'ΥΦΙΣΤΑΜΕΝΑ','ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ','ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ','ΣΥΝΟΛΟ'}
    assert oriented['ΥΦΙΣΤΑΜΕΝΑ'][COVERAGE_KEYS[0]] == 1.0
    assert oriented['ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ'][COVERAGE_KEYS[0]] == 0.0  # None -> 0.0 fill
