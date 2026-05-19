"""
ga_section.py
유전알고리즘(GA) 기반 단면 최적화 모듈

염색체: 격자 셀 값(0/1/2)의 1차원 배열
적합도: min(Ix, Iy) / cost  (유효 단면), 0 (무효 단면)
선택 방식: 토너먼트 선택 (size=3)
교차 방식: 단점 교차 (single-point crossover)
"""
import numpy as np
from section_geometry import is_connected
from section_properties import compute_section_properties
from section_filter import filter_section


# ─── 염색체 연산 ────────────────────────────────────────────────────

def random_chromosome(rows, cols, rng):
    """초기 염색체 무작위 생성 — 각 셀은 0, 1, 2 중 하나"""
    return rng.integers(0, 3, size=rows * cols)


def decode(chromosome, rows, cols):
    """1차원 염색체 → 2D 격자 (reshape)"""
    return chromosome.reshape(rows, cols)


def fitness(chromosome, rows, cols, config, strip, section_type):
    """
    적합도 함수.
    유효 단면이면 efficiency(min(Ix,Iy)/cost)를 반환, 아니면 0.
    """
    grid = decode(chromosome, rows, cols)
    props = compute_section_properties(grid, config, strip)
    if not filter_section(grid, props, section_type, config):
        return 0.0
    return props['efficiency']


# ─── 유전 연산자 ────────────────────────────────────────────────────

def selection(population, fitnesses, n_select, rng):
    """토너먼트 선택 (tournament size=3)"""
    selected = []
    pop_size = len(population)
    for _ in range(n_select):
        candidates = rng.choice(pop_size, size=3, replace=False)
        best = candidates[np.argmax(fitnesses[candidates])]
        selected.append(population[best].copy())
    return selected


def crossover(parent1, parent2, crossover_rate, rng):
    """단점 교차"""
    if rng.random() < crossover_rate:
        point = rng.integers(1, len(parent1))
        child1 = np.concatenate([parent1[:point], parent2[point:]])
        child2 = np.concatenate([parent2[:point], parent1[point:]])
    else:
        child1, child2 = parent1.copy(), parent2.copy()
    return child1, child2


def mutate(chromosome, mutation_rate, rng):
    """각 유전자를 mutation_rate 확률로 0/1/2 중 임의 값으로 교체"""
    mask = rng.random(len(chromosome)) < mutation_rate
    n_mut = int(mask.sum())
    if n_mut > 0:
        chromosome[mask] = rng.integers(0, 3, size=n_mut)
    return chromosome


# ─── GA 메인 ────────────────────────────────────────────────────────

def run_ga(config, strip, section_type, seed=42, verbose=True):
    """
    유전알고리즘 실행.

    Args:
        config       : 설정 dict
        strip        : MDFStrip 인스턴스
        section_type : 'column' 또는 'core'
        seed         : 랜덤 시드
        verbose      : 진행 로그 출력 여부

    Returns:
        list of dict — 유효 단면 결과, efficiency 내림차순 상위 top_n개
        각 dict 키: name, grid, strip_count, A, cx, cy, Ix, Iy, cost, efficiency
    """
    rng = np.random.default_rng(seed)

    ga_cfg  = config['ga']
    rows    = config['grid']['rows']
    cols    = config['grid']['cols']
    pop_size   = ga_cfg['population_size']
    n_gen      = ga_cfg['generations']
    mut_rate   = ga_cfg['mutation_rate']
    cross_rate = ga_cfg['crossover_rate']
    elite_n    = max(1, int(pop_size * ga_cfg['elite_ratio']))
    top_n      = ga_cfg['top_n']

    # 초기 집단 생성
    population = [random_chromosome(rows, cols, rng) for _ in range(pop_size)]

    # 고유 유효 단면 수집 (중복 제거용 dict)
    all_valid: dict = {}

    for gen in range(n_gen):
        # 적합도 평가
        fitnesses = np.array([
            fitness(chrom, rows, cols, config, strip, section_type)
            for chrom in population
        ])

        if verbose and (gen % 30 == 0 or gen == n_gen - 1):
            valid_n = int(np.sum(fitnesses > 0))
            print(f"  Gen {gen+1:4d}/{n_gen} | best={fitnesses.max():.4f} | valid={valid_n}/{pop_size}")

        # 유효 단면 수집
        for chrom, fit in zip(population, fitnesses):
            if fit > 0:
                key = tuple(chrom.tolist())
                if key not in all_valid:
                    grid = decode(chrom.copy(), rows, cols)
                    props = compute_section_properties(grid, config, strip)
                    props['grid'] = grid.tolist()
                    props['name'] = f"{section_type}_{len(all_valid):04d}"
                    all_valid[key] = props

        # 엘리트 보존
        elite_idx = np.argsort(fitnesses)[-elite_n:]
        elites = [population[i].copy() for i in elite_idx]

        # 선택 & 새 세대 생성
        selected = selection(population, fitnesses, pop_size - elite_n, rng)
        new_population = elites[:]

        i = 0
        while len(new_population) < pop_size:
            p1 = selected[i % len(selected)]
            p2 = selected[(i + 1) % len(selected)]
            c1, c2 = crossover(p1, p2, cross_rate, rng)
            c1 = mutate(c1, mut_rate, rng)
            c2 = mutate(c2, mut_rate, rng)
            new_population.append(c1)
            if len(new_population) < pop_size:
                new_population.append(c2)
            i += 2

        population = new_population

    results = sorted(all_valid.values(), key=lambda x: x['efficiency'], reverse=True)
    print(f"\n  [{section_type}] 유효 단면 {len(results)}개 발견 → 상위 {min(len(results), top_n)}개 반환")
    return results[:top_n]


