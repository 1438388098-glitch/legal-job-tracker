import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.collect.http import fetch  # noqa: E402


def main():
    url, out = sys.argv[1], Path(sys.argv[2])
    r = fetch(url)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    print(f"saved {len(r.content)} bytes -> {out}")


if __name__ == "__main__":
    main()
