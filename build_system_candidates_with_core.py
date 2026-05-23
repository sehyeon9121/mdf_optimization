"""
build_system_candidates_with_core.py
파라메트릭 코어 라이브러리 + 기둥 배치 후보 조합 생성

입력:
  outputs/system/system_candidates.xlsx  (build_system_candidates.py 출력)
  없으면 outputs/performance_dataset.xlsx 을 fallback 으로 사용
  core_scenario == 'none' 행만 사용 (기둥-only 기준 시스템)

코어 타입:
  none     : 코어 없음
  box      : 정사각 중공 박스 (outer_b == outer_d)
  rect_box : 직사각 중공 박스 (0.5 <= aspect_ratio <= 2.0)
  C_shape  : 한쪽이 열린 C형 단면 (3면 벽체)
  cross    : 제외 (INCLUDE_CROSS = False)

출력:
  outputs/system_candidates_with_core.csv   (항상 저장)
  outputs/system_candidates_with_core.xlsx  (행 수 <= 1,000,000 일 때만)
  outputs/core_library_expanded.xlsx / .csv

평면 정보 (확정):
  기둥: C1=(0,0), C2=(150,0), C3=(0,150), C4=(150,150) mm
  코어 중심: (75, 75) mm,  CM = (75, 75) mm
  층고 h=200 mm,  스팬 L=150 mm
"""

import os
import math
import warnings
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).parent
SYS_DIR  = BASE_DIR / 'outputs' / 'system'
OUT_DIR  = BASE_DIR / 'outputs'

# ─── 평면 상수 ────────────────────────────────────────────────────
L           = 150.0
CM_X, CM_Y  = 75.0, 75.0
CORE_X, CORE_Y = 75.0, 75.0
COL_POS = {
    'C1': (0.0,   0.0  ),
    'C2': (150.0, 0.0  ),
    'C3': (0.0,   150.0),
    'C4': (150.0, 150.0),
}

# ─── 비용 상수 ────────────────────────────────────────────────────
UNIT_PRICE    = 10
REFERENCE_DIM = 30.0    # length_factor 기준 치수 (mm)

# ─── 건축성 기준 ──────────────────────────────────────────────────
MAX_BBOX_B       = 60.0   # mm
MAX_BBOX_D       = 60.0   # mm
MIN_CLEAR_COL    = 20.0   # mm
MIN_CLEAR_WEIGHT = 5.0    # mm
WEIGHT_DIM       = 26.0   # mm  하중추 최소 치수 (26x50x50mm)
MAX_STRIP_COUNT  = 12

# ─── 실행 옵션 ────────────────────────────────────────────────────
INCLUDE_CROSS             = False   # cross 형상 제외
INCLUDE_UNBUILDABLE_CORES = True    # False 이면 buildable 코어만 조합
COST_MODE_CORE            = 'length_based'  # 'simple' | 'length_based'
MAX_ROWS_XLSX             = 1_000_000

# ─── 비틀림 위험 기준 ──────────────────────────────────────────────
TORSION_LOW  = 0.05
TORSION_HIGH = 0.15


# ═════════════════════════════════════════════════════════════════
# 단면 2차 모멘트 계산
# ═════════════════════════════════════════════════════════════════

def hollow_I(ob, od, ib, id_):
    """중공 직사각형 단면 → (Ix, Iy)"""
    Ix = (ob * od**3 - ib * id_**3) / 12.0
    Iy = (od * ob**3 - id_ * ib**3) / 12.0
    return max(Ix, 0.0), max(Iy, 0.0)


