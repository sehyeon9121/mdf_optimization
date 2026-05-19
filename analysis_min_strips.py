"""
analysis_min_strips.py
"요구 성능 만족 + strip 수 최소화" 기준으로 후보군 재분석

목적:
    efficiency 최대화가 아니라, 작년 4-strip 수준의 성능을 만족하는
    최소 strip 배치를 찾는다.

실행:
    python analysis_min_strips.py

입력:
    outputs/filtered_candidates.xlsx  (Ix/Iy 0.8~1.25 필터 적용된 파일)

출력:
    콘솔: N=4 기준 성능, 각 N별 최소 만족 후보
    outputs/min_strip_candidates.xlsx  -최소 만족 후보 정리 테이블
"""

import os
import warnings
import pandas as pd

warnings.filterwarnings('ignore')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs')


# ── 설정 ───────────────────────────────────────────────────────────
FOCUS_N = [3, 4, 5, 6, 7, 8, 9, 10]   # 집중 분석 구간
REF_N   = 16                        # efficiency 최고점 (참고용)


def sep(title=''):
    print("=" * 62)
    if title:
        print(f"  {title}")
        print("=" * 62)


# ─────────────────────────────────────────────────────────────────
# 1. 데이터 로드
# ─────────────────────────────────────────────────────────────────
def load():
    path = os.path.join(OUTPUT_DIR, 'filtered_candidates.xlsx')
    df = pd.read_excel(path)

    # 컬럼 표준화
    rename = {}
    for c in df.columns:
        if 'A(' in c:   rename[c] = 'A'
        if 'Ix(' in c:  rename[c] = 'Ix'
        if 'Iy(' in c:  rename[c] = 'Iy'
        if 'min' in c:  rename[c] = 'min_I'
    df = df.rename(columns=rename)

    if 'min_I' not in df.columns:
        df['min_I'] = df[['Ix', 'Iy']].min(axis=1)

    # Ix/Iy와 1.0의 차이 (균형 지표)
    df['balance'] = (df['Ix/Iy'] - 1.0).abs()

    return df


# ─────────────────────────────────────────────────────────────────
# 1b. N=3 상세 분석 (참고용 - 실제 성능 확인)
# ─────────────────────────────────────────────────────────────────
def analyze_n3(df):
    sep("Step 1b  N=3 후보 상세 분석 (실제 달성 성능 확인)")

    n3 = df[df['strip_count'] == 3].copy()
    print(f"  N=3 필터 통과 후보: {len(n3)}개\n")

    print(f"  [통계]")
    print(f"    efficiency  : min={n3['efficiency'].min():.4f}"
          f"  avg={n3['efficiency'].mean():.4f}"
          f"  max={n3['efficiency'].max():.4f}")
    print(f"    min(Ix,Iy)  : min={n3['min_I'].min():,.1f}"
          f"  avg={n3['min_I'].mean():,.1f}"
          f"  max={n3['min_I'].max():,.1f}  mm^4")
    print(f"    Ix/Iy 범위  : {n3['Ix/Iy'].min():.4f} ~ {n3['Ix/Iy'].max():.4f}")
    print()

    print(f"  [Ix/Iy 균형 상위 10 -기둥 등방성 관점]")
    print(f"  {'순위':>4}  {'N':>3}  {'Ix/Iy':>7}  "
          f"{'min_I':>12}  {'efficiency':>12}  name")
    print(f"  {'-'*58}")
    top_bal = n3.nsmallest(10, 'balance')
    for rank, (_, r) in enumerate(top_bal.iterrows(), 1):
        print(f"  {rank:>4}  {int(r.strip_count):>3}"
              f"  {r['Ix/Iy']:>7.4f}"
              f"  {r.min_I:>12,.1f}"
              f"  {r.efficiency:>12.4f}"
              f"  {r['name']}")
    print()

    print(f"  [efficiency 상위 10 -비용 효율 관점]")
    print(f"  {'순위':>4}  {'N':>3}  {'Ix/Iy':>7}  "
          f"{'min_I':>12}  {'efficiency':>12}  name")
    print(f"  {'-'*58}")
    top_eff = n3.nlargest(10, 'efficiency')
    for rank, (_, r) in enumerate(top_eff.iterrows(), 1):
        print(f"  {rank:>4}  {int(r.strip_count):>3}"
              f"  {r['Ix/Iy']:>7.4f}"
              f"  {r.min_I:>12,.1f}"
              f"  {r.efficiency:>12.4f}"
              f"  {r['name']}")
    print()

    return n3


