"""
main.py
MDF Strip 단면 최적화 실행 진입점

실행:
    python main.py
"""
import os
import sys

# 현재 파일 위치를 모듈 탐색 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from materials import load_config, MDFStrip
from ga_section import run_ga
from postprocess import save_results_to_csv, save_section_images

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs')


def main():
    print("=" * 55)
    print("  MDF Strip 단면 최적화")
    print("=" * 55)

    # 설정 및 재료 로드
    config = load_config()
    strip  = MDFStrip(config)

    print(f"\n[설정]")
    print(f"  격자    : {config['grid']['rows']} x {config['grid']['cols']} "
          f"(셀 크기 {config['grid']['cell_size']}mm)")
    print(f"  스트립  : {strip.b}mm x {strip.h}mm, 단가={strip.cost}")
    print(f"  GA      : 세대={config['ga']['generations']}, "
          f"집단={config['ga']['population_size']}")

    # ── 기둥 단면 최적화 ──────────────────────────────────────
    print("\n[기둥 단면 최적화]  Ix/Iy = 0.7 ~ 1.3")
    column_results = run_ga(config, strip, section_type='column', seed=42, verbose=True)

    # ── 코어 단면 최적화 ──────────────────────────────────────
    print("\n[코어 단면 최적화]  Ix/Iy = 0.5 ~ 2.0")
    core_results = run_ga(config, strip, section_type='core', seed=123, verbose=True)

    # ── 결과 저장 ─────────────────────────────────────────────
    print("\n[결과 저장]")
    all_results = column_results + core_results

    save_results_to_csv(all_results,    os.path.join(OUTPUT_DIR, 'generated_sections.csv'))
    save_results_to_csv(column_results, os.path.join(OUTPUT_DIR, 'top_column_sections.csv'))
    save_results_to_csv(core_results,   os.path.join(OUTPUT_DIR, 'top_core_sections.csv'))

    save_section_images(
        column_results, config, strip,
        output_dir=os.path.join(OUTPUT_DIR, 'images', 'column'),
        max_images=10
    )
    save_section_images(
        core_results, config, strip,
        output_dir=os.path.join(OUTPUT_DIR, 'images', 'core'),
        max_images=10
    )

    # ── 최적 결과 요약 출력 ───────────────────────────────────
    print("\n[최적 결과 요약]")

    if column_results:
        b = column_results[0]
        ratio = b['Ix'] / b['Iy']
        print(f"  기둥 최적: {b['name']}")
        print(f"    스트립={b['strip_count']}개  A={b['A']}mm²")
        print(f"    Ix={b['Ix']:.2f}  Iy={b['Iy']:.2f}  Ix/Iy={ratio:.3f}")
        print(f"    cost={b['cost']}  efficiency={b['efficiency']:.4f}")
    else:
        print("  기둥: 유효 단면 없음")

    if core_results:
        b = core_results[0]
        ratio = b['Ix'] / b['Iy']
        print(f"  코어 최적: {b['name']}")
        print(f"    스트립={b['strip_count']}개  A={b['A']}mm²")
        print(f"    Ix={b['Ix']:.2f}  Iy={b['Iy']:.2f}  Ix/Iy={ratio:.3f}")
        print(f"    cost={b['cost']}  efficiency={b['efficiency']:.4f}")
    else:
        print("  코어: 유효 단면 없음")

    print("\n완료!")


if __name__ == '__main__':
    main()
