# 🎄 ASCII Christmas Tree

문자 3,000개로 만든, 회전하는 3D 크리스마스 트리.

<p align="center">
  <img src="assets/demo.gif" alt="demo" width="432">
</p>

## Getting Started

```bash
pip install pillow numpy imageio-ffmpeg

python christmas_tree.py                    # 실시간 미리보기 창
python christmas_tree.py --save tree.mp4    # mp4로 저장
python christmas_tree.py --save tree.gif    # gif로 저장
```

| 옵션 | 설명 | 기본값 |
|---|---|---|
| `--save PATH` | `.mp4` / `.gif`로 저장 | 미리보기 |
| `--dur SEC` | 저장 길이(초) | `12` |
| `--scale X` | 출력 배율 | 미리보기 `0.6`, 저장 `1.0` |
| `--workers N` | 렌더 프로세스 수 | 코어 수 − 1 |

## How it works

- **잎** — 원뿔 표면 근처에 점 3,000개를 흩뿌리고 각 점에 `# @ % & * o x W M v ^` 같은 문자를 하나씩 배정
- **회전** — 매 프레임 `φ + rot`로 3D 좌표를 계산하고, z(깊이) 순으로 정렬해 뒤에서 앞으로 그림 (painter's algorithm). 앞쪽일수록 밝고 크게
- **갈런드** — 높이에 따라 각도가 증가하는 나선. 트리 뒤쪽으로 돌아간 부분은 숨김
- **전구 / 별** — 별도 레이어에 그린 뒤 가우시안 블러로 빛 번짐(bloom) 합성
- **병렬 렌더** — 각 프레임은 시간 `t`만의 함수라 서로 독립. 여러 프로세스가 앞 프레임을 미리 그려두고 메인은 순서대로 30fps로 표시만 함
- **연출** — 잎이 위에서부터 자라남 → 별 → 전구 → 갈런드 → 선물 상자 → `MERRY CHRISTMAS` 타이핑

## Customization

`christmas_tree.py` 상단 상수만 바꾸면 됨.

```python
N_LEAF = 3000      # 문자 수
N_LIGHT = 97       # 전구 수
GAR_TURNS = 5.5    # 갈런드 감기는 횟수
SPIN = 0.55        # 회전 속도 (rad/s)
TIERS = 6          # 가지 층 수
```
