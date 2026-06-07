from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("xhs-storage-state.json")
    target.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")
        print("请在打开的浏览器里完成小红书登录，然后回到终端按回车保存登录态。")
        input()
        context.storage_state(path=str(target))
        browser.close()

    print(f"已保存登录态到: {target.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
