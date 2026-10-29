"""X7: do the keepers' own dated entries peak on the days the committee's
summaries call a rush? (Not fully independent: the summaries were written
from the same returns. It tests the chain from text to date: sections,
roles, dates, carry-forward.)

Rush days: summary records whose quote says "rush" and whose date is a day
or a range of at most a week. Activity: the distinct station words with a
primary record on a date, all coasts of the report. Compared with the other
days of the same months; permutation p-value; broken by shifting the rush
days 10 days either way.

Run: python3 -I tools/rush_check.py
"""
import collections, csv, datetime as dt, os, random, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA


def main():
    R = list(csv.DictReader(open(os.path.join(DATA, 'records.csv'))))
    act = collections.defaultdict(set)
    for r in R:
        if r['source_kind'] == 'primary' and len(r['date']) == 10 and r['station_raw']:
            act[r['date']].add(r['station_raw'].strip().lower())
    A = {d: len(s) for d, s in act.items()}
    days = set()
    for r in R:
        if r['source_kind'] == 'summary' and re.search(r'\brush', r['quote'], re.I) and len(r['date']) == 10:
            d0 = dt.date.fromisoformat(r['date'])
            d1 = dt.date.fromisoformat(r['date_end']) if len(r['date_end']) == 10 else d0
            if 0 <= (d1 - d0).days <= 7:
                days |= {d0 + dt.timedelta(k) for k in range((d1 - d0).days + 1)}
    months = {(d.year, d.month) for d in days}
    pool = [dt.date(y, m, 1) + dt.timedelta(k) for (y, m) in months for k in range(31) if (dt.date(y, m, 1) + dt.timedelta(k)).month == m]
    mean = lambda ds: sum(A.get(d.isoformat(), 0) for d in ds) / len(ds)
    obs, base = mean(days), mean([d for d in pool if d not in days])
    rng = random.Random(1)
    null = [mean(rng.sample(pool, len(days))) for _ in range(5000)]
    p = (1 + sum(x >= obs for x in null)) / (1 + len(null))
    print(f'{len(days)} rush days in {len(months)} months; stations with entries per day: rush days {obs:.1f}, other days of those '
          f'months {base:.1f} (ratio {obs / base:.2f}); permutation p = {p:.4f}')
    for s in (10, -10):
        print(f'  broken: rush days shifted {s:+d} days: {mean({d + dt.timedelta(s) for d in days}):.1f}')


if __name__ == '__main__':
    main()
