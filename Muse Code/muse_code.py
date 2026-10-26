import re
import shutil
import sys

import muse_api

CODE_BLOCK = re.compile(r"```[\w+-]*\n(.*?)```", re.S)


def extract_code(text: str) -> str:
    blocks = CODE_BLOCK.findall(text)
    return max(blocks, key=len).rstrip() + "\n" if blocks else text.strip() + "\n"


def ask(prompt: str) -> str:
    res = muse_api.generate(prompt)
    if not res.get("ok"):
        sys.exit(f"Lỗi: {res.get('error') or res.get('content')}")
    return res["content"]


def edit_file(path: str, instruction: str, inplace: bool = False) -> str:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    prompt = (
        f"### File: {path}\n```\n{src}\n```\n\nYêu cầu: {instruction}\n\n"
        "Trả về TOÀN BỘ nội dung mới của file trong một khối code duy nhất, "
        "không rút gọn, không giải thích bên ngoài khối code."
    )
    new_code = extract_code(ask(prompt))
    out = path
    if inplace:
        shutil.copyfile(path, path + ".bak")
    else:
        out = path + ".muse"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_code)
    return out


if __name__ == "__main__":
    # python muse_code.py main.py "Thêm type hints" [--inplace]
    print("Đã lưu:", edit_file(sys.argv[1], sys.argv[2], "--inplace" in sys.argv))
