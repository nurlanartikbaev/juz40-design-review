#!/usr/bin/env python3
"""Снимает дев для дизайн-ревью: скрины, значения стилей и парные фрагменты.

Команды:
  setup                          установить зависимости
  login URL                      открыть окно для входа и сохранить сессию
  capture URL --out DIR --name N снять страницу и значения стилей
  pair DESIGN DEV --out DIR      нарезать макет и дев на парные фрагменты

Каждая команда печатает JSON в stdout.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

HOME = Path(os.environ.get("JUZ40_REVIEW_HOME", Path.home() / ".juz40-design-review"))
VENV = HOME / "venv"
VENV_PYTHON = VENV / "bin" / "python"
SESSIONS = HOME / "sessions"
REQUIREMENTS = ["playwright==1.49.1", "pillow==11.0.0"]
INSTALLED = HOME / "installed-requirements.txt"
LOGIN_PATH = re.compile(r"(^|/)(login|signin|sign-in|auth|sso)(/|\?|$)", re.I)
MAX_ELEMENTS = 2000

EXTRACT_JS = r"""
(maxElements) => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const cache = new Map();
  const toHex = (value) => {
    if (!value || value === 'none') return null;
    if (cache.has(value)) return cache.get(value);
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = '#000';
    ctx.fillStyle = value;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
    let result = null;
    if (a > 0) {
      result = '#' + [r, g, b].map((n) => n.toString(16).padStart(2, '0')).join('');
      if (a < 255) result += ' / ' + (a / 255).toFixed(2);
    }
    cache.set(value, result);
    return result;
  };
  const selector = (el) => {
    const parts = [];
    let node = el;
    while (node && node !== document.body && parts.length < 5) {
      const testId = node.getAttribute('data-testid');
      if (testId) { parts.unshift(`[data-testid="${testId}"]`); break; }
      if (node.id) { parts.unshift('#' + node.id); break; }
      const tag = node.tagName.toLowerCase();
      const same = node.parentElement
        ? [...node.parentElement.children].filter((c) => c.tagName === node.tagName)
        : [];
      parts.unshift(same.length > 1 ? `${tag}:nth-of-type(${same.indexOf(node) + 1})` : tag);
      // Путь начинается от ближайшего компонента Angular.
      if (tag.includes('-') && parts.length > 1) break;
      node = node.parentElement;
    }
    return parts.join(' > ');
  };
  const componentHosts = (el) => {
    const hosts = [];
    let node = el;
    while (node && node !== document.body && hosts.length < 3) {
      const tag = node.tagName.toLowerCase();
      if (tag.includes('-')) hosts.push(tag);
      node = node.parentElement;
    }
    return hosts;
  };
  const ANGULAR_STATE_CLASS = /^ng-(star-inserted|untouched|touched|pristine|dirty|valid|invalid|pending|submitted|animating|trigger(-.*)?|tns-.*)$/;
  const sides = (s, prop) => {
    const v = ['Top', 'Right', 'Bottom', 'Left'].map((d) => parseFloat(s[prop + d]) || 0);
    return v.some(Boolean) ? v : null;
  };
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'META', 'LINK', 'HEAD']);
  const MEDIA = new Set(['IMG', 'SVG', 'VIDEO', 'CANVAS', 'INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A']);
  const elements = [];
  let truncated = false;
  for (const el of document.querySelectorAll('body *')) {
    if (SKIP.has(el.tagName)) continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) continue;
    const text = [...el.childNodes]
      .filter((n) => n.nodeType === Node.TEXT_NODE)
      .map((n) => n.textContent.trim())
      .filter(Boolean)
      .join(' ');
    const bg = toHex(s.backgroundColor);
    const borderWidth = ['Top', 'Right', 'Bottom', 'Left'].map((d) => parseFloat(s[`border${d}Width`]) || 0);
    const hasBorder = borderWidth.some(Boolean);
    const radius = parseFloat(s.borderTopLeftRadius) || 0;
    const shadow = s.boxShadow !== 'none' ? s.boxShadow : null;
    const tag = el.tagName.toUpperCase();
    if (!text && !bg && !hasBorder && !radius && !shadow && !MEDIA.has(tag)) continue;
    if (elements.length >= maxElements) { truncated = true; break; }
    const item = {
      sel: selector(el),
      tag: tag.toLowerCase(),
      box: [r.left + scrollX, r.top + scrollY, r.width, r.height].map((n) => Math.round(n * 100) / 100),
    };
    const classes = [...el.classList].filter((c) => !ANGULAR_STATE_CLASS.test(c)).slice(0, 8).join(' ');
    if (classes) item.classes = classes;
    const components = componentHosts(el);
    if (components.length) item.components = components;
    if (el.closest('.cdk-overlay-container')) item.overlay = true;
    if (text) {
      item.text = text.slice(0, 160);
      item.font = {
        family: s.fontFamily.split(',')[0].replace(/["']/g, '').trim(),
        size: parseFloat(s.fontSize),
        weight: Number(s.fontWeight) || s.fontWeight,
        lineHeight: s.lineHeight === 'normal' ? 'normal' : parseFloat(s.lineHeight),
        letterSpacing: s.letterSpacing === 'normal' ? 0 : parseFloat(s.letterSpacing),
        color: toHex(s.color),
      };
      if (s.textTransform !== 'none') item.font.transform = s.textTransform;
      if (s.textAlign !== 'start') item.font.align = s.textAlign;
    }
    if (bg) item.bg = bg;
    if (hasBorder) item.border = { width: borderWidth, color: toHex(s.borderTopColor) };
    if (radius) item.radius = radius;
    if (shadow) item.shadow = shadow;
    const padding = sides(s, 'padding');
    if (padding) item.padding = padding;
    if (s.display.includes('flex') || s.display.includes('grid')) {
      item.layout = s.display;
      const gap = parseFloat(s.rowGap) || parseFloat(s.columnGap) || 0;
      if (gap) item.gap = gap;
    }
    if (parseFloat(s.opacity) < 1) item.opacity = parseFloat(s.opacity);
    if (tag === 'IMG') item.src = (el.currentSrc || el.src || '').slice(0, 200);
    if (el.disabled) item.disabled = true;
    elements.push(item);
  }
  const angularRoot = document.querySelector('[ng-version]');
  return {
    framework: angularRoot ? { name: 'angular', version: angularRoot.getAttribute('ng-version') } : null,
    page: {
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
      horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
    },
    truncated,
    elements,
  };
}
"""


def emit(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def fail(message, code=1, **extra):
    print(json.dumps({"error": message, **extra}, ensure_ascii=False, indent=2))
    sys.exit(code)


def ensure_venv(argv):
    """Перезапускает скрипт внутри окружения со всеми зависимостями."""
    if Path(sys.prefix).resolve() == VENV.resolve():
        return
    current = INSTALLED.read_text(encoding="utf-8") if INSTALLED.exists() else ""
    if not VENV_PYTHON.exists() or current != "\n".join(REQUIREMENTS):
        fail("Зависимости нужно установить или обновить. Запустите: python3 scripts/devshot.py setup")
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *argv])


def launch(playwright, headless=True):
    try:
        return playwright.chromium.launch(channel="chrome", headless=headless)
    except Exception:
        return playwright.chromium.launch(headless=headless)


def session_path(url):
    host = urlparse(url).netloc or "local"
    return SESSIONS / (re.sub(r"[^a-zA-Z0-9.-]", "_", host) + ".json")


def cmd_setup(_args):
    HOME.mkdir(parents=True, exist_ok=True)
    if not VENV_PYTHON.exists():
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *REQUIREMENTS],
        check=True,
    )
    probe = (
        "from playwright.sync_api import sync_playwright as s\n"
        "with s() as p:\n"
        "    p.chromium.launch(channel='chrome', headless=True).close()\n"
    )
    chrome = subprocess.run([str(VENV_PYTHON), "-c", probe], capture_output=True).returncode == 0
    if not chrome:
        subprocess.run([str(VENV_PYTHON), "-m", "playwright", "install", "chromium"], check=True)
    INSTALLED.write_text("\n".join(REQUIREMENTS), encoding="utf-8")
    emit({"ok": True, "browser": "chrome" if chrome else "chromium", "home": str(HOME)})


def cmd_login(args):
    from playwright.sync_api import Error, sync_playwright

    SESSIONS.mkdir(parents=True, exist_ok=True)
    os.chmod(SESSIONS, 0o700)
    target = session_path(args.url)
    temp = target.with_suffix(".tmp")
    saved = False
    with sync_playwright() as p:
        browser = launch(p, headless=False)
        context = browser.new_context(
            storage_state=str(target) if target.exists() else None,
            viewport=None,
        )
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        deadline = time.time() + args.timeout
        while time.time() < deadline and browser.is_connected() and context.pages:
            try:
                context.storage_state(path=str(temp))
                os.chmod(temp, 0o600)
                temp.replace(target)
                saved = True
                context.pages[0].wait_for_timeout(1500)
            except Error:
                break
        try:
            browser.close()
        except Error:
            pass
    if not saved:
        fail("Сессия не сохранена. Запустите вход ещё раз")
    emit({"ok": True, "session": str(target)})


def settle(page, timeout_ms):
    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 10000))
    except Exception:
        pass
    try:
        # Angular завершает отрисовку после загрузки данных.
        page.wait_for_function(
            "() => { const get = window.getAllAngularTestabilities;"
            " return !get || get().every((item) => item.isStable()); }",
            timeout=min(timeout_ms, 8000),
        )
    except Exception:
        pass
    page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")


def scroll_through(page):
    """Прокручивает страницу, чтобы загрузить ленивые изображения."""
    page.evaluate(
        """async () => {
          const step = Math.max(200, innerHeight - 100);
          for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
            scrollTo(0, y);
            await new Promise((r) => setTimeout(r, 120));
          }
          scrollTo(0, 0);
          await new Promise((r) => setTimeout(r, 200));
        }"""
    )


def cmd_capture(args):
    from playwright.sync_api import sync_playwright

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    png = out / f"{args.name}.png"
    data_file = out / f"{args.name}.json"
    session = session_path(args.url)

    with sync_playwright() as p:
        browser = launch(p)
        context = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=args.scale,
            storage_state=str(session) if session.exists() else None,
        )
        page = context.new_page()
        console_errors = []
        page.on("console", lambda m: console_errors.append(m.text[:300]) if m.type == "error" else None)
        response = page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
        settle(page, args.timeout * 1000)

        final = urlparse(page.url)
        requested = urlparse(args.url)
        # Angular с HashLocationStrategy хранит маршрут после символа #.
        on_login = LOGIN_PATH.search(final.path) or LOGIN_PATH.search(final.fragment)
        asked_login = LOGIN_PATH.search(requested.path) or LOGIN_PATH.search(requested.fragment)
        if on_login and not asked_login:
            browser.close()
            fail("Страница требует вход", code=3, needs_login=True, final_url=page.url)

        page.add_style_tag(
            content="*,*::before,*::after{transition:none!important;animation:none!important;"
            "caret-color:transparent!important}"
        )
        scroll_through(page)
        for selector in args.click:
            page.locator(selector).first.click(timeout=args.timeout * 1000)
            settle(page, 3000)
        for selector in args.hover:
            page.locator(selector).first.hover(timeout=args.timeout * 1000)
        if args.wait_for:
            page.locator(args.wait_for).first.wait_for(state="visible", timeout=args.timeout * 1000)
        page.wait_for_timeout(args.delay)

        data = page.evaluate(EXTRACT_JS, MAX_ELEMENTS)
        page.screenshot(
            path=str(png),
            full_page=True,
            animations="disabled",
            caret="hide",
        )
        data.update(
            {
                "url": page.url,
                "status": response.status if response else None,
                "viewport": {"width": args.width, "height": args.height, "scale": args.scale},
                "consoleErrors": console_errors[:20],
            }
        )
        data_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        browser.close()

    emit(
        {
            "ok": True,
            "png": str(png),
            "json": str(data_file),
            "status": data["status"],
            "framework": data["framework"],
            "page": data["page"],
            "elements": len(data["elements"]),
            "truncated": data["truncated"],
            "consoleErrors": len(data["consoleErrors"]),
        }
    )


def cmd_pair(args):
    from PIL import Image, ImageDraw

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    scale = args.scale
    gap = 16
    with Image.open(args.design) as d, Image.open(args.dev) as v:
        design = d.convert("RGB").resize((round(d.width / scale), round(d.height / scale)), Image.LANCZOS)
        dev = v.convert("RGB").resize((round(v.width / scale), round(v.height / scale)), Image.LANCZOS)
    width = max(design.width, dev.width)
    height = max(design.height, dev.height)
    columns = max(1, math.ceil(width / args.tile_width))
    tile_w = math.ceil(width / columns)
    step = max(1, args.tile_height - args.overlap)
    rows = max(1, math.ceil(max(height - args.overlap, 1) / step))
    tiles = []
    for row in range(rows):
        for column in range(columns):
            x, y = column * tile_w, row * step
            box = (x, y, x + tile_w, y + args.tile_height)
            canvas = Image.new("RGB", (tile_w * 2 + gap, args.tile_height), "#FF00FF")
            canvas.paste(design.crop(box), (0, 0))
            canvas.paste(dev.crop(box), (tile_w + gap, 0))
            ImageDraw.Draw(canvas).rectangle((tile_w, 0, tile_w + gap - 1, args.tile_height), fill="#111111")
            path = out / f"pair-{row + 1:02d}-{column + 1:02d}.png"
            canvas.save(path, "PNG", optimize=True)
            tiles.append({"file": str(path), "x": x, "y": y, "width": tile_w, "height": args.tile_height})
    emit(
        {
            "left": "макет",
            "right": "дев",
            "design": {"width": design.width, "height": design.height},
            "dev": {"width": dev.width, "height": dev.height},
            "tiles": tiles,
        }
    )


def build_parser():
    parser = argparse.ArgumentParser(description="Скрины и значения для дизайн-ревью")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("setup")

    login = commands.add_parser("login")
    login.add_argument("url")
    login.add_argument("--timeout", type=int, default=600)

    capture = commands.add_parser("capture")
    capture.add_argument("url")
    capture.add_argument("--out", required=True)
    capture.add_argument("--name", required=True)
    capture.add_argument("--width", type=int, default=1440)
    capture.add_argument("--height", type=int, default=900)
    capture.add_argument("--scale", type=int, default=2)
    capture.add_argument("--timeout", type=int, default=30)
    capture.add_argument("--delay", type=int, default=300)
    capture.add_argument("--wait-for")
    capture.add_argument("--click", action="append", default=[])
    capture.add_argument("--hover", action="append", default=[])

    pair = commands.add_parser("pair")
    pair.add_argument("design")
    pair.add_argument("dev")
    pair.add_argument("--out", required=True)
    pair.add_argument("--scale", type=float, default=2)
    pair.add_argument("--tile-width", type=int, default=760)
    pair.add_argument("--tile-height", type=int, default=800)
    pair.add_argument("--overlap", type=int, default=40)
    return parser


def main():
    argv = sys.argv[1:]
    args = build_parser().parse_args(argv)
    if args.command == "setup":
        cmd_setup(args)
        return
    ensure_venv(argv)
    {"login": cmd_login, "capture": cmd_capture, "pair": cmd_pair}[args.command](args)


if __name__ == "__main__":
    main()
