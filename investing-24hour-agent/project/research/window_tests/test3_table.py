"""TEST 3 table: same in-play sets, entries 9:35 vs 10:00 vs 10:15, exit at close (2020-2026 sample, from test2_results.csv)."""
import pandas as pd
R = pd.read_csv('test2_results.csv')
R = R[(R.sample_start == 2020) & (R.exit == 'close') & R.entry.isin(['9:35', '10:00', '10:15'])]
T = R.pivot_table(index=['set', 'side', 'period'], columns='entry', values='mean_bps').round(2)
T['gross_9:35'] = T['9:35'] + 20; T['wait_cost_10:00_vs_9:35'] = (T['10:00'] - T['9:35']).round(2); T['wait_cost_10:15_vs_9:35'] = (T['10:15'] - T['9:35']).round(2)
T.to_csv('test3_results.csv'); print(T.to_string())
