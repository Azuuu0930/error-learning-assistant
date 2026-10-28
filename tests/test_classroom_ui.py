from pathlib import Path
from uuid import uuid4
import json

import pytest
from streamlit.testing.v1 import AppTest

from src.analyzer import analyze_error
from src.classroom import build_card, encode_card, load_cards

APP = Path(__file__).resolve().parents[1] / 'app.py'


@pytest.fixture
def app():
    return AppTest.from_file(str(APP), default_timeout=20).run()


def analyze(app, language='Python'):
    app.selectbox(key='source_language').set_value(language)
    app.text_area(key='error_log').input("NameError: name 'PRIVATE_NAME' is not defined" if language == 'Python'
                                       else "main.c:2: error: 'PRIVATE_NAME' undeclared identifier")
    app.text_area(key='source_code').input('print(PRIVATE_NAME)' if language == 'Python' else 'int main(void) { return PRIVATE_NAME; }')
    app.button(key='analyze').click().run()
    assert not app.exception


def test_default_role_preserves_existing_student_inputs(app):
    assert app.radio(key='workspace_role').value == '学生'
    assert app.text_area(key='error_log')
    assert not any(x.value == '先生の授業サポート' for x in app.subheader)


def test_teacher_role_never_displays_student_secret_or_aggregates_it_automatically(app):
    analyze(app)
    app.radio(key='workspace_role').set_value('先生').run()
    assert not app.exception
    assert not app.text_area
    visible = '\n'.join(str(x.value) for group in (app.text, app.caption, app.markdown, app.json) for x in group)
    assert 'PRIVATE' not in visible
    assert not app.metric
    assert any('まだカードを読み込んでいません' in x.value for x in app.info)
    app.radio(key='workspace_role').set_value('学生').run()
    assert app.text_area(key='source_code').value == 'print(PRIVATE_NAME)'
    assert app.session_state['analysis'].error.error_type == 'NameError'
    assert not app.exception


def test_student_card_does_not_reveal_answers_or_raw_input_and_keeps_id_on_status_change(app):
    analyze(app)
    value = app.session_state['consultation_card']
    ident = value['card_id']
    assert value['hint_step'] == 0 and value['fix_viewed'] is False
    assert b'PRIVATE' not in encode_card(value)
    assert not any('Taro' in x.value for x in app.code)
    app.selectbox(key='card_learning_status').set_value('stuck').run()
    assert app.session_state['consultation_card']['card_id'] == ident
    assert app.session_state['consultation_card']['learning_status'] == 'stuck'
    for _ in range(3):
        app.button(key='next_hint').click().run()
    app.button(key='reveal_fix').click().run()
    assert app.session_state['consultation_card']['fix_viewed'] is True
    assert app.session_state['consultation_card']['hint_step'] == 3
    assert not app.exception


def test_reanalysis_rotates_card_id_and_code_edit_removes_old_card(app):
    analyze(app)
    ident = app.session_state['consultation_card']['card_id']
    app.button(key='analyze').click().run()
    assert app.session_state['consultation_card']['card_id'] != ident
    app.text_area(key='source_code').input('print(1)').run()
    assert 'consultation_card' not in app.session_state


def test_normal_mode_fix_viewing_is_reported_as_unmeasured(app):
    analyze(app)
    app.radio(key='display_mode').set_value('通常モード').run()
    assert app.session_state['consultation_card']['fix_viewed'] is None


def test_teacher_filter_rerender_and_clear_are_card_based(app):
    py = build_card(analyze_error('NameError: missing'), card_id=str(uuid4()), learning_status='stuck')
    c = build_card(analyze_error('Segmentation fault', language='c'), card_id=str(uuid4()))
    app.radio(key='workspace_role').set_value('先生').run()
    app.session_state['teacher_batch'] = load_cards([encode_card(py), encode_card(c)])
    app.run()
    assert app.metric[0].value == '2'
    app.run()
    assert app.metric[0].value == '2'
    app.selectbox(key='teacher_language').set_value('c').run()
    assert app.metric[0].value == '1'
    assert not app.exception
    app.button(key='clear_teacher_cards').click().run()
    assert not app.metric
    assert 'teacher_batch' not in app.session_state


@pytest.mark.parametrize('language,highlight', [('C','c'), ('C++','cpp')])
def test_c_family_inputs_examples_and_fixes_use_the_selected_language(app, language, highlight):
    app.selectbox(key='source_language').set_value(language).run()
    assert ('std::' in app.text_area(key='error_log').placeholder) is (language == 'C++')
    app.selectbox(key='language_example').set_value('name').run()
    assert app.selectbox(key='source_language').value == language
    assert 'PRIVATE' not in app.text_area(key='source_code').value
    app.radio(key='display_mode').set_value('通常モード')
    app.button(key='analyze').click().run()
    assert any(x.language == highlight and 'int main' in x.value for x in app.code)
    assert app.session_state['consultation_card']['language'] == highlight
    assert not app.exception
