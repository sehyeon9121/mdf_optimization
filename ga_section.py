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
