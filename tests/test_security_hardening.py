import pytest

from utils.pdf_generator import _safe_join_under
from utils.template_renderer import calculate_footer_code


def test_footer_code_uses_uppercase_doctor_initial_and_rounding():
    exam_data = {
        'submit_time': '260401120000',
        'total_money': 1315600,
    }

    footer = calculate_footer_code(exam_data, doctor_name='bs. quang')
    assert footer == '260401120000B1316'


def test_footer_code_rounding_examples_match_expected():
    exam_data_1 = {'submit_time': '260401120001', 'total_money': 315000}
    exam_data_2 = {'submit_time': '260401120002', 'total_money': 315300}

    footer_1 = calculate_footer_code(exam_data_1, doctor_name='quang')
    footer_2 = calculate_footer_code(exam_data_2, doctor_name='quang')

    assert footer_1.endswith('Q315')
    assert footer_2.endswith('Q315')


def test_safe_join_under_rejects_traversal(tmp_path):
    base = tmp_path / 'pdf'
    base.mkdir()

    with pytest.raises(ValueError):
        _safe_join_under(str(base), '../evil.pdf', '.pdf')

    with pytest.raises(ValueError):
        _safe_join_under(str(base), '..\\evil.pdf', '.pdf')


def test_safe_join_under_rejects_wrong_extension(tmp_path):
    base = tmp_path / 'pdf'
    base.mkdir()

    with pytest.raises(ValueError):
        _safe_join_under(str(base), 'report.txt', '.pdf')


def test_safe_join_under_accepts_valid_path(tmp_path):
    base = tmp_path / 'pdf'
    base.mkdir()

    result = _safe_join_under(str(base), 'report.pdf', '.pdf')
    assert result.endswith('report.pdf')