def c_shape_canonical(ob, od, wt):
    """
    C형 단면 (open to +X, 원점 중심) 성능 계산 — 평행축정리(B안)
    3개 벽체: 하부 플랜지, 상부 플랜지, 좌측 웹
    반환: (Ix, Iy, x_c)
      Ix  : x축(수평) 기준 단면2차모멘트
      Iy  : 도심 y축(수직) 기준 단면2차모멘트
      x_c : 도심 x좌표 (음수 = 좌측 편심)
    주의: open_direction(+Y/-Y)에 따라 Ix/Iy 역할 교환 (호출자 처리)
    TODO: 실제 CR 계산 시 x_c 편심을 코어 위치에 반영하면 정확도 향상 가능
    """
    h_web = od - 2.0 * wt
    if h_web <= 0:
        return 0.0, 0.0, 0.0

    # 부재 면적
    A_fl = ob * wt        # 상/하 플랜지 각 1개
    A_wb = wt * h_web     # 웹

    A_tot = 2.0 * A_fl + A_wb
    if A_tot <= 0:
        return 0.0, 0.0, 0.0

    # 도심 x좌표 (플랜지 중심 x=0, 웹 중심 x = -ob/2 + wt/2)
    x_wb = -ob / 2.0 + wt / 2.0
    x_c  = A_wb * x_wb / A_tot   # 도심 (y_c = 0 by symmetry)

    # Ix (x축 = y=0 통과, 대칭이므로 직접 합산)
    d_fl = od / 2.0 - wt / 2.0
    Ix_fl = ob * wt**3 / 12.0 + A_fl * d_fl**2
    Ix_wb = wt * h_web**3 / 12.0
    Ix = 2.0 * Ix_fl + Ix_wb

    # Iy (x_c 기준)
    # 플랜지: own Iy_own = wt * ob^3/12, centroid at x=0 → dist |0 - x_c|
    # 웹:     own Iy_own = h_web * wt^3/12, centroid at x_wb → dist |x_wb - x_c|
    Iy_fl = wt * ob**3 / 12.0 + A_fl * x_c**2
    Iy_wb = h_web * wt**3 / 12.0 + A_wb * (x_wb - x_c)**2
    Iy = 2.0 * Iy_fl + Iy_wb

    return max(Ix, 0.0), max(Iy, 0.0), x_c


def rotate_I(Ix0, Iy0, theta_deg):
    """단면2차모멘트 회전 변환 (Ixy=0 가정) → (Ix_rot, Iy_rot)"""
    theta = math.radians(theta_deg)
    c2 = math.cos(2.0 * theta)
    avg = (Ix0 + Iy0) / 2.0
    hdf = (Ix0 - Iy0) / 2.0
    return avg + hdf * c2, avg - hdf * c2


def bbox_after_rotation(ob, od, theta_deg):
    """직사각형 회전 후 bounding box → (bbox_b, bbox_d)"""
    t = math.radians(theta_deg)
    ct, st = abs(math.cos(t)), abs(math.sin(t))
    return ob * ct + od * st, ob * st + od * ct


# ═════════════════════════════════════════════════════════════════
# 비용 계산
# ═════════════════════════════════════════════════════════════════

def calc_core_cost(n_pieces, ob, od, core_type):
    """반환: (cost_simple, cost_length_based, length_factor)"""
    cost_simple = n_pieces * UNIT_PRICE
    if core_type == 'C_shape':
        perim = 2.0 * od + ob           # 3면 둘레 근사
        ref   = 3.0 * REFERENCE_DIM
    else:
        perim = 2.0 * (ob + od)
        ref   = 4.0 * REFERENCE_DIM
    lf = perim / ref
    cost_len = n_pieces * UNIT_PRICE * lf
    return cost_simple, cost_len, round(lf, 4)


# ═════════════════════════════════════════════════════════════════
# 건축성 평가
# ═════════════════════════════════════════════════════════════════

def calc_clearances(bbox_b, bbox_d):
    """
    bounding box 기준 클리어런스 계산 (보수적 추정)
    TODO: 실제 하중추 배치 좌표(층별 grid) 기반 정밀 검토 필요 (현재 placeholder)
    """
    # 기둥까지: bounding box 모서리 → 기둥 중심 유클리드 거리
    cl_col = math.sqrt((75.0 - bbox_b / 2.0)**2 + (75.0 - bbox_d / 2.0)**2)
    # 하중추까지: 짧은 방향 기준
    cl_wt  = min((L - bbox_b) / 2.0, (L - bbox_d) / 2.0) - WEIGHT_DIM
    return round(cl_col, 3), round(cl_wt, 3)


