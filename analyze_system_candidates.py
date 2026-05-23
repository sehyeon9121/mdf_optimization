"""
analyze_system_candidates.py
설계 시나리오별 최소 비용 시스템 선정 -- 시스템 최적화 Step 4

목적:
  최고 efficiency가 아니라, 설계 조건을 만족하는 최소 비용 시스템을 찾는다.

공통 필터:
  1. torsion_risk = 'low'
  2. 0.80 <= system_Ix_Iy <= 1.25  (단면 균형 조건)

설계 시나리오 (min_system_I 기준, 코어 포함 전체 시스템):
  economy  : min_system_I >= 10,432 mm4  (= 4 x N=4 balanced, 2,608 x 4)
  baseline : min_system_I >= 31,680 mm4  (= 4 x N=5 balanced, 7,920 x 4)
  safety   : min_system_I >= 86,404 mm4  (= 4 x N=7 balanced, 21,601 x 4)

선정 기준 (조건 만족 후보 중):
  1차: total_cost 최소
  2차: norm_ecc 최소
  3차: |system_Ix_Iy - 1.0| 최소

출력:
  outputs/system/system_optimal_by_scenario.xlsx  (시나리오별 Top-5)
  outputs/system/pareto_cost_vs_minI.png
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

warnings.filterwarnings('ignore')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SYSTEM_DIR = os.path.join(BASE_DIR, 'outputs', 'system')

# ── 비용 계산 방식 선택 ──────────────────────────────────────────
# floor_by_floor : 층별 분리 (각 층 독립 절단, 층 경계 손실 발생)
# continuous     : 연속 제작 (4층 전체 통합, 손실 최소)
COST_MODE = 'floor_by_floor'
_COST_COL = {'floor_by_floor': 'total_cost_floor_sep',
             'continuous':      'total_cost_continuous'}

# ── 설계 시나리오 정의 ──────────────────────────────────────────
DESIGN_SCENARIOS = {
    'economy': {
        'min_I':       10_432,   # 4 x N=4 balanced
        'ref':         '4 x N4_bal (2,608 x 4)',
        'description': '최소 성능 만족 + 최소 비용 (N=4 수준)',
        'color':       '#2196F3',   # blue
        'marker':      'o',
    },
    'baseline': {
        'min_I':       31_680,   # 4 x N=5 balanced
        'ref':         '4 x N5_bal (7,920 x 4)',
        'description': '기준 성능 이상 (N=5 수준, 작년 N=4 대비 안전 여유)',
        'color':       '#4CAF50',   # green
        'marker':      's',
    },
    'safety': {
        'min_I':       86_404,   # 4 x N=7 balanced
        'ref':         '4 x N7_bal (21,601 x 4)',
        'description': '높은 안전 여유 확보 (N=7 수준)',
        'color':       '#F44336',   # red
        'marker':      '^',
    },
}

# 균형 조건
BAL_LO, BAL_HI = 0.80, 1.25

TOP_K = 5   # 시나리오별 출력 후보 수


def sep(title=''):
    print("=" * 70)
    if title:
        print(f"  {title}")
        print("=" * 70)


# ─────────────────────────────────────────────────────────────────
# Pareto 프론티어 계산 (비용 최소화 vs 성능 최대화)
# ─────────────────────────────────────────────────────────────────
def pareto_frontier(costs, performances):
    """
    (cost, performance) 점들 중 파레토 최적 (비용 낮을수록 & 성능 높을수록 우수)
    반환: pareto 인덱스 마스크
    """
    n = len(costs)
    is_pareto = np.ones(n, dtype=bool)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if costs[j] <= costs[i] and performances[j] >= performances[i]:
                if costs[j] < costs[i] or performances[j] > performances[i]:
                    is_pareto[i] = False
                    break
    return is_pareto


# ─────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────
def main():
    os.makedirs(SYSTEM_DIR, exist_ok=True)

    # ── 1. 데이터 로드 ─────────────────────────────────────────────
    sep("Step 1  데이터 로드")
    src = os.path.join(SYSTEM_DIR, 'system_candidates.xlsx')
    df  = pd.read_excel(src)
    print(f"  전체 시스템 후보: {len(df):,}개")
    print(f"  비용 계산 방식: {COST_MODE}")
    cost_col = _COST_COL[COST_MODE]
    print(f"  사용 비용 컬럼: {cost_col}")
    print()

    # ── 2. 공통 필터 ───────────────────────────────────────────────
    sep("Step 2  공통 필터 적용")
    cond_torsion = df['torsion_risk'] == 'low'
    cond_balance = df['system_Ix_Iy'].between(BAL_LO, BAL_HI)
    df_filt = df[cond_torsion & cond_balance].copy()

    print(f"  torsion_risk=low          : {cond_torsion.sum():>6,}개")
    print(f"  + 균형 조건 ({BAL_LO}~{BAL_HI}) : {len(df_filt):>6,}개")
    print()

    # 타이브레이크 정렬 보조 컬럼
    df_filt['_bal_dev'] = (df_filt['system_Ix_Iy'] - 1.0).abs()

    # ── 3. 시나리오별 선정 ─────────────────────────────────────────
    sep("Step 3  시나리오별 최소 비용 후보 선정 (Top-{})".format(TOP_K))

    results = {}
    all_tops = []

    for sname, scen in DESIGN_SCENARIOS.items():
        thresh = scen['min_I']

        cand = df_filt[df_filt['min_system_I'] >= thresh].copy()

        top = (cand
               .sort_values([cost_col, 'norm_ecc', '_bal_dev'],
                            ascending=[True, True, True])
               .head(TOP_K)
               .reset_index(drop=True))

        top.insert(0, 'rank',     range(1, len(top) + 1))
        top.insert(1, 'scenario', sname)

        results[sname] = top
        all_tops.append(top)

        print(f"\n  [{sname.upper()}]  min_system_I >= {thresh:,} mm4  "
              f"({scen['ref']})")
        print(f"  만족 후보: {len(cand):,}개")
        print()
        print(f"  {'rank':>4}  {'arr':^12}  {'C1':^18}  {'C2':^18}  "
              f"{'core':^15}  {'minI':>8}  {'fbf':>6}  {'cont':>6}  {'norm_e':>7}  {'IxIy':>6}")
        print(f"  {'-'*108}")
        for _, r in top.iterrows():
            print(f"  {int(r['rank']):>4}  {r['arrangement']:^12}  "
                  f"{r['C1_tag']:^18}  {r['C2_tag']:^18}  "
                  f"{r['core_scenario']:^15}  "
                  f"{r['min_system_I']:>8,.0f}  "
                  f"{int(r['total_cost_floor_sep']):>4}원  "
                  f"{int(r['total_cost_continuous']):>4}원  "
                  f"{r['norm_ecc']:>7.4f}  "
                  f"{r['system_Ix_Iy']:>6.4f}")

    print()

    # ── 4. 시나리오 간 비교 요약 ──────────────────────────────────
    sep("Step 4  시나리오 최적안 비교 요약 (Top-1 각, 두 방식 비용 비교)")
    print(f"  {'scenario':^10}  {'arrangement':^12}  {'C1/C2':^20}  "
          f"{'core':^15}  {'minI':>8}  {'fbf':>6}  {'cont':>5}  {'절감':>5}  {'norm_e':>7}")
    print(f"  {'-'*103}")
    for sname, top in results.items():
        if top.empty:
            print(f"  {sname:^10}  -- 조건 만족 후보 없음 --")
            continue
        r = top.iloc[0]
        col_summary = f"{r['C1_tag']}" if r['C1_tag'] == r['C2_tag'] else f"{r['C1_tag']}/{r['C2_tag']}"
        fbf  = int(r['total_cost_floor_sep'])
        cont = int(r['total_cost_continuous'])
        print(f"  {sname:^10}  {r['arrangement']:^12}  {col_summary:^20}  "
              f"{r['core_scenario']:^15}  "
              f"{r['min_system_I']:>8,.0f}  "
              f"{fbf:>4}원  {cont:>3}원  {fbf-cont:>+4}원  "
              f"{r['norm_ecc']:>7.4f}")
    print()

    # ── 5. 저장 (시나리오별 시트) ─────────────────────────────────
    sep("Step 5  저장")
    out_xlsx = os.path.join(SYSTEM_DIR, 'system_optimal_by_scenario.xlsx')

    # 출력 컬럼 순서
    out_cols = ['rank', 'scenario',
                'arrangement', 'C1_tag', 'C2_tag', 'C3_tag', 'C4_tag', 'core_scenario',
                'min_system_I', 'sum_Ix', 'sum_Iy', 'system_Ix_Iy',
                'col_cost_floor_sep', 'col_cost_continuous',
                'total_cost_floor_sep', 'total_cost_continuous', 'total_cost',
                'system_efficiency',
                'CR_x', 'CR_y', 'e_x', 'e_y', 'norm_ecc', 'torsion_risk']

    with pd.ExcelWriter(out_xlsx, engine='openpyxl') as writer:
        # 요약 시트 (Top-1 per scenario)
        summary_rows = []
        for sname, top in results.items():
            if top.empty: continue
            row = top.iloc[0].copy()
            summary_rows.append(row)
        summary_df = pd.DataFrame(summary_rows)
        available = [c for c in out_cols if c in summary_df.columns]
        summary_df[available].to_excel(writer, sheet_name='summary', index=False)

        # 시나리오별 시트
        for sname, top in results.items():
            available = [c for c in out_cols if c in top.columns]
            top[available].to_excel(writer, sheet_name=sname, index=False)

        # 전체 필터 통과 후보 (참고용)
        avail_filt = [c for c in out_cols[2:] if c in df_filt.columns]
        (df_filt[avail_filt]
         .sort_values(['total_cost', 'norm_ecc'])
         .reset_index(drop=True)
         .to_excel(writer, sheet_name='all_filtered', index=False))

    print(f"  저장: {out_xlsx}")
    print()

    # ── 6. Pareto 그래프 ──────────────────────────────────────────
    sep("Step 6  Pareto 그래프 (cost vs min_system_I)")

    fig, ax = plt.subplots(figsize=(11, 7))

    # 전체 후보 (회색)
    ax.scatter(df['total_cost'], df['min_system_I'],
               c='#DDDDDD', s=6, alpha=0.4, label='All candidates', zorder=1)

    # 필터 통과 후보 (파란색 계열)
    ax.scatter(df_filt['total_cost'], df_filt['min_system_I'],
               c='#90CAF9', s=15, alpha=0.6, label='Low torsion + balanced', zorder=2)

    # Pareto 프론티어 (필터 통과 기준)
    costs_f = df_filt['total_cost'].values
    minI_f  = df_filt['min_system_I'].values
    if len(costs_f) > 0:
        is_p = pareto_frontier(costs_f, minI_f)
        pf_df = df_filt[is_p].sort_values('total_cost')
        ax.plot(pf_df['total_cost'], pf_df['min_system_I'],
                'k--', linewidth=1.2, label='Pareto frontier', zorder=3)

    # 시나리오 임계선 (수평선) + Top-1 마커
    for sname, scen in DESIGN_SCENARIOS.items():
        thresh = scen['min_I']
        ax.axhline(thresh, color=scen['color'], linewidth=1.0,
                   linestyle=':', alpha=0.8)
        ax.text(df['total_cost'].min() - 2, thresh * 1.015,
                f"{sname} ({thresh:,})", color=scen['color'],
                fontsize=8, va='bottom')

        if sname in results and not results[sname].empty:
            r = results[sname].iloc[0]
            ax.scatter(r['total_cost'], r['min_system_I'],
                       c=scen['color'], s=160, marker=scen['marker'],
                       edgecolors='black', linewidths=1.0,
                       label=f"{sname} optimal  (cost={int(r['total_cost'])})",
                       zorder=5)
            ax.annotate(f"  {sname}\n  cost={int(r['total_cost'])}\n  {r['C1_tag']}",
                        xy=(r['total_cost'], r['min_system_I']),
                        xytext=(8, 4), textcoords='offset points',
                        fontsize=7.5, color=scen['color'])

    ax.set_xlabel('Total Cost (strips)', fontsize=11)
    ax.set_ylabel('min_system_I (mm$^4$)', fontsize=11)
    ax.set_title('System Candidates: Cost vs Structural Performance\n'
                 '(Pareto Frontier among Low-Torsion Balanced Candidates)',
                 fontsize=12)
    ax.legend(fontsize=8, loc='upper left')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    out_png = os.path.join(SYSTEM_DIR, 'pareto_cost_vs_minI.png')
    plt.savefig(out_png, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  저장: {out_png}")
    print()

    sep("완료")
    print("  outputs/system/system_optimal_by_scenario.xlsx")
    print("  outputs/system/pareto_cost_vs_minI.png")
    print()
    print("  [다음 단계 제안]")
    print("  analyze_system_candidates.py 결과를 바탕으로")
    print("  시나리오별 최적안의 단면 배치 시각화 및 구조 해석 연계")
    print()


if __name__ == '__main__':
    main()
