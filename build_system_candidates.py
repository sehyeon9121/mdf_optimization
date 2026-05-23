"""
build_system_candidates.py
4기둥 + 코어 시스템 후보 생성 -- 시스템 최적화 Step 3

입력:
  outputs/system/column_library.xlsx   (Step 1 출력)
  outputs/system/core_scenarios.xlsx   (Step 2 출력)

처리:
  1. 라이브러리에서 그룹별 대표 기둥 선택 (strip_count, rotation, type_structural)
  2. 4개 기둥 배치 패턴 조합 생성:
       - uniform_4  : 4개 기둥 동일 타입  (C1=C2=C3=C4=A)
       - diag_pair  : 대각 쌍 교체        (C1=C4=A, C2=C3=B)
       - x_pair     : x방향 쌍 교체       (C1=C3=A, C2=C4=B)
       - y_pair     : y방향 쌍 교체       (C1=C2=A, C3=C4=B)
  3. 6가지 코어 시나리오 조합
  4. 시스템 지표 계산:
       sum_Ix, sum_Iy, system_Ix_Iy, min_system_I,
       col_cost_floor_sep, col_cost_continuous,
       total_cost_floor_sep, total_cost_continuous,
       total_cost (= COST_MODE 기준),
       system_efficiency,
       CR_x, CR_y, e_x, e_y, norm_ecc, torsion_risk

비용 계산 방식 (COST_MODE):
  floor_by_floor : 층별 분리 -- 각 층 독립 절단, 4기둥 함께 풀링
                   col_cost = NUM_FLOORS x ceil(sum_N / pieces_per_member) x 10
  continuous     : 연속 제작 -- 4층 전체 통합 절단 (절단 손실 최소)
                   col_cost = ceil(4 x sum_N / pieces_per_member) x 10

출력:
  outputs/system/system_candidates.xlsx

평면 정보 (확정):
  기둥 위치: C1=(0,0), C2=(150,0), C3=(0,150), C4=(150,150) mm
  코어 위치: (75, 75) mm
  질량 중심 CM: (75, 75) mm
  층고: h = 200 mm
"""

import os
import math
import warnings
import itertools
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SYSTEM_DIR = os.path.join(BASE_DIR, 'outputs', 'system')

# ── 평면 정보 (확정) ─────────────────────────────────────────────
L   = 150       # mm  기둥 간격
CM  = (75, 75)  # mm  질량 중심

COL_POS = {
    'C1': (0,   0  ),
    'C2': (150, 0  ),
    'C3': (0,   150),
    'C4': (150, 150),
}

# 비틀림 위험 기준
TORSION_LOW  = 0.05
TORSION_HIGH = 0.15

# 대표 후보 추가 선택 수 (그룹당 상위 N개)
TOP_K = 3

# ── 비용 계산 상수 ────────────────────────────────────────────────
UNIT_PRICE      = 10    # 원 / 600mm 부재 1개
MEMBER_LENGTH   = 600   # mm
FLOOR_HEIGHT    = 200   # mm
NUM_FLOORS      = 4
PIECES_PER_MBR  = MEMBER_LENGTH // FLOOR_HEIGHT   # 3

# 비용 계산 방식: 'floor_by_floor' | 'continuous'
# floor_by_floor : 층마다 독립 절단, 4기둥 재료를 층별로 함께 풀링
# continuous     : 4층 전체 통합 절단 (절단 손실 최소, 재료 최소)
COST_MODE = 'floor_by_floor'


def col_system_cost_floor_sep(n_per_col: list) -> int:
    """층별 분리: 각 층 독립 절단. 4기둥 스트립 수 합산 기준."""
    total_N = sum(n_per_col)
    members_per_floor = math.ceil(total_N / PIECES_PER_MBR)
    return NUM_FLOORS * members_per_floor * UNIT_PRICE


def col_system_cost_continuous(n_per_col: list) -> int:
    """연속 제작: 4층 전체 통합 절단. 절단 손실 최소."""
    total_pieces = sum(n_per_col) * NUM_FLOORS
    members = math.ceil(total_pieces / PIECES_PER_MBR)
    return members * UNIT_PRICE


def sep(title=''):
    print("=" * 68)
    if title:
        print(f"  {title}")
        print("=" * 68)


