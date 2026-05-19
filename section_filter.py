"""
section_filter.py
단면 후보 필터링 모듈
- 스트립 최소 개수
- 연결성 검사
- Ix/Iy 비율 범위 (기둥 / 코어 구분)
"""
from section_geometry import is_connected


def filter_section(grid, props, section_type, config):
    """
    단면 유효성 검사.

    Args:
        grid         : numpy 2D array
        props        : compute_section_properties() 반환값 dict
        section_type : 'column' 또는 'core'
        config       : 설정 dict

    Returns:
        True  - 유효한 단면
        False - 제거 대상
    """
    if props is None:
        return False

    # 최소 스트립 수 조건
    min_strips = config['ga'].get('min_strips', 2)
    if props['strip_count'] < min_strips:
        return False

    # 연결성 검사: 분리된 형상 제거
    if not is_connected(grid):
        return False

    # Ix/Iy 비율 검사
    Iy = props['Iy']
    if Iy == 0:
        return False

    ratio = props['Ix'] / Iy

    if section_type == 'column':
        cfg = config['column_filter']
    else:
        cfg = config['core_filter']

    if not (cfg['ix_iy_min'] <= ratio <= cfg['ix_iy_max']):
        return False

    return True