def check_buildable(inner_b, inner_d, bbox_b, bbox_d,
                    cl_col, cl_wt, strip_count, hollow_ratio):
    """반환: (is_buildable: bool, fail_reason: str)"""
    reasons = []
    if inner_b <= 0:          reasons.append(f'inner_b={inner_b:.2f}<=0')
    if inner_d <= 0:          reasons.append(f'inner_d={inner_d:.2f}<=0')
    if bbox_b > MAX_BBOX_B:   reasons.append(f'bbox_b={bbox_b:.2f}>{MAX_BBOX_B}')
    if bbox_d > MAX_BBOX_D:   reasons.append(f'bbox_d={bbox_d:.2f}>{MAX_BBOX_D}')
    if cl_col < MIN_CLEAR_COL:     reasons.append(f'cl_col={cl_col:.2f}<{MIN_CLEAR_COL}')
    if cl_wt  < MIN_CLEAR_WEIGHT:  reasons.append(f'cl_wt={cl_wt:.2f}<{MIN_CLEAR_WEIGHT}')
    if strip_count > MAX_STRIP_COUNT: reasons.append(f'strips={strip_count}>{MAX_STRIP_COUNT}')
    if hollow_ratio <= 0:          reasons.append('hollow_ratio<=0')
    buildable   = len(reasons) == 0
    fail_reason = '; '.join(reasons)
    return buildable, fail_reason


def make_core_entry(core_type, core_id, ob, od, wt, ib, id_,
                    rotation_deg, open_direction,
                    Ix, Iy, n_pieces, bbox_b, bbox_d,
                    cl_col, cl_wt, hollow_ratio, x_c_offset):
    cs, cl, lf = calc_core_cost(n_pieces, ob, od, core_type)
    core_cost   = cl if COST_MODE_CORE == 'length_based' else cs
    buildable, fail = check_buildable(ib, id_, bbox_b, bbox_d,
                                      cl_col, cl_wt, n_pieces, hollow_ratio)
    analysis = (buildable
                and cl_wt  >= MIN_CLEAR_WEIGHT
                and bbox_b <= MAX_BBOX_B
                and bbox_d <= MAX_BBOX_D)
    return dict(
        core_type=core_type, core_id=core_id,
        outer_b=ob, outer_d=od, wall_t=wt,
        inner_b=round(ib, 4), inner_d=round(id_, 4),
        rotation_deg=rotation_deg, open_direction=open_direction,
        core_Ix=round(Ix, 2), core_Iy=round(Iy, 2),
        core_strip_count=n_pieces,
        core_cost_simple=cs,
        core_cost_length=round(cl, 2),
        core_cost=round(core_cost, 2),
        core_length_factor=lf,
        bbox_b=round(bbox_b, 4), bbox_d=round(bbox_d, 4),
        clearance_to_column=cl_col,
        clearance_to_weight=cl_wt,
        hollow_ratio=round(hollow_ratio, 4),
        x_centroid_offset=round(x_c_offset, 4),
        core_generated=True,
        core_buildable=buildable,
        fail_reason=fail,
        analysis_candidate=analysis,
    )


# ═════════════════════════════════════════════════════════════════
# 코어 라이브러리 생성
# ═════════════════════════════════════════════════════════════════

def gen_none():
    return [dict(
        core_type='none', core_id='core_none',
        outer_b=0.0, outer_d=0.0, wall_t=0.0,
        inner_b=0.0, inner_d=0.0,
        rotation_deg=0, open_direction='',
        core_Ix=0.0, core_Iy=0.0,
        core_strip_count=0,
        core_cost_simple=0.0, core_cost_length=0.0, core_cost=0.0,
        core_length_factor=1.0,
        bbox_b=0.0, bbox_d=0.0,
        clearance_to_column=9999.0, clearance_to_weight=9999.0,
        hollow_ratio=0.0, x_centroid_offset=0.0,
        core_generated=True, core_buildable=True,
        fail_reason='', analysis_candidate=True,
    )]


