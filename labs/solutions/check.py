# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Reference solution checker of LDS-EXE-201. Recomputes every key number of the labs from the
files in labs/files/ and asserts it. Standard library only.

    uv run labs/solutions/check.py          # every lab
    uv run labs/solutions/check.py 3.3      # one lab
"""
import csv
import json
import sys
from math import comb, floor, sqrt
from pathlib import Path

LABS = Path(__file__).resolve().parent.parent
FILES = LABS / 'files'
sys.path.insert(0, str(LABS / '_tools'))
import prepare_files as P  # noqa: E402  the generator holds the planted answers

sys.stdout.reconfigure(encoding='utf-8')


def rows(name):
    with open(FILES / name, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def wilson(k, n, z=1.959964):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def lab_1_1():
    dash = {r['id']: r for r in rows('ai_dashboard.csv')}
    assert len(dash) == 12
    kinds = {}
    for k, (kind, line) in P.DASHBOARD_KEY.items():
        kinds.setdefault(kind, []).append(k)
    value = kinds['قيمة']
    assert value == ['K07', 'K08', 'K11', 'K12'], value
    lines = {r['line_id'] for r in rows('income_statement_fy2025.csv')}
    assert all(P.DASHBOARD_KEY[k][1] in lines for k in value)
    disp = rows('dispatch_monthly_2025.csv')
    late = sum(int(r['returned_late_arrival']) for r in disp) / sum(int(r['loads']) for r in disp)
    assert f'{100 * late:.1f}' == dash['K07']['value'], late
    l_m3 = sum(int(r['truck_litres']) for r in disp) / sum(int(r['m3_delivered']) for r in disp)
    assert f'{l_m3:.2f}' == dash['K12']['value'], l_m3
    print('1.1 indicators by kind:', {k: len(v) for k, v in kinds.items()})
    print('1.1 value indicators and lines:', [(k, P.DASHBOARD_KEY[k][1]) for k in value])
    print('1.1 survey claims: (a) vendor sponsor, own customers, self-report; (b) one plant, six weeks, no comparison, any-cause returns; (c) forecast, not measured')


def lab_1_2_3():
    key = {d: (s, c) for d, s, c, _ in P.MATURITY_KEY}
    peer = {r['dimension']: int(r['peer_score']) for r in rows('peer_scores.csv')}
    first = ['الاستراتيجية', 'الحوكمة', 'البيانات', 'البنية التحتية']
    print('1.2 reference scores:', {d: key[d][0] for d in first})
    rest = ['القدرات البشرية', 'التطبيقات', 'الأثر']
    print('1.3 reference scores:', {d: key[d][0] for d in rest})
    gaps = {d: peer[d] - key[d][0] for d in key}
    assert sum(gaps.values()) == 8, gaps
    assert gaps['البنية التحتية'] == 0 and max(gaps.values()) == 2
    print('1.3 peer above reference by:', gaps, 'total', sum(gaps.values()))
    print('1.3 three gaps:', [g[0] for g in P.GAPS_KEY])
    ref = rows('maturity_start_reference.csv')
    assert [r['score_0_4'] for r in ref][4:] == ['', '', ''], 'lab 1.3 start must not show its own answers'


def lab_1_4():
    longlist = {r['id'] for r in rows('usecases_longlist.csv')}
    assert len(longlist) == 20 and not longlist & set(P.MISSING_FROM_LONGLIST)
    print('1.4 cards to find:', P.MISSING_FROM_LONGLIST, '(C02/P03, P02, T01/P04, R02, R01)')
    print('1.4 tool-first card in the long list: UC13')


def lab_2_1_2():
    ucs = rows('usecases_25.csv')
    assert len(ucs) == 25
    modes = {}
    for k, v in P.TRIAGE_KEY.items():
        modes.setdefault(v[2], []).append(k)
    quads = {}
    for k, v in P.TRIAGE_KEY.items():
        quads[(v[0], v[1])] = quads.get((v[0], v[1]), 0) + 1
    print('2.1 quadrants (ambiguity, risk), before the filters:', quads)
    print('2.2 modes after the filters:', {m: len(v) for m, v in modes.items()})
    for k, (amb, risk, mode, cat, owner, flag, note) in P.TRIAGE_KEY.items():
        quad = {('منخفض', 'منخفض'): 'أتمتة', ('منخفض', 'مرتفع'): 'إدارة بضوابط حماية',
                ('مرتفع', 'منخفض'): 'إتاحة الاستكشاف', ('مرتفع', 'مرتفع'): 'إبقاء القيادة للإنسان'}[(amb, risk)]
        assert mode == quad or (mode == 'مستبعد' and cat == 'غير مقبولة'), k
        if cat == 'عالية':
            assert owner, f'{k}: high risk needs a named owner'
    uc = {u['id']: u for u in ucs}
    genai_restricted = sorted(k for k, u in uc.items()
                              if 'توليدي' in u['technique'] and u['input_classification'] in ('مقيد', 'سري'))
    flagged = sorted(k for k, v in P.TRIAGE_KEY.items() if v[5] == 'نعم')
    assert genai_restricted == flagged, (genai_restricted, flagged)
    high = sorted(k for k, v in P.TRIAGE_KEY.items() if v[3] == 'عالية')
    print('2.2 GenAI on restricted or secret inputs:', flagged, len(flagged))
    print('2.2 high risk with owner:', [(k, P.TRIAGE_KEY[k][4]) for k in high], len(high))
    print('2.2 unacceptable:', [k for k, v in P.TRIAGE_KEY.items() if v[3] == 'غير مقبولة'])
    for k in ('UC01', 'UC02'):
        assert uc[k]['input_classification'] == 'عام', k


def lab_2_3():
    cases = rows('prototype_a/cases.csv')
    passed, crit = 0, 0
    for c in cases:
        out = P.PROTO_A_RUN.get(c['case_id'], (c['expected_hazard'], int(c['expected_severity']), c['expected_plant'], c['expected_stop']))
        ok = (out[0] == c['expected_hazard'] and out[1] == int(c['expected_severity'])
              and out[2] == c['expected_plant'] and out[3] == c['expected_stop'])
        passed += ok
        crit += int(c['expected_severity']) == 3 and out[1] < 3
    lo, hi = wilson(passed, 10)
    assert (passed, crit) == (8, 0)
    print(f'2.3 prototype A (recorded stand-in): {passed}/10, critical {crit}, Wilson 95% {lo:.0%} to {hi:.0%}: go, with a sample check')


def lab_2_4():
    lo7, hi7 = wilson(7, 10)
    print(f'2.4 slide example 7/10: Wilson 95% {lo7:.1%} to {hi7:.1%}')
    passed = sum(1 for v in P.PROTO_B_RUN.values() if v[1] == 'pass')
    crit = [k for k, v in P.PROTO_B_RUN.items() if v[1] == 'fail' and v[3] == 'نعم']
    lo, hi = wilson(passed, 10)
    assert passed == 6 and crit == ['B01', 'B04']
    refer = [q[0] for q in P.PROTO_B_QUESTIONS if q[3] == 'نعم']
    assert refer == ['B04', 'B07']
    print(f'2.4 prototype B (recorded stand-in): {passed}/10, critical {crit}, Wilson 95% {lo:.0%} to {hi:.0%}: rework')
    p8 = sum(comb(10, i) * 0.7 ** i * 0.3 ** (10 - i) for i in range(8, 11))
    print(f'2.4 a system right 70% of the time scores 8/10 or more with probability {p8:.0%}')


def tco():
    out = {}
    for opt in ('build', 'buy', 'partner'):
        items = [t for t in P.TCO_ITEMS if t[0] == opt]
        out[opt] = sum(t[2] for t in items) + 3 * sum(t[3] for t in items)
    return out


def scores(local_hosting=True):
    t = tco()
    low = min(t.values())
    s = {}
    for opt in ('build', 'buy', 'partner'):
        musts = [q[0] for q in P.REQUIREMENTS if q[2] == 'ضروري']
        met = sum(P.OPTION_FIT[opt][q] for q in musts) / len(musts)
        if opt == 'buy' and local_hosting:
            met = (sum(P.OPTION_FIT[opt][q] for q in musts) + 1) / len(musts)  # Q09 met by the paid local region
        fit = 5 if met == 1 else 4 if met >= .9 else 3 if met >= .8 else 2 if met >= .7 else 1
        if any(q in musts for q in P.OPTION_UNPROVEN[opt]):
            fit -= 1  # "can be met", no customer and no prototype yet (buy: Q04 by a quoted custom integration)
        cost = max(1, 5 - floor((t[opt] / low - 1) / 0.15 + 1e-9))
        data = {'build': 5, 'buy': 4 if local_hosting else 1, 'partner': 4}[opt]
        lock = {'build': 5, 'buy': 1, 'partner': 3}[opt]
        ttv = {'build': 2, 'buy': 5, 'partner': 4}[opt]
        s[opt] = dict(fit=fit, cost=cost, data=data, lock=lock, ttv=ttv,
                      total=30 * fit + 25 * cost + 20 * data + 10 * lock + 15 * ttv)
    return s


def lab_3_1_2():
    t = tco()
    assert t == {'build': 2960000, 'buy': 1146900, 'partner': 1670000}, t
    s = scores(True)
    s_off = scores(False)
    print('3.1 scores (local hosting):', {k: {x: v[x] for x in ('fit', 'data', 'lock', 'ttv')} for k, v in s.items()})
    print('3.2 TCO three years (SAR):', t)
    print('3.2 weighted totals out of 500:', {k: v['total'] for k, v in s.items()})
    print('3.2 without local hosting:', {k: v['total'] for k, v in s_off.items()})
    assert {k: v['total'] for k, v in s.items()} == {'build': 325, 'buy': 350, 'partner': 340}
    assert {k: v['total'] for k, v in s_off.items()} == {'build': 325, 'buy': 260, 'partner': 340}
    assert max(s, key=lambda k: s[k]['total']) == 'buy'
    assert max(s_off, key=lambda k: s_off[k]['total']) == 'partner'
    print('3.2 condition: buy only if driver location data stay in the Kingdom by contract; otherwise partner')


def value_trace():
    d = rows('dispatch_monthly_2025.csv')
    S = lambda k: sum(int(r[k]) for r in d)  # noqa: E731
    late = S('returned_late_arrival')
    v_returns = round(late * 0.30 * P.WRITE_OFF_SAR_PER_LOAD)
    v_fuel = round(S('empty_km') * 0.08 * P.LITRES_PER_EMPTY_KM * P.DIESEL_SAR_PER_L)
    v_ot = round(S('driver_overtime_hours') * 0.10 * P.OVERTIME_SAR_PER_HOUR)
    m3_per_load = S('m3_delivered') / S('loads')
    upside = round(S('orders_declined_no_truck') * m3_per_load * 61)
    return dict(late=late, empty_km=S('empty_km'), overtime=S('driver_overtime_hours'),
                declined=S('orders_declined_no_truck'), v_returns=v_returns, v_fuel=v_fuel, v_ot=v_ot,
                base=v_returns + v_fuel + v_ot, upside=upside)


def lab_3_3():
    v = value_trace()
    lines = {r['line_id']: int(r['sar_thousand']) for r in rows('income_statement_fy2025.csv')}
    fuel_all = (lines['COS-04'] + lines['COS-05']) * 1000
    vendor = round(0.15 * fuel_all)
    print('3.3 baseline 2025: late-arrival returns', v['late'], 'empty km', v['empty_km'], 'overtime h', v['overtime'],
          'declined orders', v['declined'])
    print('3.3 COS-10 returns', v['v_returns'], '| COS-04 fuel', v['v_fuel'], '| COS-07 overtime', v['v_ot'],
          '| base case', v['base'])
    print('3.3 not counted: dispatcher hours (no line moves), cement (inside COS-10), declined orders upside', v['upside'])
    print('3.3 vendor 15% applied to all fuel would claim', vendor, 'versus', v['v_fuel'])
    assert v['base'] == 1952387, v['base']
    half = v['base'] - v['v_returns'] / 2
    pb_half = 9 + tco()['buy'] / (half / 12)
    print(f'3.3 stretch: returns down 15% only gives {half:,.0f} a year; buy pays back in about {pb_half:.0f} months')
    assert half == 1382147 and pb_half < 24
    assert lines['COS-10'] == round(sum(int(r['returned_loads']) for r in rows('dispatch_monthly_2025.csv')) * 1.6)


def lab_3_4():
    cand = {r['id']: r for r in rows('portfolio_candidates.csv')}
    years = [0, 0, 0]
    for k in P.REFERENCE_PORTFOLIO:
        for i in range(3):
            years[i] += int(cand[k][f'cost_y{i + 1}'])
        if cand[k]['ethics_risk_category'] == 'عالية':
            assert cand[k]['owner'], k
        for dep in cand[k]['depends_on'].split():
            assert P.REFERENCE_PORTFOLIO[dep] <= P.REFERENCE_PORTFOLIO[k], (k, dep)
    assert all(y <= c for y, c in zip(years, P.BUDGET_YEAR_CAP)), years
    assert sum(years) <= P.BUDGET_TOTAL
    y1_with_uc17 = years[0] + int(cand['UC17']['cost_y1'])
    assert y1_with_uc17 > P.BUDGET_YEAR_CAP[0]
    uc03 = cand['UC03']
    cost = sum(int(uc03[f'cost_y{i}']) for i in (1, 2, 3))
    v = value_trace()
    assert abs(cost * 1000 - tco()['buy']) <= 1000, cost
    payback = 9 + (cost * 1000) / (v['base'] / 12)
    print('3.4 reference portfolio cost per year (SAR thousand):', years, 'total', sum(years), 'of', P.BUDGET_TOTAL)
    print('3.4 excluded:', list(P.EXCLUDED))
    print(f'3.4 UC03 payback at the base case: about {payback:.1f} months from approval (rule: 24)')
    print('3.4 adding UC17 breaks the year-1 cap:', y1_with_uc17)


LABS_RUN = {'1.1': lab_1_1, '1.2': lab_1_2_3, '1.3': lab_1_2_3, '1.4': lab_1_4, '2.1': lab_2_1_2, '2.2': lab_2_1_2,
            '2.3': lab_2_3, '2.4': lab_2_4, '3.1': lab_3_1_2, '3.2': lab_3_1_2, '3.3': lab_3_3, '3.4': lab_3_4}

if __name__ == '__main__':
    want = sys.argv[1:] or list(LABS_RUN)
    done = set()
    for lab in want:
        fn = LABS_RUN[lab]
        if fn not in done:
            fn()
            done.add(fn)
    print('PASS', ' '.join(want))
