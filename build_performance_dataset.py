"""
build_performance_dataset.py
5개 대표 후보 → 4층 전단빌딩 모델 구조 성능 데이터셋 생성

전단빌딩 모델 가정:
  - 기둥: fixed-fixed (양단 고정), story stiffness = Σ(12EI/h³)
  - 하중: 삼각형 분포, V_base = 1 N (정규화)  F_i ∝ i×h
  - 모든 층 동일 기둥 단면 (현 모델)
  - x방향 횡력 → Iy로 저항, y방향 횡력 → Ix로 저항

출력:
  outputs/system/performance_dataset.xlsx
  outputs/system/performance_dataset.csv
"""

import os
import math
import pandas as pd
import numpy as np

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SYSTEM_DIR = os.path.join(BASE_DIR, 'outputs', 'system')

# ── 구조 해석 상수 ─────────────────────────────────────────────────
E_MDF      = 3500      # N/mm²  MDF 탄성계수 (대표값)
FLOOR_H    = 200       # mm     층고
NUM_FLOORS = 4
L_SPAN     = 150       # mm     스팬 (비틀림 정규화 기준)

# fixed-fixed column stiffness factor: k = K_FACTOR × I
K_FACTOR = 12 * E_MDF / (FLOOR_H ** 3)   # = 12×3500/8e6 = 0.00525 N/mm per mm⁴

# 삼각형 분포 하중: F_i ∝ floor height, Σ F_i = V_base = 1 N
FLOOR_HTS   = [FLOOR_H * (i + 1) for i in range(NUM_FLOORS)]  # [200,400,600,800]
SUM_HTS     = sum(FLOOR_HTS)                                   # 2000
F_FLOOR     = [1.0 * h / SUM_HTS for h in FLOOR_HTS]          # [0.1, 0.2, 0.3, 0.4]
# Story shear (cumulative from top): V_i = Σ F_j (j >= i, 1-based)
STORY_SHEAR = [sum(F_FLOOR[i:]) for i in range(NUM_FLOORS)]    # [1.0, 0.9, 0.7, 0.4]

# ── 비용 상수 ──────────────────────────────────────────────────────
UNIT_PRICE     = 10
PIECES_PER_MBR = 3     # 600mm / 200mm = 3
COST_MODE      = 'floor_by_floor'

# ── 5개 대표 케이스 정의 ───────────────────────────────────────────
# cols_Ix / cols_Iy: [C1, C2, C3, C4] 단면 2차모멘트 (mm⁴)
# col_N_list        : 각 기둥의 N값 (비용 계산)
# Ix_core / Iy_core : 코어 단면 2차모멘트
# core_n            : 코어 1층 기준 스트립 수 (비용 계산)
CASES = [
    {
        'case_id':           'C01',
        'base_layout':       'minimum',
        'column_combination':'N4_bal x4  (uniform_4)',
        'core_type':         'none',
        'arrangement':       'uniform_4',
        'cols_Ix':  [2608, 2608, 2608, 2608],
        'cols_Iy':  [2608, 2608, 2608, 2608],
        'col_N_list': [4, 4, 4, 4],
        'Ix_core': 0,    'Iy_core': 0,    'core_n': 0,
    },
    {
        'case_id':           'C02',
        'base_layout':       'economy',
        'column_combination':'N5_bal + N3_bal  (diag_pair)',
        'core_type':         'none',
        'arrangement':       'diag_pair',
        # C1=C4=N5_bal_0, C2=C3=N3_bal_90
        'cols_Ix':  [7960, 1736, 1736, 7960],
        'cols_Iy':  [7920, 1776, 1776, 7920],
        'col_N_list': [5, 3, 3, 5],
        'Ix_core': 0,    'Iy_core': 0,    'core_n': 0,
    },
    {
        'case_id':           'C03',
        'base_layout':       'baseline',
        'column_combination':'N7_bal + N3_bal  (diag_pair)',
        'core_type':         'none',
        'arrangement':       'diag_pair',
        # C1=C4=N7_bal_0, C2=C3=N3_bal_90
        'cols_Ix':  [21641, 1736, 1736, 21641],
        'cols_Iy':  [21601, 1776, 1776, 21601],
        'col_N_list': [7, 3, 3, 7],
        'Ix_core': 0,    'Iy_core': 0,    'core_n': 0,
    },
    {
        'case_id':           'C04',
        'base_layout':       'safety',
        'column_combination':'N7_bal_0 + N7_bal_90  (diag_pair)',
        'core_type':         'none',
        'arrangement':       'diag_pair',
        # C1=C4=N7_bal_0, C2=C3=N7_bal_90
        'cols_Ix':  [21641, 21601, 21601, 21641],
        'cols_Iy':  [21601, 21641, 21641, 21601],
        'col_N_list': [7, 7, 7, 7],
        'Ix_core': 0,    'Iy_core': 0,    'core_n': 0,
    },
    {
        'case_id':           'C05',
        'base_layout':       'overdesign',
        'column_combination':'N7_bal x4 + Strong Core  (uniform_4)',
        'core_type':         'strong',
        'arrangement':       'uniform_4',
        'cols_Ix':  [21641, 21641, 21641, 21641],
        'cols_Iy':  [21601, 21601, 21601, 21601],
        'col_N_list': [7, 7, 7, 7],
        'Ix_core': 40000, 'Iy_core': 40000, 'core_n': 12,
    },
]

