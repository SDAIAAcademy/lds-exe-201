# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Runs prototype A (safety reports) or B (contractors' questions) of LDS-EXE-201 on its ten cases.

With a hosted model: set three environment variables (see .env.example), taken from your provider's
own documentation and model list: LLM_BASE_URL (an OpenAI-compatible chat completions address),
LLM_MODEL and LLM_API_KEY. Without them, or when the model does not answer, the script replays the
recorded stand-in run in prototype/recorded/, which is scripted and not produced by a model.

    uv run labs/prototype/run_cases.py a
    uv run labs/prototype/run_cases.py b
    uv run labs/prototype/run_cases.py a --recorded     # force the recorded run

Only the synthetic files of the course are sent. Never put real company documents in.
"""
import csv
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

LABS = Path(__file__).resolve().parent.parent
FILES = LABS / 'files'
RUNS = Path(__file__).resolve().parent / 'runs'
sys.stdout.reconfigure(encoding='utf-8')

PROMPT_A = """أنت تساعد مسؤول السلامة في شركة خرسانة. التعليمات:
{brief}

البلاغ:
{text}

أجب بسطر JSON واحد فقط بالمفاتيح: hazard, severity, plant, stop"""

PROMPT_B = """أنت تكتب مسودة إجابة لمهندس المبيعات، من الدليل التالي وحده. لا تضف أي رقم ليس في الدليل.
إذا كان السؤال عن التصميم الإنشائي فلا تجب عنه وأحل السائل إلى المهندس الإنشائي المسؤول عن مشروعه.

الدليل:
{guide}

سؤال المقاول: {question}

المسودة في جملتين على الأكثر:"""


def read_csv(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def ask(prompt):
    base, model, key = (os.environ.get(k) for k in ('LLM_BASE_URL', 'LLM_MODEL', 'LLM_API_KEY'))
    if not (base and model and key):
        return None
    body = json.dumps({'model': model, 'temperature': 0,
                       'messages': [{'role': 'user', 'content': prompt}]}).encode('utf-8')
    req = urllib.request.Request(base.rstrip('/') + '/chat/completions', data=body,
                                 headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())['choices'][0]['message']['content'].strip()
    except Exception as e:  # a busy free model, a wrong key, no network
        print(f'  the model did not answer ({type(e).__name__}); using the recorded run for this case')
        return None


def recorded(which):
    data = json.loads((Path(__file__).resolve().parent / 'recorded' / f'run_{which}.json').read_text(encoding='utf-8'))
    return {r['case_id']: r['output'] for r in data['runs']}


def run_a(force):
    brief = (FILES / 'prototype_a' / 'brief.txt').read_text(encoding='utf-8')
    rec = recorded('a')
    out, passed, critical = [], 0, 0
    for c in read_csv(FILES / 'prototype_a' / 'cases.csv'):
        reply = None if force else ask(PROMPT_A.format(brief=brief, text=c['report_text']))
        source = 'model'
        try:
            got = json.loads(re.search(r'\{.*\}', reply, re.S).group(0)) if reply else None
        except (AttributeError, json.JSONDecodeError):
            got = None
        if got is None:
            got, source = rec[c['case_id']], 'recorded'
        fields = [str(got.get('hazard', '')), str(got.get('severity', '')), str(got.get('plant', '')), str(got.get('stop', ''))]
        expected = [c['expected_hazard'], c['expected_severity'], c['expected_plant'], c['expected_stop']]
        ok = fields == expected
        crit = c['expected_severity'] == '3' and fields[1] in ('1', '2')
        passed += ok
        critical += crit
        out.append([c['case_id'], *fields, 'نعم' if ok else 'لا', '' if ok else 'راجع الحقول المختلفة', 'نعم' if crit else 'لا', source])
        print(f"{c['case_id']} {'pass' if ok else 'FAIL'} ({source}) {fields}")
    print(f'prototype A: {passed}/10 passed, {critical} critical failures')
    return ['case_id', 'model_hazard', 'model_severity', 'model_plant', 'model_stop', 'pass', 'failure_type', 'critical', 'source'], out


def run_b(force):
    guide = (FILES / 'prototype_b' / 'product_guide.txt').read_text(encoding='utf-8')
    guide_numbers = set(re.findall(r'\d+', guide))
    rec = recorded('b')
    out = []
    for q in read_csv(FILES / 'prototype_b' / 'questions.csv'):
        reply = None if force else ask(PROMPT_B.format(guide=guide, question=q['question']))
        source = 'model' if reply else 'recorded'
        answer = reply or rec[q['case_id']]
        new_numbers = sorted(set(re.findall(r'\d+', answer)) - guide_numbers)
        hint = f'أرقام ليست في الدليل: {" ".join(new_numbers)}' if new_numbers else ''
        out.append([q['case_id'], answer, '', hint, '', source])
        print(f"{q['case_id']} ({source}) {answer}" + (f'  [{hint}]' if hint else ''))
    print('prototype B: score each answer against reference_answer in questions.csv; the hints only flag new numbers')
    return ['case_id', 'model_answer', 'pass', 'failure_type', 'critical', 'source'], out


if __name__ == '__main__':
    which = (sys.argv[1:] or ['a'])[0].lower()
    force = '--recorded' in sys.argv
    header, rows = run_a(force) if which == 'a' else run_b(force)
    if '--no-save' not in sys.argv:
        RUNS.mkdir(exist_ok=True)
        path = RUNS / f'results_{which}.csv'
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(header)
            w.writerows(rows)
        print('saved', path.relative_to(LABS))
