"""
analysis.py
Strip 격자 단면 후보군 정제 및 분석 스크립트

실행:
    python analysis.py

출력:
    outputs/filtered_candidates.xlsx  — Ix/Iy 필터 통과 후보
    outputs/efficiency_by_N.png       — N별 efficiency 변화 그래프
    outputs/stiffness_by_N.png        — N별 min(Ix,Iy) 변화 그래프
    콘솔: 구조 요약, 필터 전후 비교, N별 통계, 상위 후보 제안
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

warnings.filterwarnings('ignore')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs')

# ── 필터 기준 ─────────────────────────────────────────────────────
IX_IY_MIN = 0.80
IX_IY_MAX = 1.25


# ─────────────────────────────────────────────────────────────────
# 0. 데이터 로드
# ─────────────────────────────────────────────────────────────────
def load_data(path):
    df = pd.read_excel(path)
    df = df.rename(columns={
        'A(mm²)':  'A',
        'Ix(mm⁴)': 'Ix',
        'Iy(mm⁴)': 'Iy',
    })
    df['min_I'] = df[['Ix', 'Iy']].min(axis=1)
    return df


# ─────────────────────────────────────────────────────────────────
# 1~2. 파일 구조 요약
# ─────────────────────────────────────────────────────────────────
def print_structure(df):
    print("=" * 60)
    print("  [1-2] 파일 구조 요약")
    print("=" * 60)
    print(f"  시트    : Sheet1")
    print(f"  컬럼    : {df.columns.tolist()}")
    print(f"  전체 후보: {len(df):,}개")
    print()
    print("  N별 후보 수:")
    counts = df['strip_count'].value_counts().sort_index()
    for n, cnt in counts.items():
        stype = df[df['strip_count'] == n]['search_type'].iloc[0]
        tag   = '전수' if stype == '전수탐색' else 'GA'
        bar   = '#' * min(cnt // 1000 + 1, 30)
        print(f"    N={n:2d} [{tag}] {cnt:>6,}  {bar}")
    print()


# ─────────────────────────────────────────────────────────────────
# 3~4. Ix/Iy 비율 필터
# ─────────────────────────────────────────────────────────────────
def apply_filter(df):
    print("=" * 60)
    print(f"  [3-4] Ix/Iy 필터 적용  ({IX_IY_MIN} ≤ Ix/Iy ≤ {IX_IY_MAX})")
    print("=" * 60)

    before = len(df)
    filtered = df[df['Ix/Iy'].between(IX_IY_MIN, IX_IY_MAX)].copy()
    after    = len(filtered)

    print(f"  필터 전: {before:,}개")
    print(f"  필터 후: {after:,}개  (제거: {before - after:,}개, "
          f"통과율: {after/before*100:.1f}%)")
    print()

    print("  N별 필터 통과 수:")
    before_n   = df['strip_count'].value_counts().sort_index()
    after_n    = filtered['strip_count'].value_counts().sort_index()
    print(f"  {'N':>3}  {'필터전':>7}  {'필터후':>7}  {'통과율':>7}")
    print(f"  {'-'*30}")
    for n in sorted(df['strip_count'].unique()):
        b = before_n.get(n, 0)
        a = after_n.get(n, 0)
        pct = a / b * 100 if b > 0 else 0
        print(f"  {n:>3}  {b:>7,}  {a:>7,}  {pct:>6.1f}%")
    print()

    return filtered


# ─────────────────────────────────────────────────────────────────
# 5. 필터 통과 후보 저장
# ─────────────────────────────────────────────────────────────────
def save_filtered(filtered, path):
    print("=" * 60)
    print("  [5] 필터 통과 후보 저장")
    print("=" * 60)

    out = filtered.rename(columns={
        'A':     'A(mm²)',
        'Ix':    'Ix(mm⁴)',
        'Iy':    'Iy(mm⁴)',
        'min_I': 'min(Ix,Iy)(mm⁴)',
    })
    out = out.sort_values(['strip_count', 'efficiency'], ascending=[True, False])
    out.to_excel(path, index=False)
    print(f"  저장: {path}  ({len(out):,}행)")
    print()


# ─────────────────────────────────────────────────────────────────
# 6. N별 통계
# ─────────────────────────────────────────────────────────────────
def compute_stats(filtered):
    print("=" * 60)
    print("  [6] N별 구조 성능 통계 (필터 통과 후보 기준)")
    print("=" * 60)

    stats = (
        filtered.groupby('strip_count')
        .agg(
            count        = ('efficiency', 'count'),
            eff_max      = ('efficiency', 'max'),
            eff_mean     = ('efficiency', 'mean'),
            minI_max     = ('min_I',      'max'),
            minI_mean    = ('min_I',      'mean'),
        )
        .reset_index()
    )

    print(f"  {'N':>3}  {'후보':>6}  {'eff_max':>10}  {'eff_avg':>10}"
          f"  {'minI_max':>14}  {'minI_avg':>14}")
    print(f"  {'-'*65}")
    for _, row in stats.iterrows():
        print(
            f"  {int(row.strip_count):>3}  {int(row['count']):>6,}"
            f"  {row.eff_max:>10.4f}  {row.eff_mean:>10.4f}"
            f"  {row.minI_max:>14,.1f}  {row.minI_mean:>14,.1f}"
        )
    print()

    return stats


# ─────────────────────────────────────────────────────────────────
# 7. efficiency vs N 그래프
# ─────────────────────────────────────────────────────────────────
def plot_efficiency(stats, path):
    fig, ax = plt.subplots(figsize=(11, 5))

    ax.plot(stats['strip_count'], stats['eff_max'],
            'o-', color='#2166AC', linewidth=2, markersize=5,
            label='Max efficiency')
    ax.plot(stats['strip_count'], stats['eff_mean'],
            's--', color='#92C5DE', linewidth=1.5, markersize=4,
            label='Avg efficiency')

    # 증분 계산 — 효율 개선이 작아지는 구간 표시
    eff_max = stats['eff_max'].values
    ns      = stats['strip_count'].values
    deltas  = np.diff(eff_max)
    peak_gain_idx = int(np.argmax(deltas))  # 최대 증분 위치

    # 개선이 절반 이하로 떨어지는 첫 N
    half_gain = deltas[peak_gain_idx] * 0.5
    plateau_indices = np.where(deltas < half_gain)[0]
    if len(plateau_indices) > 0:
        plateau_n = ns[plateau_indices[0] + 1]
        ax.axvline(plateau_n, color='#D6604D', linestyle=':', linewidth=1.5,
                   label=f'수렴 시작 N={plateau_n}')

    ax.set_xlabel('Strip 수 (N)', fontsize=12)
    ax.set_ylabel('efficiency  =  min(Ix, Iy) / cost', fontsize=12)
    ax.set_title('N별 Efficiency 변화 (Ix/Iy 필터 통과 후보)', fontsize=13)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:,.1f}'))
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.35)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  [7] efficiency 그래프 저장: {path}")


# ─────────────────────────────────────────────────────────────────
# 8. min(Ix, Iy) vs N 그래프
# ─────────────────────────────────────────────────────────────────
def plot_stiffness(stats, path):
    fig, ax = plt.subplots(figsize=(11, 5))

    ax.plot(stats['strip_count'], stats['minI_max'] / 1e3,
            'o-', color='#1A9641', linewidth=2, markersize=5,
            label='Max min(Ix,Iy)')
    ax.plot(stats['strip_count'], stats['minI_mean'] / 1e3,
            's--', color='#A6D96A', linewidth=1.5, markersize=4,
            label='Avg min(Ix,Iy)')

    ax.set_xlabel('Strip 수 (N)', fontsize=12)
    ax.set_ylabel('min(Ix, Iy)  [×10³ mm⁴]', fontsize=12)
    ax.set_title('N별 최소 단면 2차 모멘트 변화 (Ix/Iy 필터 통과 후보)', fontsize=13)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.35)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  [8] stiffness 그래프 저장: {path}")


# ─────────────────────────────────────────────────────────────────
# 9. 수렴 구간 분석
# ─────────────────────────────────────────────────────────────────
def analyze_diminishing_returns(stats):
    print()
    print("=" * 60)
    print("  [9] Efficiency 증분 분석 (수렴 구간)")
    print("=" * 60)

    eff = stats['eff_max'].values
    ns  = stats['strip_count'].values
    deltas = np.diff(eff)

    print(f"  {'N→N+1':>8}  {'efficiency 증분':>16}  {'누적 효율 대비':>14}")
    print(f"  {'-'*44}")
    total_gain = eff[-1] - eff[0]
    for i, (d, n) in enumerate(zip(deltas, ns[:-1])):
        pct_of_total = d / total_gain * 100 if total_gain > 0 else 0
        print(f"  {n:>3}→{n+1:<3}  {d:>16.4f}  {pct_of_total:>13.1f}%")

    # 효율 증분이 최초 증분 대비 20% 미만인 첫 N
    first_delta = deltas[0] if deltas[0] != 0 else 1
    threshold   = abs(first_delta) * 0.20
    plateau_idx = next((i for i, d in enumerate(deltas) if abs(d) < threshold), None)

    print()
    if plateau_idx is not None:
        n_plateau = ns[plateau_idx + 1]
        print(f"  → N={n_plateau}부터 efficiency 증분이 초기 대비 20% 미만")
        print(f"    N={n_plateau-1}까지가 '비용 대비 효과' 상승 구간")
        print(f"    N={n_plateau} 이후는 strip 추가 대비 효율 개선이 작아짐 (수렴)")
    else:
        print("  → 탐색 범위 내에서 명확한 수렴 구간이 발견되지 않음")
    print()


# ─────────────────────────────────────────────────────────────────
# 10. 상위 후보군 제안
# ─────────────────────────────────────────────────────────────────
def propose_candidates(filtered, stats, top_k=10):
    print("=" * 60)
    print(f"  [10] 상위 후보군 제안 (최대 {top_k}개)")
    print("=" * 60)
    print("  ※ 현재 단계: 하중 미적용. 후보 정제 단계.")
    print()

    # N별로 efficiency 최고 1개씩 → 전체 efficiency 내림차순 top_k
    best_per_n = (
        filtered
        .sort_values('efficiency', ascending=False)
        .groupby('strip_count')
        .first()
        .reset_index()
        .sort_values('efficiency', ascending=False)
        .head(top_k)
    )

    print(f"  {'순위':>4}  {'N':>3}  {'cost':>5}  {'Ix/Iy':>7}"
          f"  {'min(Ix,Iy)':>13}  {'efficiency':>12}  name")
    print(f"  {'-'*70}")
    for rank, (_, row) in enumerate(best_per_n.iterrows(), 1):
        print(
            f"  {rank:>4}  {int(row.strip_count):>3}  {int(row.cost):>5}"
            f"  {row['Ix/Iy']:>7.4f}"
            f"  {row.min_I:>13,.1f}"
            f"  {row.efficiency:>12.4f}"
            f"  {row['name']}"
        )

    print()
    print("  선정 기준: N별 최고 efficiency 1개 추출 → 전체 상위 순위")
    print("  다음 단계: 실제 하중 조건 적용 후 최종 1개 선정 권장")
    print()

    return best_per_n


# ─────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────
def main():
    src_path      = os.path.join(OUTPUT_DIR, 'results_by_strip_count.xlsx')
    filtered_path = os.path.join(OUTPUT_DIR, 'filtered_candidates.xlsx')
    eff_graph     = os.path.join(OUTPUT_DIR, 'efficiency_by_N.png')
    stiff_graph   = os.path.join(OUTPUT_DIR, 'stiffness_by_N.png')

    print()
    df       = load_data(src_path)
    print_structure(df)

    filtered = apply_filter(df)
    save_filtered(filtered, filtered_path)

    stats    = compute_stats(filtered)
    plot_efficiency(stats, eff_graph)
    plot_stiffness(stats, stiff_graph)

    analyze_diminishing_returns(stats)
    propose_candidates(filtered, stats, top_k=10)


if __name__ == '__main__':
    main()