# 기둥 위치 (mm)
COL_POS = [(0, 0), (150, 0), (0, 150), (150, 150)]
CORE_POS = (75, 75)
CM = (75, 75)


# ─────────────────────────────────────────────────────────────────
# 비용 계산
# ─────────────────────────────────────────────────────────────────
def cost_floor_sep(col_N: list, core_n: int) -> int:
    """층별 분리: 각 층 독립 절단. 4기둥 + 코어 각각."""
    total_col_N = sum(col_N)
    col_cost = NUM_FLOORS * math.ceil(total_col_N / PIECES_PER_MBR) * UNIT_PRICE
    if core_n == 0:
        return col_cost
    core_cost = NUM_FLOORS * math.ceil(core_n / PIECES_PER_MBR) * UNIT_PRICE
    return col_cost + core_cost


def cost_continuous(col_N: list, core_n: int) -> int:
    """연속 제작: 4층 전체 통합 절단."""
    col_cost  = math.ceil(sum(col_N) * NUM_FLOORS / PIECES_PER_MBR) * UNIT_PRICE
    if core_n == 0:
        return col_cost
    core_cost = math.ceil(core_n * NUM_FLOORS / PIECES_PER_MBR) * UNIT_PRICE
    return col_cost + core_cost


# ─────────────────────────────────────────────────────────────────
# 구조 해석
# ─────────────────────────────────────────────────────────────────
def story_stiffness(cols_Ix, cols_Iy, Ix_core, Iy_core):
    """
    층별 전단 강성 [N/mm] (모든 층 동일)
    k_x = K_FACTOR × (Σ Iy_col + Iy_core)  → x방향 횡력 저항 (Iy 기여)
    k_y = K_FACTOR × (Σ Ix_col + Ix_core)  → y방향 횡력 저항 (Ix 기여)
    """
    k_x = K_FACTOR * (sum(cols_Iy) + Iy_core)
    k_y = K_FACTOR * (sum(cols_Ix) + Ix_core)
    return k_x, k_y


def lateral_response(k_x, k_y):
    """
    삼각형 분포 단위 하중 (V_base=1N) 하에서의 층별 변위 및 지붕 변위
    반환값 단위: 변위 [mm], 층간변위비 [-]
    """
    # 층간 변위 (drift)
    drifts_x = [V / k_x for V in STORY_SHEAR]   # [mm]
    drifts_y = [V / k_y for V in STORY_SHEAR]

    # 누적 변위 (floor displacement from base)
    disp_x = [sum(drifts_x[: i + 1]) for i in range(NUM_FLOORS)]
    disp_y = [sum(drifts_y[: i + 1]) for i in range(NUM_FLOORS)]

    # 층간변위비 (= drift / floor height)
    drift_ratio_x = [d / FLOOR_H for d in drifts_x]
    drift_ratio_y = [d / FLOOR_H for d in drifts_y]

    max_dr_x = max(drift_ratio_x)
    max_dr_y = max(drift_ratio_y)

    # 최대 층간변위비 발생 층 (1-based)
    idx_x = drift_ratio_x.index(max_dr_x) + 1
    idx_y = drift_ratio_y.index(max_dr_y) + 1
    first_dmg = f"Story {min(idx_x, idx_y)}"

    return {
        'k_x': k_x, 'k_y': k_y,
        'drifts_x': drifts_x, 'drifts_y': drifts_y,
        'disp_x': disp_x, 'disp_y': disp_y,
        'drift_ratio_x': drift_ratio_x, 'drift_ratio_y': drift_ratio_y,
        'roof_disp_X': disp_x[-1], 'roof_disp_Y': disp_y[-1],
        'max_story_drift_X': max_dr_x, 'max_story_drift_Y': max_dr_y,
        'first_damage_location': first_dmg,
    }