# ─── 스트립 수 고정 탐색 ────────────────────────────────────────────

def init_chromosome_constrained(target_n, n_cells, rng):
    """정확히 target_n개 스트립을 가진 초기 염색체 생성"""
    chrom = np.zeros(n_cells, dtype=int)
    pos = rng.choice(n_cells, min(target_n, n_cells), replace=False)
    chrom[pos] = rng.integers(1, 3, size=len(pos))
    return chrom


def repair_chromosome(chromosome, target_n, rng):
    """
    교차·돌연변이 후 스트립 수를 target_n으로 보정.
    초과 시 무작위 제거, 부족 시 빈 셀에 무작위 추가.
    """
    chrom = chromosome.copy()
    strip_idx = np.where(chrom > 0)[0]
    empty_idx = np.where(chrom == 0)[0]
    diff = len(strip_idx) - target_n

    if diff > 0:
        remove = rng.choice(strip_idx, diff, replace=False)
        chrom[remove] = 0
    elif diff < 0:
        needed = -diff
        if len(empty_idx) >= needed:
            add = rng.choice(empty_idx, needed, replace=False)
            chrom[add] = rng.integers(1, 3, size=needed)

    return chrom


def fitness_constrained(chromosome, rows, cols, config, strip):
    """
    스트립 수 고정 탐색용 적합도.
    4-연결 단일 형상이면 efficiency 반환, 아니면 0.
    """
    grid = decode(chromosome, rows, cols)
    props = compute_section_properties(grid, config, strip)
    if props is None or not is_connected(grid):
        return 0.0
    return props['efficiency']


