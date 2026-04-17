"""
convert_mermaid.py
------------------
model_architecture.md 안의 ```mermaid ... ``` 블록을
PNG 이미지로 변환하고, md 파일을 아래 형식으로 교체합니다:

  ![diagram_NN](images/diagram_NN.png)
  <!-- source: images/diagram_NN.mmd -->

되돌리려면 revert_to_mermaid.py 를 실행하세요.
"""

import re
import subprocess
import sys
from pathlib import Path

MD_FILE   = Path(__file__).parent / "model_architecture.md"
IMG_DIR   = Path(__file__).parent / "images"
MMDC_CMD  = Path(__file__).parent / "node_modules" / ".bin" / "mmdc.cmd"

IMG_DIR.mkdir(exist_ok=True)

with open(MD_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# blockquote(>) 안에 있는 경우도 포함해서 mermaid 블록 탐지
pattern = re.compile(
    r'([ \t]*(?:> *)*)```mermaid\n(.*?)```',
    re.DOTALL
)

blocks = list(pattern.finditer(content))
if not blocks:
    print("변환할 mermaid 블록이 없습니다.")
    sys.exit(0)

print(f"\nMermaid 블록 {len(blocks)}개 발견")

replacements = []  # (start, end, new_text)

for i, m in enumerate(blocks, 1):
    prefix      = m.group(1)   # blockquote prefix (있으면)
    diagram_src = m.group(2)

    name    = f"diagram_{i:02d}"
    mmd_path = IMG_DIR / f"{name}.mmd"
    png_path = IMG_DIR / f"{name}.png"

    # mmd 소스 저장
    clean_diagram = diagram_src.rstrip("\n")
    with open(mmd_path, "w", encoding="utf-8") as f:
        f.write(clean_diagram)

    print(f"  [{i}] 변환 중: {name} ... ", end="", flush=True)

    result = subprocess.run(
        [str(MMDC_CMD), "-i", str(mmd_path), "-o", str(png_path),
         "-b", "transparent"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"❌\n    오류: {result.stderr.strip()}")
        continue

    print("✅")

    # 교체할 텍스트 (prefix 유지)
    img_line      = f"{prefix}![{name}](images/{name}.png)"
    comment_line  = f"{prefix}<!-- source: images/{name}.mmd -->"
    new_text      = f"{img_line}\n{comment_line}"

    replacements.append((m.start(), m.end(), new_text))

# 뒤에서부터 교체해야 위치 어긋나지 않음
for start, end, new_text in reversed(replacements):
    content = content[:start] + new_text + content[end:]

with open(MD_FILE, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\n완료: {len(replacements)}개 블록 이미지로 교체됨 → {MD_FILE.name}")
