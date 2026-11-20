"""Standard-library HTTP interface for the in-memory URL shortener."""

import argparse
import html
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, unquote, urlsplit

from src.hash_table import HashTable
from src.shortener import Shortener

_DEFAULT_TABLE_CAPACITY = 10
_MAX_FORM_BYTES = 1_048_576


def _page(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font: 1rem/1.6 system-ui, sans-serif; margin: 2rem auto; max-width: 60rem; padding: 0 1rem; }}
    input[type=text] {{ box-sizing: border-box; max-width: 38rem; padding: .6rem; width: 100%; }}
    button {{ cursor: pointer; margin-top: .6rem; padding: .55rem 1rem; }}
    code {{ overflow-wrap: anywhere; }}
    .chain {{ align-items: flex-start; display: flex; flex-wrap: wrap; gap: .75rem; }}
    .chain-node {{ border: 1px solid #bbb; border-radius: .4rem; max-width: 32rem; padding: .75rem; }}
    .arrow {{ align-self: center; font-size: 1.4rem; }}
    .bucket {{ border-bottom: 1px solid #ddd; padding: .75rem 0; text-align: left; vertical-align: top; }}
    .muted {{ color: #555; }}
  </style>
</head>
<body>
  <header><a href="/">URL 단축기</a> · <a href="/table">해시 테이블</a></header>
  <main>
    <h1>{html.escape(title)}</h1>
    {content}
  </main>
</body>
</html>"""


def _form_page(message: str = "") -> str:
    notice = f'<p role="status">{html.escape(message)}</p>' if message else ""
    content = f"""{notice}
<form action="/shorten" method="post">
  <label for="url">줄일 URL</label><br>
  <input id="url" name="url" type="text" placeholder="https://example.com 또는 example.com" required>
  <p class="muted">http:// 또는 https://를 생략하면 https://를 붙입니다.</p>
  <br><button type="submit">줄이기</button>
</form>"""
    return _page("URL 단축기", content)


def _hash_details(key: str, code: str, table: HashTable[str]) -> str:
    accumulators, bucket_index = table.hash_calculation(key)
    steps = []
    previous = 0
    for position, (character, accumulator) in enumerate(zip(key, accumulators), start=1):
        steps.append(
            "<li><code>"
            f"h{position} = 31 × {previous} + ord({html.escape(repr(character))}) "
            f"= 31 × {previous} + {ord(character)} = {accumulator}"
            "</code></li>"
        )
        previous = accumulator
    if not steps:
        steps.append("<li>빈 문자열이므로 해시값은 0입니다.</li>")

    return f"""<div class="chain-node">
  <div><strong>URL 키</strong>: <code>{html.escape(key)}</code></div>
  <div><strong>짧은 코드</strong>: <code>{html.escape(code)}</code></div>
  <div><strong>짧은 링크</strong>: <a href="/{html.escape(code)}">/{html.escape(code)}</a></div>
  <details>
    <summary>Horner 해시 계산 보기</summary>
    <ol>{''.join(steps)}</ol>
    <p>최종 해시값 {previous} % 버킷 수 {table.capacity} = 버킷 인덱스 {bucket_index}</p>
  </details>
</div>"""


def _table_page(shortener: Shortener) -> str:
    rows = []
    for index, bucket in enumerate(shortener.table.buckets()):
        nodes = []
        for node_index, (key, code) in enumerate(bucket):
            if node_index:
                nodes.append('<span class="arrow" aria-hidden="true">&rarr;</span>')
            nodes.append(_hash_details(key, code, shortener.table))
        chain = '<div class="chain">' + (
            "".join(nodes) if nodes else '<span class="muted">(비어 있음)</span>'
        ) + "</div>"
        rows.append(
            f'<tr><th class="bucket" scope="row">{index}</th>'
            f'<td class="bucket">{chain}</td></tr>'
        )
    content = f"""<p>버킷 수: {shortener.table.capacity} · 저장된 URL: {len(shortener.table)}</p>
<table>
  <thead><tr><th scope="col">버킷</th><th scope="col">연결 리스트 (앞에서 뒤로)</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>"""
    return _page("현재 해시 테이블", content)


class ShortenerServer(ThreadingHTTPServer):
    """HTTP server that keeps one shortener instance for its lifetime."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], shortener: Shortener | None = None):
        self.shortener = (
            shortener
            if shortener is not None
            else Shortener(table_capacity=_DEFAULT_TABLE_CAPACITY)
        )
        super().__init__(address, ShortenerRequestHandler)


class ShortenerRequestHandler(BaseHTTPRequestHandler):
    server: ShortenerServer

    def _send_html(self, status: int, document: str) -> None:
        body = document.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path == "/":
            self._send_html(200, _form_page())
            return
        if path == "/table":
            self._send_html(200, _table_page(self.server.shortener))
            return

        code = path.removeprefix("/")
        if not code or "/" in code:
            self._send_html(404, _page("페이지를 찾을 수 없습니다", "<p>요청한 페이지가 없습니다.</p>"))
            return
        try:
            url = self.server.shortener.expand(code)
        except KeyError:
            self._send_html(404, _page("링크를 찾을 수 없습니다", "<p>등록되지 않은 짧은 링크입니다.</p>"))
            return

        self.send_response(302)
        self.send_header("Location", url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/shorten":
            self._send_html(404, _page("페이지를 찾을 수 없습니다", "<p>요청한 페이지가 없습니다.</p>"))
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_html(400, _form_page("요청 본문 길이가 올바르지 않습니다."))
            return
        if content_length < 0:
            self._send_html(400, _form_page("요청 본문 길이가 올바르지 않습니다."))
            return
        if content_length > _MAX_FORM_BYTES:
            self._send_html(413, _form_page("요청이 너무 큽니다."))
            return

        try:
            fields = parse_qsl(
                self.rfile.read(content_length).decode("utf-8"),
                keep_blank_values=True,
            )
        except (UnicodeDecodeError, ValueError):
            self._send_html(400, _form_page("폼 데이터가 올바르지 않습니다."))
            return

        urls = [value for name, value in fields if name == "url"]
        if len(urls) != 1:
            self._send_html(400, _form_page("URL을 하나 입력해 주세요."))
            return
        url = urls[0].strip()
        if url:
            parsed_url = urlsplit(url)
            if not parsed_url.scheme or "." in parsed_url.scheme or parsed_url.scheme == "localhost":
                url = f"https://{url.lstrip('/')}"
        try:
            code = self.server.shortener.shorten(url)
        except ValueError as error:
            self._send_html(400, _form_page(str(error)))
            return

        short_path = f"/{html.escape(code)}"
        original_url = html.escape(self.server.shortener.expand(code), quote=True)
        content = f"""<p>짧은 링크가 준비되었습니다.</p>
<p>짧은 링크: <a id="short-link" href="{short_path}">{short_path}</a></p>
<script>
  const shortLink = document.getElementById("short-link");
  shortLink.textContent = new URL(shortLink.href, window.location.origin).href;
</script>
<p>원래 주소: <a href="{original_url}" target="_blank" rel="noopener noreferrer">{original_url}</a></p>
<p><a href="/">다른 URL 줄이기</a></p>"""
        self._send_html(200, _page("짧은 링크", content))


def main() -> None:
    parser = argparse.ArgumentParser(description="URL 단축기 웹 서버")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="서버 포트 (기본값: PORT 환경 변수 또는 8000)",
    )
    args = parser.parse_args()

    server = ShortenerServer(("0.0.0.0", args.port))
    print(f"URL 단축기 실행 중: http://0.0.0.0:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