# ─────────────────────────────────────────────────────────────────
# 2. N=4 상세 분석
# ─────────────────────────────────────────────────────────────────
def analyze_n4(df):
    sep("Step 1  N=4 후보 상세 분석 (Ix/Iy 필터 통과 기준)")

    n4 = df[df['strip_count'] == 4].copy()
    print(f"  N=4 필터 통과 후보: {len(n4)}개\n")

    # --- 전체 통계
    print(f"  [통계]")
    print(f"    efficiency  : min={n4['efficiency'].min():.4f}"
          f"  avg={n4['efficiency'].mean():.4f}"
          f"  max={n4['efficiency'].max():.4f}")
    print(f"    min(Ix,Iy)  : min={n4['min_I'].min():,.1f}"
          f"  avg={n4['min_I'].mean():,.1f}"
          f"  max={n4['min_I'].max():,.1f}  mm^4")
    print(f"    Ix/Iy 범위  : {n4['Ix/Iy'].min():.4f} ~ {n4['Ix/Iy'].max():.4f}")
    print()

    # --- Ix/Iy 균형 상위 10 (balance 최소 = 1.0에 가장 가까움)
    print(f"  [Ix/Iy 균형 상위 10 -기둥 등방성 관점]")
    print(f"  {'순위':>4}  {'N':>3}  {'Ix/Iy':>7}  "
          f"{'min_I':>12}  {'efficiency':>12}  name")
    print(f"  {'-'*58}")
    top_bal = n4.nsmallest(10, 'balance')
    for rank, (_, r) in enumerate(top_bal.iterrows(), 1):
        print(f"  {rank:>4}  {int(r.strip_count):>3}"
              f"  {r['Ix/Iy']:>7.4f}"
              f"  {r.min_I:>12,.1f}"
              f"  {r.efficiency:>12.4f}"
              f"  {r['name']}")
    print()

    # --- efficiency 상위 10
    print(f"  [efficiency 상위 10 -비용 효율 관점]")
    print(f"  {'순위':>4}  {'N':>3}  {'Ix/Iy':>7}  "
          f"{'min_I':>12}  {'efficiency':>12}  name")
    print(f"  {'-'*58}")
    top_eff = n4.nlargest(10, 'efficiency')
    for rank, (_, r) in enumerate(top_eff.iterrows(), 1):
        print(f"  {rank:>4}  {int(r.strip_count):>3}"
              f"  {r['Ix/Iy']:>7.4f}"
              f"  {r.min_I:>12,.1f}"
              f"  {r.efficiency:>12.4f}"
              f"  {r['name']}")
    print()

    return n4


# ─────────────────────────────────────────────────────────────────
# 3. I_required 설정
# ─────────────────────────────────────────────────────────────────
def set_i_required(n4):
    sep("Step 2  I_required 후보 설정 (N=4 기준 성능값)")

    i_max  = n4['min_I'].max()
    i_mean = n4['min_I'].mean()
    i_p75  = n4['min_I'].quantile(0.75)

    print(f"  N=4 min(Ix,Iy) 통계:")
    print(f"    최대값 (max)  : {i_max:>10,.1f} mm^4  ← 가장 엄격한 기준")
    print(f"    75백분위 (p75): {i_p75:>10,.1f} mm^4")
    print(f"    평균값 (mean) : {i_mean:>10,.1f} mm^4  ← 평균적인 N=4 성능")
    print()
    print(f"  → I_required = {i_max:,.1f} mm^4 (N=4 최고 성능) 로 설정")
    print(f"    ※ 이 기준은 '최소한 N=4 최고 단면 수준'을 의미")
    print(f"    ※ 완화 기준: {i_mean:,.1f} mm^4 (N=4 평균 수준) 도 함께 확인")
    print()

    return i_max, i_mean


# ─────────────────────────────────────────────────────────────────
# 4~6. 각 N별 최소 만족 후보 탐색
# ─────────────────────────────────────────────────────────────────
def find_min_cost_candidates(df, i_required_strict, i_required_relaxed):
    sep("Step 3  N별 'I_required 만족 + 최소 cost' 후보")

    print(f"  기준 A (엄격): min(Ix,Iy) >= {i_required_strict:,.1f} mm^4")
    print(f"  기준 B (완화): min(Ix,Iy) >= {i_required_relaxed:,.1f} mm^4")
    print()

    rows_strict  = []
    rows_relaxed = []

    all_n = sorted(df['strip_count'].unique())

    for i_req, label, rows in [
        (i_required_strict,  '엄격', rows_strict),
        (i_required_relaxed, '완화', rows_relaxed),
    ]:
        print(f"  [기준 {label}]  I_required = {i_req:,.1f} mm^4")
        print(f"  {'N':>3}  {'만족 후보':>8}  {'최소 cost':>9}  "
              f"{'min_I':>12}  {'Ix/Iy':>7}  {'efficiency':>11}  name")
        print(f"  {'-'*70}")

        for n in all_n:
            sub = df[(df['strip_count'] == n) & (df['min_I'] >= i_req)]
            if sub.empty:
                print(f"  {n:>3}  {'없음':>8}")
                continue

            # 최소 cost 중에서 efficiency 최고
            min_cost = sub['cost'].min()
            best = (sub[sub['cost'] == min_cost]
                    .nlargest(1, 'efficiency')
                    .iloc[0])

            print(f"  {n:>3}  {len(sub):>8,}  {int(best.cost):>9}"
                  f"  {best.min_I:>12,.1f}"
                  f"  {best['Ix/Iy']:>7.4f}"
                  f"  {best.efficiency:>11.4f}"
                  f"  {best['name']}")

            rows.append({
                'strip_count': int(n),
                'criteria':    label,
                'n_satisfy':   len(sub),
                'min_cost':    int(best.cost),
                'min_I':       round(best.min_I, 2),
                'Ix/Iy':       round(best['Ix/Iy'], 4),
                'efficiency':  round(best.efficiency, 4),
                'name':        best['name'],
            })

        print()

    return rows_strict, rows_relaxed


