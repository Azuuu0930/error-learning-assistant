"""相談カードは自由入力を出力せず、集計はカード単位で扱う。"""
import json
from uuid import uuid4

import pytest

from src.analyzer import analyze_error
from src.classroom import (
    MAX_CARD_BYTES, MAX_BATCH_BYTES, MAX_FILES, build_card, encode_card,
    decode_card, load_cards, summarize, summary_csv, card_preview,
)


def card(**changes):
    result = analyze_error("NameError: name 'PRIVATE_NAME' is not defined")
    return dict(build_card(result, card_id=str(uuid4())), **changes)


def payload(value):
    return json.dumps(value, ensure_ascii=False).encode('utf-8')


def test_export_is_allowlisted_and_never_contains_input_secrets():
    result = analyze_error('  File "PRIVATE_PATH.py", line 2\nNameError: name \'PRIVATE_NAME\' is not defined',
                           'PRIVATE_NAME = "PRIVATE_VALUE"\nprint(PRIVATE_OTHER)')
    value = build_card(result, card_id=str(uuid4()), hint_step=2, fix_viewed=False)
    raw = encode_card(value)
    assert b'PRIVATE' not in raw
    assert decode_card(raw) == value
    assert set(value) == {'schema_version', 'card_id', 'app_release', 'language', 'environment',
                          'error_type', 'diagnostic_code', 'category', 'phase', 'concept_candidates',
                          'analysis_status', 'hint_step', 'fix_viewed', 'learning_status'}
    assert 'PRIVATE' not in json.dumps(card_preview(value), ensure_ascii=False)


def test_unknown_custom_exception_name_is_not_exported():
    value = build_card(analyze_error('PRIVATE_CUSTOM_Error: PRIVATE_MESSAGE'), card_id=str(uuid4()))
    assert value['error_type'] == 'unknown'
    assert value['phase'] == 'unknown' and value['category'] == 'unknown'
    assert b'PRIVATE' not in encode_card(value)


@pytest.mark.parametrize('language,log,phase,concept', [
    ('python', 'SyntaxError: invalid syntax', 'compile', 'syntax'),
    ('python', "IndexError: out of range", 'runtime', 'collections'),
    ('python', 'UnboundLocalError: local variable', 'runtime', 'scope'),
    ('c', "main.c:2: error: 'total' undeclared identifier", 'compile', 'names'),
    ('cpp', "undefined reference to `render()'", 'link', 'build'),
    ('c', 'Segmentation fault', 'runtime', 'memory'),
])
def test_language_phase_and_concept_remain_separate(language, log, phase, concept):
    value = build_card(analyze_error(log, language=language), card_id=str(uuid4()))
    assert value['language'] == language and value['phase'] == phase
    assert concept in value['concept_candidates']
    assert decode_card(encode_card(value)) == value


@pytest.mark.parametrize('changes', [
    {'schema_version': True}, {'schema_version': 2}, {'schema_version': 1.0},
    {'hint_step': True}, {'hint_step': -1}, {'hint_step': 4}, {'hint_step': 1.5},
    {'fix_viewed': True},
    {'fix_viewed': 1}, {'fix_viewed': 'false'}, {'language': 'ruby'},
    {'environment': 'private-machine'}, {'learning_status': 'PRIVATE'},
    {'error_type': 'PRIVATE_Error'}, {'category': 'unknown'}, {'phase': 'compile'},
    {'concept_candidates': ['scope']}, {'concept_candidates': 'names'},
    {'concept_candidates': ['names', 'names']}, {'analysis_status': 'success'},
    {'diagnostic_code': 'C2065'}, {'card_id': 'PRIVATE_ID'},
    {'card_id': '00000000-0000-0000-0000-000000000000'}, {'app_release': 'private-version'},
])
def test_invalid_fields_and_inconsistent_facts_are_rejected(changes):
    value = card()
    value.update(changes)
    with pytest.raises(ValueError):
        decode_card(payload(value))


def test_extra_fields_cannot_smuggle_code_and_errors_do_not_echo_content():
    value = card()
    value['source_code'] = 'PRIVATE_SECRET'
    with pytest.raises(ValueError) as caught:
        decode_card(payload(value))
    assert 'PRIVATE' not in str(caught.value) and 'source_code' not in str(caught.value)


@pytest.mark.parametrize('raw', [b'', b'not-json', b'[]', b'null', b'\xff',
                                b'[' * 1100 + b']' * 1100, b'{"schema_version":1,"schema_version":1}'])
def test_malformed_json_and_duplicate_keys_never_crash_the_importer(raw):
    batch = load_cards([encode_card(card()), raw])
    assert len(batch.cards) == 1 and batch.invalid == 1


def test_card_size_limit_is_checked_before_parsing():
    with pytest.raises(ValueError):
        decode_card(b' ' * (MAX_CARD_BYTES + 1))


def test_batch_limits_are_rejected_without_partial_aggregation():
    with pytest.raises(ValueError):
        load_cards([b'{}'] * (MAX_FILES + 1))
    with pytest.raises(ValueError):
        load_cards([b' ' * (MAX_BATCH_BYTES // 2 + 1)] * 2)


def test_exact_duplicates_are_counted_once():
    value = card()
    batch = load_cards([payload(value), json.dumps(value, indent=2).encode()])
    assert len(batch.cards) == 1 and batch.duplicates == 1
    assert batch.invalid == batch.conflicts == 0


def test_conflicting_id_is_excluded_in_every_order():
    first = card()
    second = dict(first, learning_status='resolved')
    other = card()
    for values in [[first, second, other], [other, second, first], [first, first, second, other]]:
        batch = load_cards([payload(x) for x in values])
        assert [x['card_id'] for x in batch.cards] == [other['card_id']]
        assert batch.conflicts == 1


def test_summary_counts_cards_and_self_reports_and_respects_filters():
    a = card(hint_step=3, learning_status='stuck', fix_viewed=False)
    b = card(learning_status='resolved', fix_viewed=None)
    c = build_card(analyze_error('Segmentation fault', language='c'), card_id=str(uuid4()))
    result = summarize([a, b, c])
    assert (result['total'], result['stuck'], result['hint3'], result['unanswered']) == (3, 1, 1, 1)
    assert result['fix_unmeasured'] == 2
    assert result['by_language'] == {'python': 2, 'c': 1}
    assert summarize([a, b, c], language='c')['total'] == 1
    assert summarize([a, b, c], phase='compile')['total'] == 0
    assert summarize([])['total'] == 0
    csv = summary_csv(result).decode('utf-8-sig')
    assert '相談件数' in csv and '自己申告' in csv and 'PRIVATE' not in csv


def test_summary_rejects_unvalidated_cards_instead_of_exporting_arbitrary_labels():
    with pytest.raises(ValueError):
        summarize([dict(card(), error_type='=PRIVATE_FORMULA')])
