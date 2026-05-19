"""
evaluator.py
단면 후보별 구조 특성 계산 및 필터링 모듈

계산 항목:
  - area_mm2  : 단면적 (mm²)
  - weight_kg : 무게 (kg), config의 length_mm 기준
  - Ix_mm4    : x축 단면 2차 모멘트 (mm⁴)  — 수평 하중에 대한 휨 저항
  - Iy_mm4    : y축 단면 2차 모멘트 (mm⁴)  — 수직 하중에 대한 휨 저항
  - score     : (Ix + Iy) / weight_kg       — 강성/무게 효율 지표

단면 2차 모멘트 계산 원리:
  박스(hollow rectangle):
    Ix = (w * d³ - inner_w * inner_d³) / 12
    Iy = (d * w³ - inner_d * inner_w³) / 12

  리브 (병렬축 정리, parallel axis theorem):
    Ix_rib = (inner_w * t³ / 12) + A_rib * d_centroid²
    Iy_rib = t * inner_w³ / 12  (y축 대칭이므로 도심 이동 없음)
"""


def compute_properties(candidate, config):
    """
    box_core 단면 하나의 구조 특성을 계산한다.

    Args:
        candidate (dict): width, depth, thickness, rib_count, type
        config    (dict): config.yaml 설정

    Returns:
        dict: candidate 항목 + area_mm2, weight_kg, Ix_mm4, Iy_mm4, score
    """
    w = candidate['width']       # 외부 폭  (mm)
    d = candidate['depth']       # 외부 깊이 (mm)
    t = candidate['thickness']   # 벽 두께  (mm)
    r = candidate['rib_count']   # 수평 리브 수

    # 밀도 단위 변환: kg/m³ → kg/mm³  (1 m³ = 10⁹ mm³)
    density = config['material']['density_kg_per_m3'] * 1e-9
    length  = config['section']['length_mm']   # 기준 길이 (mm)

    inner_w = w - 2 * t   # 내부 공동 폭  (mm)
    inner_d = d - 2 * t   # 내부 공동 깊이 (mm)

    # ── 단면적 ───────────────────────────────────────────────────
    # 박스 벽 면적: 외부 전체 - 내부 공동
    area_box = w * d - inner_w * inner_d

    # 리브 1개 면적: 폭 = inner_w, 높이 = t (벽 두께와 동일)
    area_one_rib = inner_w * t
    area_ribs    = r * area_one_rib

    area_total = area_box + area_ribs   # 총 단면적 (mm²)

    # ── 무게 ─────────────────────────────────────────────────────
    volume = area_total * length        # 부피 (mm³)
    weight = volume * density           # 무게 (kg)

    # ── 단면 2차 모멘트: 박스 본체 ───────────────────────────────
    # 외부 사각형의 Ix - 내부 공동의 Ix (도심이 동일하므로 직접 빼기 가능)
    Ix_box = (w * d**3 - inner_w * inner_d**3) / 12
    Iy_box = (d * w**3 - inner_d * inner_w**3) / 12

    # ── 단면 2차 모멘트: 수평 리브 기여 (병렬축 정리) ────────────
    Ix_ribs = 0.0
    Iy_ribs = 0.0

    if r > 0:
        # 리브 i의 중심 위치: 내부 공동 하단으로부터 spacing * i
        # 내부 공동은 단면 도심과 같은 y좌표 중심을 가짐
        # → 도심으로부터의 거리 = (spacing * i) - inner_d / 2
        spacing = inner_d / (r + 1)

        for i in range(1, r + 1):
            # 내부 공동 하단 기준 리브 중심 위치
            y_in_inner = spacing * i
            # 단면 전체 도심으로부터의 거리
            d_centroid = y_in_inner - inner_d / 2

            # Ix 기여: 자체 관성 + 병렬축 이동 항
            Ix_rib_self = inner_w * t**3 / 12
            Ix_ribs += Ix_rib_self + area_one_rib * d_centroid**2

            # Iy 기여: 리브는 y축에 대해 대칭 → 도심 이동 없음
            Iy_ribs += t * inner_w**3 / 12

    Ix_total = Ix_box + Ix_ribs
    Iy_total = Iy_box + Iy_ribs

    # ── score: 강성/무게 효율 ────────────────────────────────────
    score = (Ix_total + Iy_total) / weight if weight > 0 else 0.0

    return {
        **candidate,
        'area_mm2'  : round(area_total, 2),
        'weight_kg' : round(weight, 6),
        'Ix_mm4'    : round(Ix_total, 2),
        'Iy_mm4'    : round(Iy_total, 2),
        'score'     : round(score, 2),
    }


def filter_candidates(evaluated, config):
    """
    계산된 후보 중 필터 조건을 통과한 것만 반환한다.

    필터 조건 (하나라도 해당되면 제외):
      - 무게 초과: weight_kg > max_weight_kg
      - 단면적 미달: area_mm2 < min_area_mm2

    Args:
        evaluated (list): compute_properties 결과 list
        config    (dict): config.yaml 설정

    Returns:
        list of dict: 필터를 통과한 후보들
    """
    flt = config['filter']
    max_w = flt['max_weight_kg']
    min_a = flt['min_area_mm2']

    valid = []
    for c in evaluated:
        if c['weight_kg'] > max_w:
            continue   # 너무 무거운 단면 제외
        if c['area_mm2'] < min_a:
            continue   # 단면적이 너무 작은 단면 제외
        valid.append(c)

    return valid