def torsion_metrics(cols_Ix, cols_Iy, Ix_core, Iy_core):
    """
    강성 편심 및 비틀림 지수 계산
    norm_ecc    = max(e_x, e_y) / L_SPAN         [0이면 완전 대칭]
    torsion_idx = max(e_x, e_y) / r_k  (편심비)
    r_k = sqrt(J_k / Σk)  비틀림 반경
    """
    k_x_cols = [K_FACTOR * Iy for Iy in cols_Iy]
    k_y_cols = [K_FACTOR * Ix for Ix in cols_Ix]
    k_x_core = K_FACTOR * Iy_core
    k_y_core = K_FACTOR * Ix_core

    sum_kx = sum(k_x_cols) + k_x_core
    sum_ky = sum(k_y_cols) + k_y_core

    num_CRx = sum(k_x_cols[i] * COL_POS[i][0] for i in range(4)) + k_x_core * CORE_POS[0]
    num_CRy = sum(k_y_cols[i] * COL_POS[i][1] for i in range(4)) + k_y_core * CORE_POS[1]

    CR_x = num_CRx / sum_kx if sum_kx > 0 else CM[0]
    CR_y = num_CRy / sum_ky if sum_ky > 0 else CM[1]
    e_x  = abs(CR_x - CM[0])
    e_y  = abs(CR_y - CM[1])
    e_max = max(e_x, e_y)
    norm_ecc = e_max / L_SPAN

    # 비틀림 강성 J_k (CR 기준)
    J_k = (sum(k_y_cols[i] * (COL_POS[i][0] - CR_x) ** 2 for i in range(4))
         + sum(k_x_cols[i] * (COL_POS[i][1] - CR_y) ** 2 for i in range(4))
         + k_y_core * (CORE_POS[0] - CR_x) ** 2
         + k_x_core * (CORE_POS[1] - CR_y) ** 2)

    sum_k = sum_kx + sum_ky
    r_k = math.sqrt(J_k / sum_k) if (sum_k > 0 and J_k > 0) else 0.0
    torsion_idx = e_max / r_k if r_k > 0 else 0.0

    return round(norm_ecc, 6), round(torsion_idx, 6), round(CR_x, 3), round(CR_y, 3)


def compute_score(min_I, total_cost, roof_disp_avg, torsion_idx):
    """
    복합 구조 성능 점수 (높을수록 우수)
      score = (min_I / cost) / (roof_disp_avg × scale)
            × torsion_penalty
    - min_I / cost     : 강성 효율 (원당 단면 성능)
    - roof_disp_avg    : 평균 지붕 변위 역수 → 강성 반영
    - torsion_penalty  : 1/(1 + 10×torsion_idx) → 비틀림 페널티
    단위: [mm⁴ / (원 × mm)] = [mm³/원]
    """
    if total_cost <= 0 or roof_disp_avg <= 0:
        return 0.0
    eff      = min_I / total_cost
    t_factor = 1.0 / (1 + 10 * torsion_idx)
    score    = eff * t_factor / roof_disp_avg
    return round(score, 4)