def gen_box():
    """정사각 중공 박스: outer_b == outer_d"""
    SIZES = [20, 25, 30, 35, 40, 45, 50, 55, 60]
    WALLS = [2, 3, 4, 5]
    ROTS  = [0, 15, 30, 45]
    cores = []
    for ob, wt, rot in product(SIZES, WALLS, ROTS):
        ob = float(ob); wt = float(wt)
        ib = ob - 2.0 * wt
        if ib <= 0:
            continue
        Ix0, Iy0 = hollow_I(ob, ob, ib, ib)
        Ix, Iy   = rotate_I(Ix0, Iy0, rot)
        bb, bd   = bbox_after_rotation(ob, ob, rot)
        cl_col, cl_wt = calc_clearances(bb, bd)
        h_ratio = (ib * ib) / (ob * ob) if ob > 0 else 0.0
        cid = f'box_{int(ob)}x{int(ob)}_t{int(wt)}_r{rot}'
        cores.append(make_core_entry(
            'box', cid, ob, ob, wt, ib, ib,
            rot, '', Ix, Iy, 4, bb, bd, cl_col, cl_wt, h_ratio, 0.0))
    return cores


def gen_rect_box():
    """직사각 중공 박스: 0.5 <= aspect_ratio <= 2.0"""
    SIZES = [20, 25, 30, 35, 40, 45, 50, 55, 60]
    WALLS = [2, 3, 4, 5]
    ROTS  = [0, 15, 30, 45, 90]
    cores = []
    for ob, od, wt, rot in product(SIZES, SIZES, WALLS, ROTS):
        ob = float(ob); od = float(od); wt = float(wt)
        ar = ob / od
        if not (0.5 <= ar <= 2.0):
            continue
        ib  = ob - 2.0 * wt
        id_ = od - 2.0 * wt
        if ib <= 0 or id_ <= 0:
            continue
        Ix0, Iy0 = hollow_I(ob, od, ib, id_)
        Ix, Iy   = rotate_I(Ix0, Iy0, rot)
        bb, bd   = bbox_after_rotation(ob, od, rot)
        cl_col, cl_wt = calc_clearances(bb, bd)
        h_ratio = (ib * id_) / (ob * od) if (ob * od) > 0 else 0.0
        cid = f'rect_{int(ob)}x{int(od)}_t{int(wt)}_r{rot}'
        cores.append(make_core_entry(
            'rect_box', cid, ob, od, wt, ib, id_,
            rot, '', Ix, Iy, 4, bb, bd, cl_col, cl_wt, h_ratio, 0.0))
    return cores


def gen_c_shape():
    """C형 단면 (3면 벽체)"""
    SIZES    = [30, 35, 40, 45, 50, 55, 60]
    WALLS    = [2, 3, 4, 5]
    OPEN_DIR = ['+X', '-X', '+Y', '-Y']
    ROTS     = [0, 90]
    cores    = []
    for ob, od, wt, odir, rot in product(SIZES, SIZES, WALLS, OPEN_DIR, ROTS):
        ob = float(ob); od = float(od); wt = float(wt)
        ib  = ob - 2.0 * wt   # 참조용 내부 치수
        id_ = od - 2.0 * wt
        if ib <= 0 or id_ <= 0:
            continue

        # canonical C (open +X): Ix, Iy, x_c
        Ix_c, Iy_c, x_off = c_shape_canonical(ob, od, wt)

        # open_direction 기본 방향 처리:
        # +X/-X → canonical 그대로, +Y/-Y → Ix/Iy 교환 (90도 회전 효과)
        if odir in ('+Y', '-Y'):
            Ix_base, Iy_base = Iy_c, Ix_c
            eff_b, eff_d     = od, ob      # bounding box 기준 effective dims
        else:
            Ix_base, Iy_base = Ix_c, Iy_c
            eff_b, eff_d     = ob, od

        # additional rotation_deg
        Ix, Iy = rotate_I(Ix_base, Iy_base, rot)
        bb, bd = bbox_after_rotation(eff_b, eff_d, rot)
        cl_col, cl_wt = calc_clearances(bb, bd)

        # C형 hollow_ratio: (총 면적 - 재료 면적) / 총 면적
        A_mat   = 2.0 * ob * wt + wt * (od - 2.0 * wt)
        h_ratio = 1.0 - A_mat / (ob * od) if (ob * od) > 0 else 0.0

        cid = f'C_{int(ob)}x{int(od)}_t{int(wt)}_{odir}_r{rot}'
        cores.append(make_core_entry(
            'C_shape', cid, ob, od, wt, ib, id_,
            rot, odir, Ix, Iy, 3, bb, bd, cl_col, cl_wt, h_ratio, x_off))
    return cores


