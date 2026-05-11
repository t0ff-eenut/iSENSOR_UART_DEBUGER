"""기존 history JSON 마이그레이션:
  - loss → train_loss 키 리네임
  - lr 키 없는 경우 로그 파일 파싱으로 추가
"""
import os, json, re

BASE    = 'AI/mlp/models'
LOG_DIR = 'AI/mlp/logs'
LR_PAT  = re.compile(r'\|\s*lr:\s*([\d.e+\-]+)')

updated = 0
skipped = 0
for d in sorted(os.listdir(BASE)):
    if not d.startswith('MLP_'):
        continue
    hist_path = os.path.join(BASE, d, d + '_history.json')
    if not os.path.exists(hist_path):
        continue
    with open(hist_path, encoding='utf-8') as f:
        h = json.load(f)

    changed = False

    # ① loss → train_loss 리네임
    if 'loss' in h and 'train_loss' not in h:
        h['train_loss'] = h.pop('loss')
        changed = True
        print(f'  [RENAME] loss→train_loss: {d}')

    # ② lr 없으면 로그 파일 파싱
    if 'lr' not in h:
        log_path = os.path.join(LOG_DIR, d + '.log')
        if not os.path.exists(log_path):
            print(f'  [SKIP-no-log] {d}')
        else:
            lr_raw = []
            with open(log_path, encoding='utf-8') as lf:
                for line in lf:
                    m = LR_PAT.search(line)
                    if m:
                        lr_raw.append(round(float(m.group(1)), 10))
            ep_cnt = len(h['epochs'])
            if len(lr_raw) != ep_cnt:
                print(f'  [SKIP-mismatch] len(lr)={len(lr_raw)} vs ep={ep_cnt}: {d}')
            else:
                h['lr'] = lr_raw
                changed = True
                print(f'  [LR] {d}  ({len(lr_raw)}개)')

    if changed:
        with open(hist_path, 'w', encoding='utf-8') as f:
            json.dump(h, f, ensure_ascii=False)
        updated += 1
    else:
        skipped += 1

print(f'\n완료: {updated}개 업데이트, {skipped}개 건너뜀')