# ─────────────────────────────────────────────────────────────────
# 7. 저부재 구간 집중 분석 (N=4~7)
# ─────────────────────────────────────────────────────────────────
def focus_low_n(df, i_required_strict, i_required_relaxed):
    sep("Step 4  저부재 구간 집중 분석 (N=3~7)")

    for n in [3, 4, 5, 6, 7]:
        sub = df[df['strip_count'] == n]
        print(f"  --- N={n}  (전체 {len(sub):,}개 후보) ---")

        for i_req, label in [
            (i_required_strict,  '엄격'),
            (i_required_relaxed, '완화'),
        ]:
            sat = sub[sub['min_I'] >= i_req]
            if sat.empty:
                print(f"    기준 {label}: 만족 없음")
                continue

            best = sat.nsmallest(3, 'cost').copy()
            best = best.sort_values(['cost', 'efficiency'],
                                    ascending=[True, False])
            print(f"    기준 {label} ({len(sat):,}개 만족)"
                  f" -최소 cost 상위 3개:")
            for _, r in best.iterrows():
                print(f"      cost={int(r.cost)}  min_I={r.min_I:,.1f}"
                      f"  Ix/Iy={r['Ix/Iy']:.4f}"
                      f"  eff={r.efficiency:.4f}  {r['name']}")
        print()


# ─────────────────────────────────────────────────────────────────
# 8. 참고: N=16 최고 효율 후보
# ─────────────────────────────────────────────────────────────────
def show_reference(df):
    sep("Step 5  참고 후보: N=16 (efficiency 최고점)")
    print("  ※ 최종 후보로 선택하지 않음 -과설계 가능성")
    print()

    n16 = df[df['strip_count'] == REF_N].nlargest(3, 'efficiency')
    print(f"  {'N':>3}  {'cost':>5}  {'Ix/Iy':>7}  "
          f"{'min_I':>12}  {'efficiency':>12}  name")
    print(f"  {'-'*58}")
    for _, r in n16.iterrows():
        print(f"  {int(r.strip_count):>3}  {int(r.cost):>5}"
              f"  {r['Ix/Iy']:>7.4f}"
              f"  {r.min_I:>12,.1f}"
              f"  {r.efficiency:>12.4f}"
              f"  {r['name']}")
    print()


# ─────────────────────────────────────────────────────────────────
# 9. 결과 저장
# ─────────────────────────────────────────────────────────────────
def save_summary(rows_strict, rows_relaxed, path):
    all_rows = rows_strict + rows_relaxed
    if not all_rows:
        return
    df_out = pd.DataFrame(all_rows)
    df_out = df_out.sort_values(['criteria', 'strip_count'])
    df_out.to_excel(path, index=False)
    print(f"  저장: {path}")


# ─────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────
def main():
    print()
    print("  분석 기준: '요구 성능 만족 + strip 수 최소화'")
    print("  (efficiency 최대화 기준 → 폐기)")
    print()

    df = load()

    n3 = analyze_n3(df)
    n4 = analyze_n4(df)
    i_strict, i_relaxed = set_i_required(n4)

    rows_strict, rows_relaxed = find_min_cost_candidates(
        df, i_strict, i_relaxed
    )

    focus_low_n(df, i_strict, i_relaxed)
    show_reference(df)

    save_path = os.path.join(OUTPUT_DIR, 'min_strip_candidates.xlsx')
    save_summary(rows_strict, rows_relaxed, save_path)

    sep("분석 완료")
    print(f"  저장 파일: outputs/min_strip_candidates.xlsx")
    print()
    print("  [설계 방향 요약]")
    print(f"    - N=3 최대 성능: min(Ix,Iy) = {n3['min_I'].max():,.1f} mm^4"
          f"  (효율 최고: {n3['efficiency'].max():.4f})")
    print(f"    - N=4 기준 성능: min(Ix,Iy) = {i_strict:,.1f} mm^4"
          f"  (N=4 전체 균일)")
    print(f"    - N=3 달성 가능 여부: "
          + ("만족" if n3['min_I'].max() >= i_strict else
             f"미달 ({n3['min_I'].max():,.1f} < {i_strict:,.1f})"))
    print(f"    - 이 성능을 만족하는 최소 N → 위 표에서 '만족 후보 > 0' 첫 N")
    print(f"    - 다음 단계: 실제 하중 → I_required 확정 → 최종 단면 선정")
    print()


if __name__ == '__main__':
    main()