def make_core_library():
    rows = gen_none() + gen_box() + gen_rect_box() + gen_c_shape()
    return pd.DataFrame(rows)


# ═════════════════════════════════════════════════════════════════
# 기둥 후보별 시스템 지표 (벡터화 계산)
# ═════════════════════════════════════════════════════════════════

def compute_batch(col_row, cores_np, cores_df):
    """
    단일 기둥 후보 + 전체 코어 배열 → 시스템 지표 (numpy 벡터화)
    cores_np: dict of numpy arrays (pre-extracted from cores_df)
    반환: dict of 1-D numpy arrays (길이 = 코어 수)
    """
    C_Ix = np.array([col_row[f'{c}_Ix'] for c in ['C1','C2','C3','C4']], dtype=float)
    C_Iy = np.array([col_row[f'{c}_Iy'] for c in ['C1','C2','C3','C4']], dtype=float)
    xs   = np.array([COL_POS[c][0] for c in ['C1','C2','C3','C4']], dtype=float)
    ys   = np.array([COL_POS[c][1] for c in ['C1','C2','C3','C4']], dtype=float)

    sum_Ix_col  = C_Ix.sum()
    sum_Iy_col  = C_Iy.sum()
    CRx_num_col = (C_Iy * xs).sum()
    CRy_num_col = (C_Ix * ys).sum()
    col_cost    = float(col_row.get('col_cost_floor_sep', 0))

    core_Ix   = cores_np['core_Ix']
    core_Iy   = cores_np['core_Iy']
    core_cost = cores_np['core_cost']

    sys_Ix = sum_Ix_col + core_Ix
    sys_Iy = sum_Iy_col + core_Iy

    CRx_num = CRx_num_col + core_Iy * CORE_X
    CRy_num = CRy_num_col + core_Ix * CORE_Y

    CR_x = np.where(sys_Iy > 0, CRx_num / sys_Iy, CM_X)
    CR_y = np.where(sys_Ix > 0, CRy_num / sys_Ix, CM_Y)

    e_x = np.abs(CR_x - CM_X)
    e_y = np.abs(CR_y - CM_Y)
    norm_ecc = np.maximum(e_x, e_y) / L

    min_I      = np.minimum(sys_Ix, sys_Iy)
    total_cost = col_cost + core_cost
    sys_eff    = np.where(total_cost > 0, min_I / total_cost, 0.0)

    contrib_x  = np.where(sys_Ix > 0, core_Ix / sys_Ix, 0.0)
    contrib_y  = np.where(sys_Iy > 0, core_Iy / sys_Iy, 0.0)

    torsion = np.where(norm_ecc < TORSION_LOW, 'low',
              np.where(norm_ecc < TORSION_HIGH, 'medium', 'high'))

    return dict(
        system_Ix_with_core   = np.round(sys_Ix, 2),
        system_Iy_with_core   = np.round(sys_Iy, 2),
        system_min_I_with_core= np.round(min_I, 2),
        total_cost_with_core  = np.round(total_cost, 2),
        sys_eff_with_core     = np.round(sys_eff, 4),
        CR_x_with_core        = np.round(CR_x, 3),
        CR_y_with_core        = np.round(CR_y, 3),
        e_x_with_core         = np.round(e_x, 3),
        e_y_with_core         = np.round(e_y, 3),
        norm_ecc_with_core    = np.round(norm_ecc, 6),
        torsion_risk_with_core= torsion,
        core_contribution_ratio_x = np.round(contrib_x, 4),
        core_contribution_ratio_y = np.round(contrib_y, 4),
    )


# ═════════════════════════════════════════════════════════════════
# 유틸
# ═════════════════════════════════════════════════════════════════

def sep(title=''):
    print('=' * 72)
    if title:
        print(f'  {title}')
        print('=' * 72)


