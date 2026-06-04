import pandas as pd


df = pd.read_excel('raw-data.xlsx', sheet_name='Tabelle1', header=None)
header = df.iloc[0].tolist()
feature_names = [str(x).strip() for x in header[2:]]

is_month = df[0].astype(str).str.contains('年', na=False) & df[0].astype(str).str.contains('月', na=False)
is_data = pd.to_numeric(df[0], errors='coerce').notna() & (~is_month)
data = df.loc[is_data].copy()
N = len(data)

rows = []
for i, col in enumerate(data.columns[2:]):
    name = feature_names[i]
    s = data[col].astype(str).str.strip()
    valid_mask = (s != '未登録') & (s != 'nan') & (s != '')
    numeric = pd.to_numeric(s.where(valid_mask), errors='coerce')
    valid_numeric = numeric.dropna()
    valid_cnt = int(valid_numeric.shape[0])
    coverage = valid_cnt / N if N else 0.0
    unique_cnt = int(valid_numeric.nunique()) if valid_cnt else 0

    if valid_cnt >= 500 and coverage >= 0.50:
        status = 'MVP対象'
    elif valid_cnt >= 300 and coverage >= 0.30:
        status = '要注意'
    else:
        status = '対象外'

    rows.append(
        {
            'target': name,
            'valid_count': valid_cnt,
            'coverage': round(coverage, 4),
            'missing_rate': round(1 - coverage, 4),
            'unique_values': unique_cnt,
            'min': float(valid_numeric.min()) if valid_cnt else None,
            'max': float(valid_numeric.max()) if valid_cnt else None,
            'status': status,
        }
    )

out = pd.DataFrame(rows)
priority = {'MVP対象': 0, '要注意': 1, '対象外': 2}
out['_p'] = out['status'].map(priority)
out = out.sort_values(['_p', 'coverage'], ascending=[True, False]).drop(columns=['_p'])
out.to_csv('target-readiness.csv', index=False, encoding='utf-8-sig')

print('data_rows', N)
print('total_targets', len(out))
print('status_counts', out['status'].value_counts().to_dict())
print('--- top MVP targets ---')
print(out[out['status'] == 'MVP対象'].head(10).to_string(index=False))
print('--- caution targets ---')
print(out[out['status'] == '要注意'].head(10).to_string(index=False))
print('--- excluded targets ---')
print(out[out['status'] == '対象外'].head(10).to_string(index=False))
print('saved target-readiness.csv')