# ─────────────────────────────────────────────────────────────────
# 시스템 지표 계산
# ─────────────────────────────────────────────────────────────────
def compute_system(col_rows, core_row):
    """
    col_rows : dict {'C1': row, 'C2': row, 'C3': row, 'C4': row}
    core_row : Series (Ix_core, Iy_core, cost_core_floor_sep, cost_core_continuous)
    반환: dict of system metrics
    """
    positions = COL_POS  # {'C1': (x, y), ...}

    sum_Ix = sum(col_rows[c]['Ix'] for c in col_rows) + core_row['Ix_core']
    sum_Iy = sum(col_rows[c]['Iy'] for c in col_rows) + core_row['Iy_core']

    # 기둥 strip_count 추출 (비용 계산용)
    n_per_col = [int(col_rows[c]['strip_count']) for c in ['C1', 'C2', 'C3', 'C4']]

    # 기둥 비용: 두 방식 모두 계산
    col_cost_fbf  = col_system_cost_floor_sep(n_per_col)
    col_cost_cont = col_system_cost_continuous(n_per_col)

    # 코어 비용: 두 방식 모두 계산
    core_cost_fbf  = int(core_row['cost_core_floor_sep'])
    core_cost_cont = int(core_row['cost_core_continuous'])

    # COST_MODE 기준 primary 비용
    if COST_MODE == 'floor_by_floor':
        col_cost   = col_cost_fbf
        core_cost  = core_cost_fbf
    else:
        col_cost   = col_cost_cont
        core_cost  = core_cost_cont
    total_cost = col_cost + core_cost

    # CR 계산 (기둥만 사용 -- 코어는 평면 중앙에 고정)
    # 코어 기여: Ix_core * 75 / sum_Ix, Iy_core * 75 / sum_Iy
    sum_Ix_col = sum(col_rows[c]['Ix'] for c in col_rows)
    sum_Iy_col = sum(col_rows[c]['Iy'] for c in col_rows)

    Ix_total = sum_Ix_col + core_row['Ix_core']
    Iy_total = sum_Iy_col + core_row['Iy_core']

    # CR_x = sum(Iy_i * xi) / sum(Iy_i)  [y방향 횡력 저항 -- x좌표 기준]
    num_CRx = (sum(col_rows[c]['Iy'] * positions[c][0] for c in col_rows)
               + core_row['Iy_core'] * 75)
    CR_x = num_CRx / Iy_total if Iy_total > 0 else 75.0

    # CR_y = sum(Ix_i * yi) / sum(Ix_i)  [x방향 횡력 저항 -- y좌표 기준]
    num_CRy = (sum(col_rows[c]['Ix'] * positions[c][1] for c in col_rows)
               + core_row['Ix_core'] * 75)
    CR_y = num_CRy / Ix_total if Ix_total > 0 else 75.0

    e_x = abs(CR_x - CM[0])
    e_y = abs(CR_y - CM[1])
    norm_ecc = max(e_x, e_y) / L

    if norm_ecc < TORSION_LOW:
        torsion_risk = 'low'
    elif norm_ecc < TORSION_HIGH:
        torsion_risk = 'medium'
    else:
        torsion_risk = 'high'

    min_system_I = min(sum_Ix, sum_Iy)
    sys_eff = min_system_I / total_cost if total_cost > 0 else 0.0
    sys_ratio = sum_Ix / sum_Iy if sum_Iy > 0 else float('inf')

    return {
        'sum_Ix':                sum_Ix,
        'sum_Iy':                sum_Iy,
        'system_Ix_Iy':          round(sys_ratio, 4),
        'min_system_I':          min_system_I,
        'col_cost_floor_sep':    col_cost_fbf,
        'col_cost_continuous':   col_cost_cont,
        'col_cost':              col_cost,
        'total_cost_floor_sep':  col_cost_fbf  + core_cost_fbf,
        'total_cost_continuous': col_cost_cont + core_cost_cont,
        'total_cost':            total_cost,
        'system_efficiency':     round(sys_eff, 4),
        'CR_x':                  round(CR_x, 2),
        'CR_y':                  round(CR_y, 2),
        'e_x':                   round(e_x, 2),
        'e_y':                   round(e_y, 2),
        'norm_ecc':              round(norm_ecc, 4),
        'torsion_risk':          torsion_risk,
    }