# ─────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────
def main():
    os.makedirs(SYSTEM_DIR, exist_ok=True)

    records = []

    for case in CASES:
        rec = {}

        # ── 기본 정보 ──────────────────────────────────────────────
        rec['case_id']           = case['case_id']
        rec['base_layout']       = case['base_layout']
        rec['column_combination']= case['column_combination']
        rec['core_type']         = case['core_type']
        rec['arrangement']       = case['arrangement']
        # 층별 기둥 조합 (현 모델: 전 층 동일)
        rec['floors_col_layout'] = f"F1~F4: {case['column_combination']}"

        # ── 댐퍼/퓨즈 (미래 확장용 placeholder) ───────────────────
        rec['damper_type']       = None
        rec['damper_floor']      = None
        rec['damper_direction']  = None
        rec['fuse_type']         = None
        rec['fuse_location']     = None
        rec['fuse_strength']     = None
        rec['rubber_band_count'] = None

        # ── 비용 ───────────────────────────────────────────────────
        c_fbf  = cost_floor_sep (case['col_N_list'], case['core_n'])
        c_cont = cost_continuous(case['col_N_list'], case['core_n'])
        rec['total_cost_floor_sep']  = c_fbf
        rec['total_cost_continuous'] = c_cont
        rec['total_cost'] = c_fbf if COST_MODE == 'floor_by_floor' else c_cont

        # ── 단면 성능 ──────────────────────────────────────────────
        sum_Ix = sum(case['cols_Ix']) + case['Ix_core']
        sum_Iy = sum(case['cols_Iy']) + case['Iy_core']
        rec['sum_Ix']       = sum_Ix
        rec['sum_Iy']       = sum_Iy
        rec['min_system_I'] = min(sum_Ix, sum_Iy)
        rec['Ix_Iy_ratio']  = round(sum_Ix / sum_Iy, 6) if sum_Iy > 0 else 0.0

        # ── 층별 stiffness (모든 층 동일) ──────────────────────────
        k_x, k_y = story_stiffness(
            case['cols_Ix'], case['cols_Iy'], case['Ix_core'], case['Iy_core'])
        for fl in range(1, NUM_FLOORS + 1):
            rec[f'k_story{fl}_X'] = round(k_x, 6)
            rec[f'k_story{fl}_Y'] = round(k_y, 6)

        # ── 횡변위 응답 ────────────────────────────────────────────
        resp = lateral_response(k_x, k_y)
        rec['roof_disp_X']       = round(resp['roof_disp_X'], 8)
        rec['roof_disp_Y']       = round(resp['roof_disp_Y'], 8)
        rec['max_story_drift_X'] = round(resp['max_story_drift_X'], 8)
        rec['max_story_drift_Y'] = round(resp['max_story_drift_Y'], 8)

        # 층별 층간 변위 (mm)
        for fl in range(1, NUM_FLOORS + 1):
            rec[f'drift{fl}_X'] = round(resp['drifts_x'][fl - 1], 8)
            rec[f'drift{fl}_Y'] = round(resp['drifts_y'][fl - 1], 8)
        # 층별 누적 변위 (mm)
        for fl in range(1, NUM_FLOORS + 1):
            rec[f'disp{fl}_X'] = round(resp['disp_x'][fl - 1], 8)
            rec[f'disp{fl}_Y'] = round(resp['disp_y'][fl - 1], 8)

        # ── 비틀림 ────────────────────────────────────────────────
        norm_ecc, t_idx, CR_x, CR_y = torsion_metrics(
            case['cols_Ix'], case['cols_Iy'], case['Ix_core'], case['Iy_core'])
        rec['norm_ecc']      = norm_ecc
        rec['torsion_index'] = t_idx
        rec['CR_x']          = CR_x
        rec['CR_y']          = CR_y

        # ── 파괴 정보 ──────────────────────────────────────────────
        rec['first_damage_location'] = resp['first_damage_location']
        rec['failure_mode']          = 'column_flexure'

        # ── 점수 ───────────────────────────────────────────────────
        roof_avg = (resp['roof_disp_X'] + resp['roof_disp_Y']) / 2
        rec['score'] = compute_score(rec['min_system_I'], c_fbf, roof_avg, t_idx)

        records.append(rec)

    df = pd.DataFrame(records)

    # ── 컬럼 순서 (요구사항 + 확장) ─────────────────────────────────
    col_order = [
        # 식별
        'case_id', 'base_layout', 'column_combination', 'floors_col_layout',
        'core_type', 'arrangement',
        # 댐퍼/퓨즈 (placeholder)
        'damper_type', 'damper_floor', 'damper_direction',
        'fuse_type', 'fuse_location', 'fuse_strength', 'rubber_band_count',
        # 비용
        'total_cost_floor_sep', 'total_cost_continuous', 'total_cost',
        # 단면 성능
        'min_system_I', 'sum_Ix', 'sum_Iy', 'Ix_Iy_ratio',
        # 층별 stiffness
        'k_story1_X', 'k_story1_Y', 'k_story2_X', 'k_story2_Y',
        'k_story3_X', 'k_story3_Y', 'k_story4_X', 'k_story4_Y',
        # 비틀림
        'norm_ecc', 'torsion_index', 'CR_x', 'CR_y',
        # 변위 응답
        'roof_disp_X', 'roof_disp_Y',
        'max_story_drift_X', 'max_story_drift_Y',
        # 층별 변위 (mm)
        'drift1_X', 'drift1_Y', 'drift2_X', 'drift2_Y',
        'drift3_X', 'drift3_Y', 'drift4_X', 'drift4_Y',
        'disp1_X', 'disp1_Y', 'disp2_X', 'disp2_Y',
        'disp3_X', 'disp3_Y', 'disp4_X', 'disp4_Y',
        # 파괴 / 점수
        'first_damage_location', 'failure_mode', 'score',
    ]
    available = [c for c in col_order if c in df.columns]
    df_out = df[available]

    # ── 저장 ───────────────────────────────────────────────────────
    out_xlsx = os.path.join(SYSTEM_DIR, 'performance_dataset.xlsx')
    out_csv  = os.path.join(SYSTEM_DIR, 'performance_dataset.csv')
    df_out.to_excel(out_xlsx, index=False)
    df_out.to_csv(out_csv,   index=False, encoding='utf-8-sig')

    # ── 콘솔 출력 ──────────────────────────────────────────────────
    sep = '=' * 74
    print(sep)
    print('  4층 전단빌딩 구조 성능 데이터셋')
    print(sep)
    print(f'  E_MDF      = {E_MDF} N/mm2')
    print(f'  floor_h    = {FLOOR_H} mm   K_factor = {K_FACTOR:.6f} N/(mm * mm4)')
    print(f'  V_base     = 1 N (triangular: {F_FLOOR})')
    print(f'  COST_MODE  = {COST_MODE}')
    print()

    # 비용 비교표
    print(f'  {"case":^6}  {"layout":^12}  {"core":^8}  '
          f'{"fbf_cost":>9}  {"cont_cost":>10}  {"diff":>6}')
    print(f'  {"-"*62}')
    for rec in records:
        diff = rec['total_cost_floor_sep'] - rec['total_cost_continuous']
        print(f'  {rec["case_id"]:^6}  {rec["base_layout"]:^12}  '
              f'{rec["core_type"]:^8}  '
              f'{rec["total_cost_floor_sep"]:>7}won  '
              f'{rec["total_cost_continuous"]:>8}won  '
              f'{diff:>+5}won')
    print()

    # 성능 비교표
    print(f'  {"case":^6}  {"min_I":>8}  {"k_X":>10}  '
          f'{"roof_X mm":>10}  {"max_dr_X":>10}  {"score":>8}')
    print(f'  {"-"*62}')
    for rec in records:
        print(f'  {rec["case_id"]:^6}  {rec["min_system_I"]:>8,}  '
              f'{rec["k_story1_X"]:>10.3f}  '
              f'{rec["roof_disp_X"]:>10.6f}  '
              f'{rec["max_story_drift_X"]:>10.2e}  '
              f'{rec["score"]:>8.2f}')
    print()

    print(f'  저장: {out_xlsx}')
    print(f'  저장: {out_csv}')
    print()
    print('  [모델 전제]')
    print(f'  - 전단빌딩: fixed-fixed, k = 12EI/h3')
    print(f'  - E = {E_MDF} N/mm2 (MDF 대표값, 조정 가능)')
    print(f'  - V_base = 1N 단위 하중 (실제 지진 크기 미반영)')
    print(f'  - 층간변위비 max_story_drift = drift / floor_h')
    print(f'  - score = (min_I/cost) / roof_disp_avg x torsion_penalty')
    print()


if __name__ == '__main__':
    main()
