"""
section_properties.py
단면 성능 지표 계산 모듈
- 단면적 A, 도심(cx, cy), 단면 2차 모멘트 Ix/Iy
- 비용 및 효율지수 계산
"""
from section_geometry import grid_to_positions


def compute_section_properties(grid, config, strip):
    """
    격자 배열로부터 단면 성능 지표를 계산한다.

    병렬축 정리 적용:
      Ix = Σ (Ix_local_i + A_i * (y_ci - y_bar)^2)
      Iy = Σ (Iy_local_i + A_i * (x_ci - x_bar)^2)

    Args:
        grid   : numpy 2D array (0/1/2)
        config : 설정 dict
        strip  : MDFStrip 인스턴스

    Returns:
        dict (strip_count, A, cx, cy, Ix, Iy, cost, efficiency)
        또는 None (스트립 없음)
    """
    cell_size = config['grid']['cell_size']
    positions = grid_to_positions(grid, cell_size)

    if not positions:
        return None

    strip_count = len(positions)
    a_i = strip.area()          # 24 mm^2 (방향 무관)
    A = strip_count * a_i

    # 도심 계산 (모든 스트립 면적이 동일하므로 단순 평균)
    cx = sum(p[3] for p in positions) / strip_count
    cy = sum(p[4] for p in positions) / strip_count

    # 단면 2차 모멘트 (병렬축 정리)
    Ix = 0.0
    Iy = 0.0
    for _, _, orientation, x_c, y_c in positions:
        Ix_loc, Iy_loc = strip.local_inertia(orientation)
        Ix += Ix_loc + a_i * (y_c - cy) ** 2
        Iy += Iy_loc + a_i * (x_c - cx) ** 2

    cost = strip_count * strip.cost

    # 효율지수: min(Ix, Iy) / cost
    efficiency = min(Ix, Iy) / cost if cost > 0 else 0.0

    return {
        'strip_count': strip_count,
        'A':          round(A, 4),
        'cx':         round(cx, 4),
        'cy':         round(cy, 4),
        'Ix':         round(Ix, 4),
        'Iy':         round(Iy, 4),
        'cost':       cost,
        'efficiency': round(efficiency, 4),
    }
