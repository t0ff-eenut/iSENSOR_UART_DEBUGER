"""
MLP 학습 로그 분석 스크립트
사용법: python3 analyze_log.py <로그파일경로>
예시:  python3 analyze_log.py mlp_L64-32_b128_d2_ep1000_lr2e-3_lrp50_lrf5_f14_0508_012131.log
"""
import sys
import re

def analyze(filepath):
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    # 총 에폭 수 자동 감지
    max_ep = 0
    for line in lines:
        m = re.search(r'에폭\s+\d+/(\d+)', line)
        if m:
            max_ep = int(m.group(1))

    # target 에폭 집합 자동 생성 (약 12~15개 구간)
    if max_ep > 0:
        step = max(1, max_ep // 10)
        target = set(range(step, max_ep, step)) | {1, max_ep}
        # 최종 베스트 에폭만 추가 (마지막 ★ 줄)
        best_ep = None
        for line in lines:
            if '★' in line:
                ep = re.search(r'에폭\s+(\d+)/', line)
                if ep:
                    best_ep = int(ep.group(1))
        if best_ep:
            target.add(best_ep)
    else:
        target = set()

    # LR 감소 타임라인
    prev_lr = None
    print('=== LR 감소 타임라인 ===')
    for line in lines:
        m = re.search(r'lr: ([0-9e.+-]+)', line)
        ep = re.search(r'에폭\s+(\d+)/', line)
        if m and ep:
            lr = m.group(1)
            if lr != prev_lr:
                print(f'  ep{int(ep.group(1)):>4d}: {prev_lr} → {lr}')
                prev_lr = lr

    # 주요 에폭 진행 추이
    print()
    print(f'=== 주요 에폭 진행 추이 (총 {max_ep}에폭) ===')
    for line in lines:
        ep = re.search(r'에폭\s+(\d+)/', line)
        if ep and int(ep.group(1)) in target:
            print(' ', line.strip())

    # 최종 결과 요약
    print()
    print('=== 최종 결과 ===')
    for line in lines:
        if any(kw in line for kw in ['최고 검증 정확도', '학습 시간', '베이스라인 정확도']):
            print(' ', line.strip())


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python3 analyze_log.py <로그파일경로>")
        sys.exit(1)
    analyze(sys.argv[1])
