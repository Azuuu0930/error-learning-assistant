"""Opt-in evidence scoring; legacy wording rules remain reproducible.

Only observations returned by the application are read. Code, traceback text,
case IDs and finding.evidence never create a diagnosis in this evaluator.
"""
import re

from evaluation import scoring as legacy

NEW_ACTIONABLE = {'assertion_failure', 'empty_iterator', 'iteration_mutation'}


def warning(analysis: dict) -> bool:
    return legacy.warning(analysis) or any(f.get('kind') in NEW_ACTIONABLE for f in analysis.get('findings', []))


def _count(value):
    return type(value) is int and value >= 0


def check_detection(expectation: str, pipeline: dict, *, ast_only: bool) -> dict:
    previous = legacy.check_detection(expectation, pipeline, ast_only=ast_only)
    previous['evidence_source'] = 'legacy' if previous['matched'] else None
    name = previous['concept']
    if name is None:
        return previous
    analysis = pipeline.get('code_analysis') or {}
    findings = analysis.get('findings', [])
    facts = analysis.get('facts', [])
    ids = legacy.identifiers(expectation)
    numbers = [int(n) for n in re.findall(r'\d+', expectation)]
    evidence = []
    def names_match(observed, ignored=()):
        wanted = set(ids) - set(ignored)
        return wanted <= {v for v in observed if isinstance(v, str)}

    if name == 'builtin_resolution':
        observed = [f for f in facts if f.get('kind') == 'builtin_reference']
        if names_match([f.get('subject') for f in observed], ('builtins',)):
            evidence.extend(observed)
    elif name == 'handled_exception':
        evidence.extend(f for f in facts if f.get('kind') == 'handled_exception'
                        and names_match([f.get('subject')], ('except',)))
    elif name == 'present_attribute':
        evidence.extend(f for f in facts if f.get('kind') == 'defined_attribute'
                        and names_match([f.get('subject'), f.get('details', {}).get('class_name')]))
    for finding in findings:
        kind, details = finding.get('kind'), finding.get('details') or {}
        subject = finding.get('target')
        related = [subject, details.get('function_name'), details.get('keyword')]
        if kind == 'call_arguments' and names_match(related):
            issue = details.get('argument_issue')
            required, supplied, maximum = (details.get(k) for k in ('required_count', 'supplied_count', 'maximum_positional'))
            if name == 'too_many_arguments' and issue == 'too_many' and _count(maximum) and _count(supplied) and supplied > maximum:
                evidence.append(finding)
            elif name == 'required_argument_count' and issue == 'missing' and _count(required) and (not numbers or numbers[0] == required):
                evidence.append(finding)
            elif name == 'supplied_argument_count' and issue == 'missing' and _count(supplied) and (not numbers or numbers[0] == supplied):
                evidence.append(finding)
            elif name == 'unknown_keyword' and issue == 'unexpected_keyword' and details.get('keyword'):
                evidence.append(finding)
        if name == 'missing_attribute' and kind == 'missing_attribute':
            if details.get('attribute') and names_match([details.get('receiver_type'), details.get('class_name'), details.get('attribute')]):
                evidence.append(finding)
        if name == 'mixed_bytes_string' and kind == 'incompatible_operation':
            if (details.get('operator') == '+' and {details.get('left_type'), details.get('right_type')} == {'bytes', 'str'}
                    and names_match([subject, details.get('left_type'), details.get('right_type'),
                                     details.get('left_name'), details.get('right_name')])):
                evidence.append(finding)
        if name == 'mixed_addition' and kind == 'incompatible_operation' and details.get('operator') == '+':
            left, right = details.get('left_type'), details.get('right_type')
            if (left and right and left != right and not {left, right} <= {'int', 'float', 'bool'}
                    and names_match([subject, left, right, details.get('left_name'), details.get('right_name')])):
                evidence.append(finding)
        requirements = {
            'zero_division': ('zero_division', 'ZeroDivisionError'),
            'false_assertion': ('assertion_failure', 'AssertionError'),
            'empty_iterator': ('empty_iterator', 'StopIteration'),
        }
        if name in requirements and (kind, details.get('exception_type')) == requirements[name]:
            # assert/next are Python keywords/functions, not independently requested subjects.
            if names_match([details.get('subject'), subject, 'assert', 'False', 'next']):
                evidence.append(finding)
        if name in {'dict_iteration_mutation', 'set_iteration_mutation'} and kind == 'iteration_mutation':
            expected_type = 'dict' if name == 'dict_iteration_mutation' else 'set'
            if details.get('exception_type') == 'RuntimeError' and details.get('container_type') == expected_type:
                if names_match([subject, expected_type]):
                    evidence.append(finding)
    if evidence:
        return {'expectation': expectation, 'concept': name, 'matched': True, 'evidence': evidence,
                'status': 'matched', 'evidence_source': 'structured'}
    return previous
