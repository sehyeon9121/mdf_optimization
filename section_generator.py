"""
section_generator.py
box_core 타입 MDF 단면 후보 자동 생성 모듈

box_core 단면 구조:
  ┌─────────────────┐  ← depth
  │░░░░░░░░░░░░░░░░░│
  │░┌─────────────┐░│
  │░│             │░│  ← 내부 공동 (hollow)
  │░│─────────────│░│  ← 수평 리브 (rib)
  │░│             │░│
  │░└─────────────┘░│
  │░░░░░░░░░░░░░░░░░│
  └─────────────────┘
        width

  ░ = MDF 재료 (벽 두께: thickness)
  리브: 내부 공동을 수평으로 나누는 MDF 판
"""
import itertools


def generate_candidates(config):
    """
    config 설정 기반으로 모든 (width, depth, thickness, rib_count) 조합을 생성하고
    제작 가능 조건을 만족하는 후보만 반환한다.

    제작 불가 조건 (이 조건에 해당하면 제외):
      1. 벽 두께가 너무 두꺼워 내부 공동이 없는 경우
         (inner_w = width - 2*t <= 0  or  inner_d = depth - 2*t <= 0)
      2. 리브가 있는 경우, 리브 간격이 벽 두께보다 작아 리브를 배치할 수 없는 경우
         (spacing = inner_d / (rib_count + 1) < thickness)

    Args:
        config (dict): config.yaml에서 읽어온 설정 dict

    Returns:
        list of dict: 유효한 단면 파라미터 목록
                      각 항목: width, depth, thickness, rib_count, type
    """
    sec = config['section']

    # 파라미터 범위 생성 (range는 정수형 스텝만 지원)
    widths      = range(sec['width_min'],     sec['width_max']     + 1, sec['width_step'])
    depths      = range(sec['depth_min'],     sec['depth_max']     + 1, sec['depth_step'])
    thicknesses = range(sec['thickness_min'], sec['thickness_max'] + 1, sec['thickness_step'])
    rib_counts  = range(sec['rib_count_min'], sec['rib_count_max'] + 1)

    candidates = []

    # 모든 조합에 대해 제작 가능 여부 판단
    for w, d, t, r in itertools.product(widths, depths, thicknesses, rib_counts):

        inner_w = w - 2 * t   # 내부 공동 폭
        inner_d = d - 2 * t   # 내부 공동 깊이

        # 조건 1: 내부 공동이 존재해야 함
        if inner_w <= 0 or inner_d <= 0:
            continue

        # 조건 2: 리브가 있는 경우 리브 간격 확인
        if r > 0:
            # 내부 공동을 (rib_count + 1) 등분한 간격
            rib_spacing = inner_d / (r + 1)
            # 리브 두께(= 벽 두께)보다 간격이 작으면 물리적으로 배치 불가
            if rib_spacing < t:
                continue

        candidates.append({
            'width'    : w,
            'depth'    : d,
            'thickness': t,
            'rib_count': r,
            'type'     : 'box_core',
        })

    return candidates
