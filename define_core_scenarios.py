"""
define_core_scenarios.py
코어 시나리오 6개 정의 -- 시스템 최적화 Step 2

출력: outputs/system/core_scenarios.xlsx

부재 규격: 4x6x600mm, 단가=10원, 층고=200mm
  → 600mm 부재 1개에서 200mm 조각 3개 제작 (pieces_per_member = 3)

제작 방식별 비용 (N: 1층 기준 코어 스트립 수):
  층별 분리: 각 층 독립 절단  cost = 4 x ceil(N/3) x 10
  연속 제작: 4층 통합 절단    cost =   ceil(4N/3) x 10
  (두 방식이 다른 경우: N이 3의 배수가 아닐 때)

코어 비용 예시:
  none  N= 0 : 층별=  0  연속=  0
  weak  N= 5 : 층별= 80  연속= 70
  base  N= 8 : 층별=120  연속=110
  strong N=12 : 층별=160  연속=160  (12가 3의 배수 -> 동일)
  x/y   N=10 : 층별=160  연속=140
"""

import os
import math
import pandas as pd

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SYSTEM_DIR = os.path.join(BASE_DIR, 'outputs', 'system')

# ── 비용 상수 ─────────────────────────────────────────────────────
UNIT_PRICE      = 10    # 원 / 600mm 부재 1개
MEMBER_LENGTH   = 600   # mm
FLOOR_HEIGHT    = 200   # mm
NUM_FLOORS      = 4
PIECES_PER_MBR  = MEMBER_LENGTH // FLOOR_HEIGHT   # 3


def cost_floor_sep(n_1floor: int) -> int:
    """층별 분리: 각 층 독립 절단. 코어 스트립 n_1floor개 기준."""
    if n_1floor == 0:
        return 0
    members_per_floor = math.ceil(n_1floor / PIECES_PER_MBR)
    return NUM_FLOORS * members_per_floor * UNIT_PRICE


def cost_continuous(n_1floor: int) -> int:
    """연속 제작: 4층 전체 통합 절단 (최소 재료, 절단 손실 최소화)."""
    if n_1floor == 0:
        return 0
    total_pieces = n_1floor * NUM_FLOORS
    members = math.ceil(total_pieces / PIECES_PER_MBR)
    return members * UNIT_PRICE


# ── 코어 시나리오 정의 ────────────────────────────────────────────
# n_1floor: 1층 기준 코어 스트립 수 (비용 계산 기준값)
SCENARIOS = [
    {
        'scenario_id': 'none',
        'n_1floor':     0,
        'Ix_core':      0,
        'Iy_core':      0,
        'Ix_Iy_core':  '-',
        'ref_level':   '코어 없음',
        'description': '코어 미사용 -- 기둥 4개만으로 구성 (최소 비용)',
    },
    {
        'scenario_id': 'weak',
        'n_1floor':     5,
        'Ix_core':      5_000,
        'Iy_core':      5_000,
        'Ix_Iy_core':  1.00,
        'ref_level':   'N=5 수준 x 0.6',
        'description': '약한 코어 -- 단일 기둥 N=4~5 사이 수준 (경제형)',
    },
    {
        'scenario_id': 'base',
        'n_1floor':     8,
        'Ix_core':      15_000,
        'Iy_core':      15_000,
        'Ix_Iy_core':  1.00,
        'ref_level':   'N=6~7 수준',
        'description': '기본 코어 -- 단일 기둥 N=6~7 수준 (표준)',
    },
    {
        'scenario_id': 'strong',
        'n_1floor':     12,
        'Ix_core':      40_000,
        'Iy_core':      40_000,
        'Ix_Iy_core':  1.00,
        'ref_level':   'N=7 x 1.8',
        'description': '강한 코어 -- N=7의 약 2배 (보수적 안전 기준)',
    },
    {
        'scenario_id': 'x_strong_core',
        'n_1floor':     10,
        'Ix_core':      40_000,
        'Iy_core':      10_000,
        'Ix_Iy_core':  4.00,
        'ref_level':   'Ix 우세',
        'description': 'x방향 강화 코어 -- Ix >> Iy (y방향 횡력 대응)',
    },
    {
        'scenario_id': 'y_strong_core',
        'n_1floor':     10,
        'Ix_core':      10_000,
        'Iy_core':      40_000,
        'Ix_Iy_core':  0.25,
        'ref_level':   'Iy 우세',
        'description': 'y방향 강화 코어 -- Iy >> Ix (x방향 횡력 대응)',
    },
]


def main():
    os.makedirs(SYSTEM_DIR, exist_ok=True)

    df = pd.DataFrame(SCENARIOS)

    # 두 제작 방식별 비용 계산
    df['cost_core_floor_sep']  = df['n_1floor'].apply(cost_floor_sep)
    df['cost_core_continuous'] = df['n_1floor'].apply(cost_continuous)
    # cost_core: 두 스크립트 모두 이 컬럼을 참조 -- COST_MODE에 따라 덮어씌워짐
    df['cost_core'] = df['cost_core_continuous']   # 기본값 = 연속

    out_path = os.path.join(SYSTEM_DIR, 'core_scenarios.xlsx')
    df.to_excel(out_path, index=False)

    # ── 출력 ────────────────────────────────────────────────────────
    print("=" * 72)
    print("  코어 시나리오 정의 (6개)")
    print("=" * 72)
    print(f"  {'scenario_id':^16}  {'n_1floor':>8}  "
          f"{'floor_sep':>10}  {'continuous':>10}  {'diff':>6}  ref")
    print(f"  {'-'*70}")
    for _, r in df.iterrows():
        diff = int(r['cost_core_floor_sep']) - int(r['cost_core_continuous'])
        print(f"  {r['scenario_id']:^16}  {int(r['n_1floor']):>8}  "
              f"  {int(r['cost_core_floor_sep']):>7}원  "
              f"  {int(r['cost_core_continuous']):>7}원  "
              f"  {diff:>+5}원  "
              f"  {r['ref_level']}")
    print()
    print(f"  저장: {out_path}")
    print()

    print("  [비용 공식]")
    print(f"  부재: 4x6x{MEMBER_LENGTH}mm,  단가={UNIT_PRICE}원,  층고={FLOOR_HEIGHT}mm")
    print(f"  pieces_per_member = {MEMBER_LENGTH}/{FLOOR_HEIGHT} = {PIECES_PER_MBR}")
    print(f"  층별 분리: {NUM_FLOORS} x ceil(N / {PIECES_PER_MBR}) x {UNIT_PRICE}")
    print(f"  연속 제작:   ceil({NUM_FLOORS}N / {PIECES_PER_MBR}) x {UNIT_PRICE}")
    print()

    print("  [두 방식이 달라지는 조건]")
    print("  N mod 3 != 0 일 때 층별 분리 > 연속 제작")
    print("  (각 층 절단 시 남은 조각을 다음 층에 쓸 수 없으면 낭비 발생)")
    print()


if __name__ == '__main__':
    main()