# ═════════════════════════════════════════════════════════════════
# 메인
# ═════════════════════════════════════════════════════════════════

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. 기둥 후보 로드 ─────────────────────────────────────────
    sep('Step 1  기둥 후보 로드')
    src = SYS_DIR / 'system_candidates.xlsx'
    if not src.exists():
        src = OUT_DIR / 'performance_dataset.xlsx'
        if not src.exists():
            raise FileNotFoundError(
                'system_candidates.xlsx / performance_dataset.xlsx 를 찾을 수 없습니다.')

    df_all  = pd.read_excel(src)
    df_cols = (df_all[df_all['core_scenario'] == 'none']
               .copy()
               .reset_index(drop=True))
    print(f'  원본 파일  : {src.name}  ({len(df_all):,}행, {len(df_all.columns)}열)')
    print(f'  기둥-only  : {len(df_cols):,}개  (core_scenario=none)')
    print()

    # ── 2. 코어 라이브러리 생성 ───────────────────────────────────
    sep('Step 2  파라메트릭 코어 라이브러리 생성')
    core_lib = make_core_library()

    n_total = len(core_lib)
    n_build = int(core_lib['core_buildable'].sum())
    n_cand  = int(core_lib['analysis_candidate'].sum())

    print(f'  전체 코어 후보:          {n_total:>8,}개')
    print(f'  buildable:               {n_build:>8,}개')
    print(f'  analysis_candidate:      {n_cand:>8,}개')
    print()
    print(f'  {"core_type":^12}  {"total":>6}  {"build":>6}  {"cand":>6}')
    print(f'  {"-"*36}')
    for ct in ['none', 'box', 'rect_box', 'C_shape']:
        sub = core_lib[core_lib['core_type'] == ct]
        if sub.empty:
            continue
        sb = int(sub['core_buildable'].sum())
        sc = int(sub['analysis_candidate'].sum())
        print(f'  {ct:^12}  {len(sub):>6,}  {sb:>6,}  {sc:>6,}')
    print()

    # ── 3. 코어 라이브러리 저장 ───────────────────────────────────
    sep('Step 3  코어 라이브러리 저장')
    clb_xlsx = OUT_DIR / 'core_library_expanded.xlsx'
    clb_csv  = OUT_DIR / 'core_library_expanded.csv'
    core_lib.to_excel(clb_xlsx, index=False)
    core_lib.to_csv(clb_csv, index=False, encoding='utf-8-sig')
    print(f'  저장: {clb_xlsx}  ({len(core_lib):,}행 x {len(core_lib.columns)}열)')
    print(f'  저장: {clb_csv}')
    print()

    # ── 4. 조합 생성 (청크 CSV 쓰기) ─────────────────────────────
    sep('Step 4  기둥 x 코어 조합 생성')

    if INCLUDE_UNBUILDABLE_CORES:
        cores_use = core_lib.reset_index(drop=True)
    else:
        cores_use = core_lib[core_lib['core_buildable']].reset_index(drop=True)

    n_col  = len(df_cols)
    n_core = len(cores_use)
    n_comb = n_col * n_core
    print(f'  기둥 {n_col:,}  x  코어 {n_core:,}  =  {n_comb:,}개')

    out_csv  = OUT_DIR / 'system_candidates_with_core.csv'
    out_xlsx = OUT_DIR / 'system_candidates_with_core.xlsx'

    # 코어 numpy 배열 (벡터화용)
    cores_np = {
        'core_Ix'  : cores_use['core_Ix'].to_numpy(float),
        'core_Iy'  : cores_use['core_Iy'].to_numpy(float),
        'core_cost': cores_use['core_cost'].to_numpy(float),
    }

    # 출력할 코어 컬럼 목록 (system_candidates에 없는 새 컬럼)
    CORE_COLS = [
        'core_type', 'core_id', 'outer_b', 'outer_d', 'wall_t',
        'inner_b', 'inner_d', 'rotation_deg', 'open_direction',
        'core_Ix', 'core_Iy', 'core_strip_count',
        'core_cost_simple', 'core_cost_length', 'core_cost',
        'core_length_factor', 'bbox_b', 'bbox_d',
        'clearance_to_column', 'clearance_to_weight',
        'hollow_ratio', 'x_centroid_offset',
        'core_buildable', 'fail_reason', 'analysis_candidate',
    ]

    # 기존 컬럼 중 유지할 목록
    KEEP_COLS = [c for c in [
        'arrangement', 'C1_tag', 'C2_tag', 'C3_tag', 'C4_tag', 'core_scenario',
        'sum_Ix', 'sum_Iy', 'system_Ix_Iy', 'min_system_I',
        'col_cost_floor_sep', 'col_cost_continuous',
        'CR_x', 'CR_y', 'e_x', 'e_y', 'norm_ecc', 'torsion_risk',
        'C1_N', 'C2_N', 'C3_N', 'C4_N',
        'C1_Ix', 'C1_Iy', 'C2_Ix', 'C2_Iy',
        'C3_Ix', 'C3_Iy', 'C4_Ix', 'C4_Iy',
    ] if c in df_cols.columns]

    # core 데이터를 numpy 행렬로 준비 (반복 접근 최적화)
    cores_rec = cores_use[CORE_COLS].to_dict(orient='records')

    # CSV 헤더 결정 (첫 시험행으로 확인)
    first_col_row = df_cols.iloc[0]
    batch_metrics = compute_batch(first_col_row, cores_np, cores_use)
    metric_cols   = list(batch_metrics.keys())

    header_order = ['system_id'] + CORE_COLS + metric_cols + KEEP_COLS

    first_write = True
    n_written   = 0
    n_analysis  = 0

    for col_idx, (_, col_row) in enumerate(df_cols.iterrows()):
        # 벡터화 계산
        metrics = compute_batch(col_row, cores_np, cores_use)

        # 기존 컬럼 값 (공통)
        col_vals = {c: col_row[c] for c in KEEP_COLS}

        # 출력 DataFrame 구성
        n = n_core
        out = {}
        # system_id
        base_id = col_idx * n_core
        out['system_id'] = [f"S{base_id + k + 1:09d}" for k in range(n)]

        # 코어 컬럼
        for cc in CORE_COLS:
            out[cc] = cores_use[cc].tolist()

        # 시스템 지표 (numpy)
        for mk, mv in metrics.items():
            out[mk] = mv

        # 기존 컬럼 (스칼라 → broadcast)
        for cv, vv in col_vals.items():
            out[cv] = [vv] * n

        chunk_df = pd.DataFrame(out)[header_order]

        n_analysis += int(chunk_df['analysis_candidate'].sum())

        mode   = 'w' if first_write else 'a'
        header = first_write
        chunk_df.to_csv(out_csv, mode=mode, header=header,
                        index=False, encoding='utf-8-sig')
        first_write = False
        n_written  += n

        if (col_idx + 1) % 200 == 0 or (col_idx + 1) == n_col:
            pct = (col_idx + 1) / n_col * 100
            print(f'    [{col_idx+1:>5}/{n_col}] {n_written:>10,}행  ({pct:.1f}%)')

    print()

    # ── 5. xlsx 저장 여부 ──────────────────────────────────────────
    sep('Step 5  xlsx 저장 여부 확인')
    saved_xlsx = False
    if n_written <= MAX_ROWS_XLSX:
        print(f'  행 수 {n_written:,} <= {MAX_ROWS_XLSX:,} → xlsx 저장 중...')
        full_df = pd.read_csv(out_csv, encoding='utf-8-sig', low_memory=False)
        full_df.to_excel(out_xlsx, index=False)
        saved_xlsx = True
        print(f'  저장: {out_xlsx}')
    else:
        print(f'  행 수 {n_written:,} > {MAX_ROWS_XLSX:,} → xlsx 생략 (csv 만 저장)')
    print()

    # ── 6. 결과 요약 ──────────────────────────────────────────────
    sep('완료 — 결과 요약')
    print(f'  입력 기둥 후보:            {n_col:>10,} 개')
    print(f'  생성 전체 코어 후보:        {n_total:>10,} 개')
    print(f'  buildable 코어:             {n_build:>10,} 개')
    print(f'  analysis_candidate 코어:    {n_cand:>10,} 개')
    print(f'  전체 조합 수:               {n_written:>10,} 개')
    print(f'  analysis_candidate 조합:    {n_analysis:>10,} 개')
    print(f'  xlsx 저장:   {"예" if saved_xlsx else "아니오 (1M 초과)"}')
    print(f'  CSV:  {out_csv}')
    if saved_xlsx:
        print(f'  XLSX: {out_xlsx}')
    print(f'  코어 라이브러리:  {clb_xlsx}')
    print()


if __name__ == '__main__':
    main()
