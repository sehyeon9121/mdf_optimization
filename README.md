# MDF Strip 단면 최적화

4층 구조물의 기둥 및 코어 단면을 MDF Strip으로 구성하고,  
유전알고리즘으로 최적 단면 후보를 탐색합니다.

## 파일 구조

```
mdf_optimization/
├── config.yaml           # 스트립 규격, 격자 크기, GA 파라미터
├── materials.py          # MDFStrip 클래스, load_config
├── section_geometry.py   # 연결성 검사, 좌표 변환, 시각화
├── section_properties.py # 단면적 A, 도심, Ix, Iy, 비용 계산
├── section_filter.py     # 연결성 / Ix-Iy 비율 필터링
├── ga_section.py         # 유전알고리즘 최적화
├── postprocess.py        # CSV 저장, 이미지 저장
├── main.py               # 실행 진입점
└── outputs/              # (자동 생성)
    ├── generated_sections.csv
    ├── top_column_sections.csv
    ├── top_core_sections.csv
    └── images/
        ├── column/
        └── core/
```

## 설치 및 실행

```bash
pip install numpy pandas matplotlib pyyaml
python main.py
```

## 격자 인코딩

| 값 | 의미 |
|----|------|
| 0  | 빈 공간 |
| 1  | MDF Strip 기본 방향 (x-폭 4mm, y-높이 6mm) |
| 2  | MDF Strip 90도 회전 (x-폭 6mm, y-높이 4mm) |

## 단면 성능 지표

| 지표 | 설명 |
|------|------|
| A | 단면적 (mm²) |
| cx, cy | 도심 좌표 (mm) |
| Ix | x축 단면 2차 모멘트 (mm⁴) |
| Iy | y축 단면 2차 모멘트 (mm⁴) |
| cost | 스트립 총 비용 (개수 × 10) |
| efficiency | min(Ix, Iy) / cost |

## 필터 조건

- **기둥**: Ix/Iy 비율 0.7 ~ 1.3 (등방성에 가까운 단면)
- **코어**: Ix/Iy 비율 0.5 ~ 2.0 (방향성 허용)
- 공통: 모든 스트립이 4-연결로 이어진 단일 형상

## OpenSeesPy 연동 준비

`outputs/` CSV의 `grid` 컬럼은 2D 리스트 문자열로 저장되어 있습니다.

```python
import ast
grid = ast.literal_eval(row['grid'])  # 복원
```

각 후보의 `name, grid, strip_count, A, Ix, Iy, cost, efficiency`를  
그대로 OpenSeesPy 단면 정의에 연결할 수 있습니다.
