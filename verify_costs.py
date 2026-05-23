import pandas as pd
lib = pd.read_excel('outputs/system/column_library.xlsx')
print('columns:', [c for c in lib.columns if 'cost' in c or 'eff' in c])
print()
print(f"  N  cost_1floor  cost_4floor  efficiency")
for n in [3,4,5,6,7]:
    s = lib[(lib['strip_count']==n) & (lib['rotation']==0)].iloc[0]
    c1 = s.get('cost_1floor', n*10)
    c4 = s['cost']
    eff = s['efficiency']
    print(f"  {n}  {c1:>11}  {c4:>11}  {eff:.4f}")