def col_tag(row):
    """N4_bal_0 형태 태그 생성"""
    n   = int(row['strip_count'])
    rot = int(row['rotation'])
    t   = row['type_structural']
    abbr = {'balanced': 'bal', 'near_balanced': 'nbal',
            'x_strong': 'xST', 'y_strong': 'yST'}
    return f"N{n}_{abbr.get(t, t)}_{rot}"


# ─────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────
def main():
    os.makedirs(SYSTEM_DIR, exist_ok=True)

    # ── 1. 데이터 로드 ─────────────────────────────────────────────
    sep("Step 1  데이터 로드")
    lib_path  = os.path.join(SYSTEM_DIR, 'column_library.xlsx')
    core_path = os.path.join(SYSTEM_DIR, 'core_scenarios.xlsx')

    lib  = pd.read_excel(lib_path)
    core = pd.read_excel(core_path)

    print(f"  column_library : {len(lib):,}개")
    print(f"  core_scenarios : {len(core)}개")
    print()

    # ── 2. 그룹별 대표 기둥 선택 ──────────────────────────────────
    sep("Step 2  그룹별 대표 기둥 선택 (TOP_K={})".format(TOP_K))

    grp_cols = ['strip_count', 'rotation', 'type_structural']
    repr_rows = []
    for keys, grp in lib.groupby(grp_cols, sort=True):
        top = grp.nlargest(TOP_K, 'efficiency')
        repr_rows.append(top)

    repr_df = pd.concat(repr_rows, ignore_index=True)
    repr_df['col_tag'] = repr_df.apply(col_tag, axis=1)

    # 태그별 최고 efficiency만 유지 (중복 제거)
    repr_df = (repr_df
               .sort_values('efficiency', ascending=False)
               .drop_duplicates('col_tag')
               .reset_index(drop=True))

    print(f"  선택된 대표 기둥: {len(repr_df)}개")
    print(f"  {'col_tag':^18}  {'Ix':>8}  {'Iy':>8}  {'Ix/Iy':>7}  {'cost':>5}  {'eff':>8}")
    print(f"  {'-'*62}")
    for _, r in repr_df.sort_values('col_tag').iterrows():
        print(f"  {r['col_tag']:^18}  {r['Ix']:>8,.0f}  {r['Iy']:>8,.0f}"
              f"  {r['Ix/Iy']:>7.4f}  {int(r['cost']):>5}  {r['efficiency']:>8.4f}")
    print()

    # ── 3. 배치 패턴별 조합 생성 ─────────────────────────────────
    sep("Step 3  4기둥 배치 패턴 × 코어 시나리오 조합")

    tags = repr_df['col_tag'].tolist()
    tag_map = repr_df.set_index('col_tag')

    records = []

    def make_record(arrangement, col_tags_dict, core_row):
        col_rows = {pos: tag_map.loc[t] for pos, t in col_tags_dict.items()}
        metrics  = compute_system(col_rows, core_row)

        rec = {
            'arrangement':    arrangement,
            'C1_tag':         col_tags_dict['C1'],
            'C2_tag':         col_tags_dict['C2'],
            'C3_tag':         col_tags_dict['C3'],
            'C4_tag':         col_tags_dict['C4'],
            'core_scenario':  core_row['scenario_id'],
        }
        rec.update(metrics)

        # 개별 기둥 정보 (비용/Ix/Iy)
        for pos in ['C1', 'C2', 'C3', 'C4']:
            r = col_rows[pos]
            rec[f'{pos}_N']   = int(r['strip_count'])
            rec[f'{pos}_rot'] = int(r['rotation'])
            rec[f'{pos}_Ix']  = r['Ix']
            rec[f'{pos}_Iy']  = r['Iy']
            rec[f'{pos}_cost']= r['cost']
        return rec

    n_col = len(tags)
    total_before = 0

    for _, core_row in core.iterrows():
        sid = core_row['scenario_id']

        # uniform_4: 모든 기둥 동일
        for tA in tags:
            col_dict = {'C1': tA, 'C2': tA, 'C3': tA, 'C4': tA}
            records.append(make_record('uniform_4', col_dict, core_row))

        # diag_pair: C1=C4=A, C2=C3=B  (A != B)
        for tA, tB in itertools.permutations(tags, 2):
            col_dict = {'C1': tA, 'C2': tB, 'C3': tB, 'C4': tA}
            records.append(make_record('diag_pair', col_dict, core_row))

        # x_pair: C1=C3=A, C2=C4=B  (A != B)
        for tA, tB in itertools.permutations(tags, 2):
            col_dict = {'C1': tA, 'C2': tB, 'C3': tA, 'C4': tB}
            records.append(make_record('x_pair', col_dict, core_row))

        # y_pair: C1=C2=A, C3=C4=B  (A != B)
        for tA, tB in itertools.permutations(tags, 2):
            col_dict = {'C1': tA, 'C2': tA, 'C3': tB, 'C4': tB}
            records.append(make_record('y_pair', col_dict, core_row))

    df = pd.DataFrame(records)

    print(f"  생성된 시스템 후보: {len(df):,}개")
    print()

    # ── 4. 통계 요약 ──────────────────────────────────────────────
    sep("Step 4  통계 요약")

    arr_cnt = df.groupby('arrangement').size()
    print("  [배치 패턴별 후보 수]")
    for arr, cnt in arr_cnt.items():
        print(f"    {arr:^12}: {cnt:>8,}")
    print()

    risk_cnt = df.groupby('torsion_risk').size()
    print("  [비틀림 위험 분포]")
    for risk in ['low', 'medium', 'high']:
        cnt = risk_cnt.get(risk, 0)
        pct = cnt / len(df) * 100
        print(f"    {risk:^8}: {cnt:>8,}개  ({pct:.1f}%)")
    print()

    print("  [min_system_I 분포]")
    for arr in ['uniform_4', 'diag_pair', 'x_pair', 'y_pair']:
        sub = df[df['arrangement'] == arr]['min_system_I']
        if sub.empty: continue
        print(f"    {arr:^12}: min={sub.min():>10,.0f}  max={sub.max():>10,.0f}"
              f"  median={sub.median():>10,.0f}")
    print()

    # ── 5. 저장 ───────────────────────────────────────────────────
    sep("Step 5  저장")

    out_path = os.path.join(SYSTEM_DIR, 'system_candidates.xlsx')

    # 컬럼 순서 정리
    front = ['arrangement', 'C1_tag', 'C2_tag', 'C3_tag', 'C4_tag', 'core_scenario',
             'sum_Ix', 'sum_Iy', 'system_Ix_Iy', 'min_system_I',
             'col_cost_floor_sep', 'col_cost_continuous', 'col_cost',
             'total_cost_floor_sep', 'total_cost_continuous', 'total_cost',
             'system_efficiency',
             'CR_x', 'CR_y', 'e_x', 'e_y', 'norm_ecc', 'torsion_risk']
    detail = [c for c in df.columns if c not in front]
    df = df[front + detail]

    df.to_excel(out_path, index=False)
    print(f"  저장: {out_path}")
    print(f"  행 수: {len(df):,}  |  컬럼: {len(df.columns)}")
    print()

    # ── 6. Top-10 요약 ────────────────────────────────────────────
    sep("Top 10  (low torsion, 최고 system_efficiency)")
    top10 = (df[df['torsion_risk'] == 'low']
             .nlargest(10, 'system_efficiency'))

    print(f"  {'arr':^12}  {'C1':^18}  {'C2':^18}  {'core':^15}"
          f"  {'sumIx':>8}  {'sumIy':>8}  {'eff':>8}  {'norm_e':>7}")
    print(f"  {'-'*100}")
    for _, r in top10.iterrows():
        print(f"  {r['arrangement']:^12}  {r['C1_tag']:^18}  {r['C2_tag']:^18}"
              f"  {r['core_scenario']:^15}"
              f"  {r['sum_Ix']:>8,.0f}  {r['sum_Iy']:>8,.0f}"
              f"  {r['system_efficiency']:>8.2f}  {r['norm_ecc']:>7.4f}")

    sep("완료")
    print("  outputs/system/system_candidates.xlsx")
    print("  -> 다음 단계: analyze_system_candidates.py  (최적 시스템 선정)")
    print()


if __name__ == '__main__':
    main()