def run_ga_by_strip_count(config, strip, target_n, seed=42, verbose=False, max_collect=None):
    """
    스트립 수를 target_n으로 고정하고 최적 단면 배치 탐색.

    제약: 4-연결 단일 형상
    목적: efficiency = min(Ix, Iy) / cost 최대화

    Args:
        config      : 설정 dict
        strip       : MDFStrip 인스턴스
        target_n    : 배치할 스트립 정확한 개수 (1~25)
        seed        : 랜덤 시드
        verbose     : 중간 진행 출력 여부
        max_collect : 수집할 최대 유효 단면 수 (None이면 config 값 사용)

    Returns:
        list of dict, efficiency 내림차순 (최대 max_collect개)
        각 dict 키: name, grid, strip_count, A, cx, cy, Ix, Iy, cost, efficiency
    """
    rng = np.random.default_rng(seed + target_n)

    ga_cfg  = config['ga']
    rows    = config['grid']['rows']
    cols    = config['grid']['cols']
    n_cells = rows * cols

    if target_n < 1 or target_n > n_cells:
        return []

    pop_size    = ga_cfg['population_size']
    n_gen       = ga_cfg['generations']
    mut_rate    = ga_cfg['mutation_rate']
    cross_rate  = ga_cfg['crossover_rate']
    elite_n     = max(1, int(pop_size * ga_cfg['elite_ratio']))
    if max_collect is None:
        max_collect = ga_cfg.get('ga_max_collect', 500)

    population = [
        init_chromosome_constrained(target_n, n_cells, rng)
        for _ in range(pop_size)
    ]

    all_valid: dict = {}

    for gen in range(n_gen):
        fitnesses = np.array([
            fitness_constrained(chrom, rows, cols, config, strip)
            for chrom in population
        ])

        if verbose and (gen % 50 == 0 or gen == n_gen - 1):
            valid_n = int(np.sum(fitnesses > 0))
            print(f"    N={target_n:2d} Gen {gen+1:3d}/{n_gen}"
                  f" | best={fitnesses.max():.4f} | valid={valid_n}/{pop_size}")

        # 유효 단면 수집 (중복 제거)
        for chrom, fit in zip(population, fitnesses):
            if fit > 0:
                key = tuple(chrom.tolist())
                if key not in all_valid:
                    grid = decode(chrom.copy(), rows, cols)
                    props = compute_section_properties(grid, config, strip)
                    props['grid'] = grid.tolist()
                    props['name'] = f"n{target_n:02d}_{len(all_valid):04d}"
                    all_valid[key] = props

        # 엘리트 보존
        elite_idx = np.argsort(fitnesses)[-elite_n:]
        elites = [population[i].copy() for i in elite_idx]

        # 선택 → 교차 → 돌연변이 → 수리
        selected = selection(population, fitnesses, pop_size - elite_n, rng)
        new_population = elites[:]

        i = 0
        while len(new_population) < pop_size:
            p1 = selected[i % len(selected)]
            p2 = selected[(i + 1) % len(selected)]
            c1, c2 = crossover(p1, p2, cross_rate, rng)
            c1 = mutate(c1, mut_rate, rng)
            c2 = mutate(c2, mut_rate, rng)
            c1 = repair_chromosome(c1, target_n, rng)
            c2 = repair_chromosome(c2, target_n, rng)
            new_population.append(c1)
            if len(new_population) < pop_size:
                new_population.append(c2)
            i += 2

        population = new_population

    results = sorted(all_valid.values(), key=lambda x: x['efficiency'], reverse=True)
    return results[:max_collect]


# ─── 전수탐색 (N=1~exhaustive_max 용) ──────────────────────────────

def enumerate_all_arrangements(target_n, config, strip):
    """
    N개 스트립의 모든 유효(4-연결) 배치를 전수탐색.

    알고리즘:
      1. C(25, N) 위치 조합마다 BFS로 연결성 검사
      2. 연결된 조합에 대해서만 2^N 방향 조합 전부 계산
      → 비연결 조합은 방향 계산 생략하여 속도 최적화

    Args:
        target_n : 배치할 스트립 수 (N ≤ 6 권장)
        config   : 설정 dict
        strip    : MDFStrip 인스턴스

    Returns:
        list of dict, efficiency 내림차순 (모든 유효 배치 포함)
        각 dict 키: name, grid, strip_count, A, cx, cy, Ix, Iy, cost, efficiency
    """
    from itertools import combinations, product as iproduct

    rows    = config['grid']['rows']
    cols    = config['grid']['cols']
    n_cells = rows * cols

    results = []

    for positions in combinations(range(n_cells), target_n):
        # BFS 연결성 검사 — 방향 무관, 위치만으로 판단
        pos_set = set(positions)
        visited = {positions[0]}
        queue   = [positions[0]]
        while queue:
            cell = queue.pop()
            r, c = divmod(cell, cols)
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    nb = nr * cols + nc
                    if nb in pos_set and nb not in visited:
                        visited.add(nb)
                        queue.append(nb)

        if len(visited) != target_n:
            continue  # 비연결 → 방향 조합 생략

        # 연결된 위치 조합: 모든 방향 조합 (가로=1, 세로=2) 열거
        for orientations in iproduct([1, 2], repeat=target_n):
            grid = np.zeros((rows, cols), dtype=int)
            for pos, ori in zip(positions, orientations):
                r, c = divmod(pos, cols)
                grid[r, c] = ori

            props = compute_section_properties(grid, config, strip)
            if props is None:
                continue

            props['grid'] = grid.tolist()
            props['name'] = f"n{target_n:02d}_{len(results):05d}"
            results.append(props)

    return sorted(results, key=lambda x: x['efficiency'], reverse=True)
