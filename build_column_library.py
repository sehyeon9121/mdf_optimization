"""
build_column_library.py
기둥 후보 라이브러리 구축 — 시스템 최적화 Step 1

소스:  outputs/results_by_strip_count.xlsx  (N=3~7)
처리:
  1. N=3~7 전체 로드 (Ix/Iy 필터 없음 — x_strong/y_strong 포함)
  2. 0° / 90° 회전 두 버전 생성 (90°는 Ix·Iy 교환)
  3. type_structural (balanced/near_balanced/x_strong/y_strong) 분류
  4. type_cost (low_cost/baseline/safe/high_performance) 분류
  5. is_representative 플래그 — 타입별 대표 후보 TOP_K개

출력:  outputs/system/column_library.xlsx

평면 정보 (확정):
  기둥 위치: C1=(0,0), C2=(150,0), C3=(0,150), C4=(150,150) mm
  코어 위치: (75, 75) mm  (평면 중앙)
  층고:       h = 200 mm / 층
  → 비틀림 계산 기준 포함 (build_system_candidates.py에서 사용)
"""

import os
import math
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs')
SYSTEM_DIR = os.path.join(OUTPUT_DIR, 'system')

# ── 평면 정보 (확정) ─────────────────────────────────────────────
PLAN = {
    'span_L':   150,    # mm  기둥 간격 (양방향)
    'story_h':  200,    # mm  층고 (기둥 유효 길이)
    'col_pos': {        # 기둥 평면 좌표 (mm)
        'C1': (0,   0  ),
        'C2': (150, 0  ),
        'C3': (0,   150),
        'C4': (150, 150),
    },
    'core_pos': (75, 75),   # 코어 중심 (mm)
    'CM':       (75, 75),   # 질량 중심 = 기하 중심 (균일 질량 가정)
}

# ── 분류 기준 ─────────────────────────────────────────────────────
BALANCED_TIGHT = (0.90, 1.10)   # balanced
BALANCED_WIDE  = (0.80, 1.25)   # near_balanced 포함 범위
# x_strong : Ix/Iy > 1.25
# y_strong : Ix/Iy < 0.80

COST_TIER = {3: 'low_cost', 4: 'baseline', 5: 'safe'}
# N=6,7 → 'high_performance'

# ── 4층 기준 비용 계산 ────────────────────────────────────────────
# 부재 규격 : 4×6×600 mm,  단가 = 10원/개
# 층고      : 200 mm  →  1개 부재에서 3조각 (600/200=3, 무손실)
# 4층 소요  : N조각/층 × 4층 = 4N조각  →  ceil(4N/3) 개 부재
UNIT_PRICE     = 10    # 원 / 부재
STRIP_LENGTH   = 600   # mm
FLOOR_HEIGHT   = 200   # mm
NUM_FLOORS     = 4
CUTS_PER_STRIP = STRIP_LENGTH // FLOOR_HEIGHT   # = 3

def cost_4floor(n_strips: int) -> int:
    pieces  = n_strips * NUM_FLOORS
    members = math.ceil(pieces / CUTS_PER_STRIP)
    return members * UNIT_PRICE

N_TARGET   = [3, 4, 5, 6, 7]
TOP_K_REPR = 5   # 타입별 대표 후보 수


def sep(title=''):
    print("=" * 66)
    if title:
        print(f"  {title}")
        print("=" * 66)


# ─────────────────────────────────────────────────────────────────
# 분류 함수
# ─────────────────────────────────────────────────────────────────
def classify_structural(ratio):
    lo_tight, hi_tight = BALANCED_TIGHT
    lo_wide,  hi_wide  = BALANCED_WIDE
    if lo_tight <= ratio <= hi_tight:   return 'balanced'
    if lo_wide  <= ratio <= hi_wide:    return 'near_balanced'
    if ratio > hi_wide:                 return 'x_strong'
    return 'y_strong'


def classify_cost(n):
    return COST_TIER.get(n, 'high_performance')


# ─────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────
def main():
    os.makedirs(SYSTEM_DIR, exist_ok=True)

    # ── 1. 데이터 로드 ────────────────────────────────────────────
    sep("Step 1  데이터 로드 (N=3~7 전체, Ix/Iy 필터 없음)")
    src = os.path.join(OUTPUT_DIR, 'results_by_strip_count.xlsx')
    raw = pd.read_excel(src)

    # 컬럼 표준화 (Ix(mm⁴) → Ix 등)
    rename = {}
    for c in raw.columns:
        if c.startswith('Ix('):   rename[c] = 'Ix'
        elif c.startswith('Iy('): rename[c] = 'Iy'
        elif c.startswith('A('):  rename[c] = 'A'
        elif c == 'name':         rename[c] = 'source_name'
    raw = raw.rename(columns=rename)

    df = raw[raw['strip_count'].isin(N_TARGET)].copy()
    print(f"  전체 후보: {len(df):,}개")
    for n in N_TARGET:
        sub = df[df['strip_count'] == n]
        print(f"    N={n}: {len(sub):>6,}개  "
              f"(Ix/Iy 범위: {sub['Ix/Iy'].min():.3f} ~ {sub['Ix/Iy'].max():.3f})")
    print()

    # ── 2. 0°/90° 두 버전 생성 ───────────────────────────────────
    sep("Step 2  0° / 90° 회전 버전 생성")

    df0          = df.copy()
    df0['rotation'] = 0

    df90         = df.copy()
    df90['rotation'] = 90
    # 90°: x축 → y축, y축 → x축 방향 교환 → Ix와 Iy swap
    df90['Ix']   = df['Iy'].values
    df90['Iy']   = df['Ix'].values

    lib = pd.concat([df0, df90], ignore_index=True)

    # 비용 재계산: 4층 기준 (ceil(4N/3) × 단가)
    lib['cost_1floor'] = lib['strip_count'] * UNIT_PRICE          # 참고용 (1층 기준)
    lib['cost']        = lib['strip_count'].apply(cost_4floor)    # 4층 실제 기준

    # 회전 후 지표 재계산
    lib['Ix/Iy']    = lib['Ix'] / lib['Iy']
    lib['min_I']     = lib[['Ix', 'Iy']].min(axis=1)
    lib['efficiency']= lib['min_I'] / lib['cost']

    print(f"  0°+90° 합산: {len(lib):,}개")
    print(f"  [비용 기준: 4층, 부재 {STRIP_LENGTH}mm/{FLOOR_HEIGHT}mm = {CUTS_PER_STRIP}조각/부재]")
    print(f"  {'N':>3}  {'cost_1floor':>12}  {'cost_4floor':>12}")
    for n in N_TARGET:
        c1 = n * UNIT_PRICE
        c4 = cost_4floor(n)
        print(f"  {n:>3}  {c1:>12}  {c4:>12}")
    print()
    print()

    # ── 3. 분류 ──────────────────────────────────────────────────
    sep("Step 3  type_structural / type_cost 분류")

    lib['type_structural'] = lib['Ix/Iy'].apply(classify_structural)
    lib['type_cost']       = lib['strip_count'].apply(classify_cost)

    print("  [type_structural 분포]")
    print(f"  {'N':>3}  {'rot':>4}  {'balanced':>10}"
          f"  {'near_bal':>10}  {'x_strong':>10}  {'y_strong':>10}  합계")
    print(f"  {'-'*65}")
    for n in N_TARGET:
        for rot in [0, 90]:
            sub = lib[(lib['strip_count'] == n) & (lib['rotation'] == rot)]
            if sub.empty: continue
            cnt = sub['type_structural'].value_counts()
            total = len(sub)
            print(f"  {n:>3}  {rot:>4}°"
                  f"  {cnt.get('balanced', 0):>10,}"
                  f"  {cnt.get('near_balanced', 0):>10,}"
                  f"  {cnt.get('x_strong', 0):>10,}"
                  f"  {cnt.get('y_strong', 0):>10,}"
                  f"  {total:>6,}")
    print()

    # ── 4. lib_id 부여 ────────────────────────────────────────────
    lib = lib.reset_index(drop=True)
    lib.insert(0, 'lib_id', [f"L{i+1:06d}" for i in range(len(lib))])

    # ── 5. 대표 후보 선정 (is_representative) ───────────────────
    sep("Step 4  대표 후보 선정 (타입별 TOP_K={})".format(TOP_K_REPR))

    lib['is_representative'] = False
    grp_cols = ['strip_count', 'rotation', 'type_structural']
    repr_count = 0

    print(f"  {'N':>3}  {'rot':>4}  {'type':^16}  {'대표수':>6}  {'eff 범위'}")
    print(f"  {'-'*60}")
    for keys, grp in lib.groupby(grp_cols, sort=True):
        n, rot, stype = keys
        top_idx = grp.nlargest(TOP_K_REPR, 'efficiency').index
        lib.loc[top_idx, 'is_representative'] = True
        repr_count += len(top_idx)
        eff_min = grp.loc[top_idx, 'efficiency'].min()
        eff_max = grp.loc[top_idx, 'efficiency'].max()
        print(f"  {n:>3}  {rot:>4}°  {stype:^16}  {len(top_idx):>6}  "
              f"{eff_min:.4f} ~ {eff_max:.4f}")

    print(f"\n  전체 대표 후보: {repr_count}개 / {len(lib):,}개")
    print()

    # ── 6. 저장 ──────────────────────────────────────────────────
    sep("Step 5  저장")

    # 출력 컬럼 순서 정리
    keep = ['lib_id', 'source_name', 'strip_count', 'rotation',
            'cost', 'Ix', 'Iy', 'Ix/Iy', 'min_I', 'efficiency',
            'type_structural', 'type_cost', 'is_representative', 'search_type']
    keep = [c for c in keep if c in lib.columns]

    lib_out = (lib[keep]
               .sort_values(['strip_count', 'rotation', 'type_structural', 'efficiency'],
                            ascending=[True, True, True, False])
               .reset_index(drop=True))

    out_path = os.path.join(SYSTEM_DIR, 'column_library.xlsx')
    lib_out.to_excel(out_path, index=False)
    print(f"  저장: {out_path}")
    print(f"  전체: {len(lib_out):,}개  |  대표 후보: {lib_out['is_representative'].sum():,}개")
    print()

    # ── 7. 대표 후보 요약 출력 ───────────────────────────────────
    sep("대표 후보 요약 (is_representative=True)")
    repr_df = lib_out[lib_out['is_representative']].copy()

    print(f"  {'lib_id':^10}  {'source':^16}  {'N':>3}  {'rot':>4}"
          f"  {'Ix/Iy':>7}  {'min_I':>10}  {'eff':>8}  type")
    print(f"  {'-'*80}")
    for _, r in repr_df.sort_values(['strip_count', 'rotation', 'type_structural']).iterrows():
        print(f"  {r['lib_id']:^10}  {r['source_name']:^16}  {int(r['strip_count']):>3}"
              f"  {int(r['rotation']):>4}°"
              f"  {r['Ix/Iy']:>7.4f}"
              f"  {r['min_I']:>10,.1f}"
              f"  {r['efficiency']:>8.4f}"
              f"  {r['type_structural']} / {r['type_cost']}")

    # ── 8. 평면 정보 확인 출력 ───────────────────────────────────
    print()
    sep("평면 정보 (확정)")
    print(f"  스팬 L       : {PLAN['span_L']} mm")
    print(f"  층고 h       : {PLAN['story_h']} mm")
    print(f"  기둥 위치    : C1{PLAN['col_pos']['C1']}  C2{PLAN['col_pos']['C2']}")
    print(f"               C3{PLAN['col_pos']['C3']}  C4{PLAN['col_pos']['C4']}")
    print(f"  코어 위치    : {PLAN['core_pos']} mm (평면 중앙)")
    print(f"  질량 중심 CM : {PLAN['CM']} mm")
    print()
    print("  [비틀림 위험 계산 공식 (build_system_candidates.py에서 사용)]")
    print("    CR_x = sum(Iy_col_i * xi) / sum(Iy_col_i)")
    print("    CR_y = sum(Ix_col_i * yi) / sum(Ix_col_i)")
    print("    e_x  = |CR_x - CM_x|  ,  e_y = |CR_y - CM_y|")
    print(f"    norm_e = max(e_x, e_y) / {PLAN['span_L']}  (0이면 완전 균형)")
    print()

    sep("완료")
    print(f"  outputs/system/column_library.xlsx")
    print(f"  → 다음 단계: build_system_candidates.py")
    print()


if __name__ == '__main__':
    main()
