"""Standard-library HTTP interface for the in-memory URL shortener."""

import argparse
import html
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib.parse import parse_qsl, unquote, urlsplit

from src.hash_table import HashTable
from src.linear_probing import LinearProbingHashTable
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


def _form_page(
    message: str = "",
    selected_strategy: str = "chaining",
    selectable: bool = False,
) -> str:
    notice = f'<p role="status">{html.escape(message)}</p>' if message else ""
    strategy_control = ""
    if selectable:
        chaining_selected = " selected" if selected_strategy == "chaining" else ""
        linear_selected = " selected" if selected_strategy == "linear" else ""
        strategy_control = f"""<label for="strategy">해시 방식</label><br>
<select id="strategy" name="strategy">
  <option value="chaining"{chaining_selected}>개별 체이닝 (기본)</option>
  <option value="linear"{linear_selected}>선형 탐지</option>
</select><br>"""
    content = f"""{notice}
<form action="/shorten" method="post">
  {strategy_control}
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


def _table_page(
    shortener: Shortener,
    include_linear: bool = True,
    strategy_selector: bool = False,
    selected_strategy: str = "chaining",
) -> str:
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
    if include_linear:
        _, linear_content = _linear_table_view(shortener)
        linear_content = f'<p><a href="/linear">선형 탐지 표만 새 페이지에서 보기</a></p>{linear_content}'
    elif strategy_selector:
        linear_content = _table_strategy_links(selected_strategy)
    else:
        linear_content = ""
    content = f"""<p>버킷 수: {shortener.table.capacity} · 저장된 URL: {len(shortener.table)}</p>
<table>
  <thead><tr><th scope="col">버킷</th><th scope="col">연결 리스트 (앞에서 뒤로)</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>
{linear_content}"""
    return _page("현재 해시 테이블", content)


def _linear_table_view(shortener: Shortener) -> tuple[LinearProbingHashTable[str], str]:
    items = shortener.table.items()
    capacity = max(shortener.table.capacity, len(items), 1)
    table = LinearProbingHashTable[str](capacity=capacity)
    for key, code in items:
        table[key] = code

    rows = []
    for index, bucket in enumerate(table.buckets()):
        if not bucket:
            cell = '<span class="muted">(비어 있음)</span>'
        else:
            key, code = bucket[0]
            accumulators, start = table.hash_calculation(key)
            trace = table.probe_trace(key)
            steps = []
            previous = 0
            for position, (character, accumulator) in enumerate(
                zip(key, accumulators), start=1
            ):
                steps.append(
                    "<li><code>"
                    f"h{position} = 31 × {previous} + ord({html.escape(repr(character))}) "
                    f"= {accumulator}"
                    "</code></li>"
                )
                previous = accumulator
            if not steps:
                steps.append("<li>빈 문자열이므로 해시값은 0입니다.</li>")
            inspected = " &rarr; ".join(str(slot) for slot in trace)
            cell = f"""<div class="chain-node">
  <div><strong>URL 키</strong>: <code>{html.escape(key)}</code></div>
  <div><strong>짧은 코드</strong>: <code>{html.escape(code)}</code></div>
  <div><strong>짧은 링크</strong>: <a href="/{html.escape(code)}">/{html.escape(code)}</a></div>
  <details>
    <summary>Horner 해시와 탐지 경로 보기</summary>
    <ol>{''.join(steps)}</ol>
    <p>시작 칸: 해시값 {previous} % 버킷 수 {table.capacity} = {start}</p>
    <p>조회 시 확인한 칸: {inspected}</p>
    <p>이 키는 칸 {index}에서 발견됩니다.</p>
  </details>
</div>"""
        rows.append(
            f'<tr><th class="bucket" scope="row">{index}</th>'
            f'<td class="bucket">{cell}</td></tr>'
        )

    content = f"""<section>
  <h2>선형 탐지 테이블</h2>
  <p>칸 수: {table.capacity} · 저장된 URL: {len(table)}</p>
  <table>
    <thead><tr><th scope="col">칸</th><th scope="col">저장 내용과 탐색 근거</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</section>"""
    return table, content


def _table_strategy_links(selected_strategy: str) -> str:
    chaining_label = "개별 체이닝"
    linear_label = "선형 탐지"
    if selected_strategy == "chaining":
        chaining_label = f"<strong>{chaining_label}</strong>"
    else:
        linear_label = f"<strong>{linear_label}</strong>"
    return (
        '<p>표 방식: '
        f'<a href="/table?strategy=chaining">{chaining_label}</a> · '
        f'<a href="/table?strategy=linear">{linear_label}</a></p>'
    )


def _linear_table_page(
    shortener: Shortener,
    strategy_selector: bool = False,
) -> str:
    _, content = _linear_table_view(shortener)
    links = (
        _table_strategy_links("linear")
        if strategy_selector
        else '<p><a href="/table">체이닝 표와 함께 보기</a></p>'
    )
    return _page("선형 탐지 테이블", f"{links}{content}")


class ShortenerServer(ThreadingHTTPServer):
    """HTTP server that keeps its shortener instances for its lifetime."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        shortener: Shortener | None = None,
        strategy: str | None = None,
    ):
        if strategy is None:
            strategy = (
                "linear"
                if shortener is not None
                and isinstance(shortener.table, LinearProbingHashTable)
                else "chaining"
            )
        if strategy not in ("chaining", "linear", "selectable"):
            raise ValueError(f"unknown hash table strategy: {strategy}")
        self.strategy = strategy
        self.shortener_lock = Lock()

        if strategy == "selectable":
            capacity = (
                shortener.table.capacity
                if shortener is not None
                else _DEFAULT_TABLE_CAPACITY
            )
            self.chaining_shortener = Shortener(
                table_type=HashTable,
                table_capacity=capacity,
            )
            self.linear_shortener = Shortener(
                table_type=LinearProbingHashTable,
                table_capacity=capacity,
            )
            self.shortener = self.chaining_shortener
        else:
            self.shortener = (
                shortener if shortener is not None else _make_shortener(strategy)
            )
            self.chaining_shortener = (
                self.shortener if strategy == "chaining" else None
            )
            self.linear_shortener = (
                self.shortener if strategy == "linear" else None
            )
        super().__init__(address, ShortenerRequestHandler)

    def shortener_for(self, strategy: str) -> Shortener:
        if strategy == "chaining" and self.chaining_shortener is not None:
            return self.chaining_shortener
        if strategy == "linear" and self.linear_shortener is not None:
            return self.linear_shortener
        raise ValueError(f"hash table strategy is unavailable: {strategy}")


class ShortenerRequestHandler(BaseHTTPRequestHandler):
    server: ShortenerServer

    def _send_html(self, status: int, document: str) -> None:
        body = document.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_form_page(
        self,
        status: int,
        message: str = "",
        selected_strategy: str = "chaining",
    ) -> None:
        self._send_html(
            status,
            _form_page(
                message,
                selected_strategy,
                self.server.strategy == "selectable",
            ),
        )

    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path == "/":
            self._send_html(
                200,
                _form_page(selectable=self.server.strategy == "selectable"),
            )
            return
        if path == "/table":
            strategies = [
                value
                for name, value in parse_qsl(urlsplit(self.path).query)
                if name == "strategy"
            ]
            if self.server.strategy == "selectable" and (
                len(strategies) > 1
                or (strategies and strategies[0] not in ("chaining", "linear"))
            ):
                self._send_html(
                    400,
                    _page("잘못된 방식", "<p>표 방식을 선택해 주세요.</p>"),
                )
                return
            with self.server.shortener_lock:
                if self.server.strategy == "selectable":
                    selected_strategy = strategies[0] if strategies else "chaining"
                    shortener = self.server.shortener_for(selected_strategy)
                    if selected_strategy == "linear":
                        document = _linear_table_page(
                            shortener,
                            strategy_selector=True,
                        )
                    else:
                        document = _table_page(
                            shortener,
                            include_linear=False,
                            strategy_selector=True,
                            selected_strategy=selected_strategy,
                        )
                elif isinstance(self.server.shortener.table, LinearProbingHashTable):
                    document = _linear_table_page(self.server.shortener)
                else:
                    document = _table_page(self.server.shortener)
            self._send_html(200, document)
            return
        if path == "/linear":
            with self.server.shortener_lock:
                linear_shortener = (
                    self.server.shortener_for("linear")
                    if self.server.strategy == "selectable"
                    else self.server.shortener
                )
                document = _linear_table_page(
                    linear_shortener,
                    strategy_selector=self.server.strategy == "selectable",
                )
            self._send_html(200, document)
            return

        code = path.removeprefix("/")
        if not code or "/" in code:
            self._send_html(404, _page("페이지를 찾을 수 없습니다", "<p>요청한 페이지가 없습니다.</p>"))
            return
        try:
            with self.server.shortener_lock:
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
            self._send_form_page(400, "요청 본문 길이가 올바르지 않습니다.")
            return
        if content_length < 0:
            self._send_form_page(400, "요청 본문 길이가 올바르지 않습니다.")
            return
        if content_length > _MAX_FORM_BYTES:
            self._send_form_page(413, "요청이 너무 큽니다.")
            return

        try:
            fields = parse_qsl(
                self.rfile.read(content_length).decode("utf-8"),
                keep_blank_values=True,
            )
        except (UnicodeDecodeError, ValueError):
            self._send_form_page(400, "폼 데이터가 올바르지 않습니다.")
            return

        if self.server.strategy == "selectable":
            strategies = [value for name, value in fields if name == "strategy"]
            if len(strategies) != 1 or strategies[0] not in ("chaining", "linear"):
                self._send_form_page(
                    400,
                    "해시 방식을 하나 선택해 주세요.",
                )
                return
            selected_strategy = strategies[0]
            shortener = self.server.shortener_for(selected_strategy)
        else:
            selected_strategy = self.server.strategy
            shortener = self.server.shortener

        urls = [value for name, value in fields if name == "url"]
        if len(urls) != 1:
            self._send_form_page(
                400,
                "URL을 하나 입력해 주세요.",
                selected_strategy,
            )
            return
        url = urls[0].strip()
        if url:
            parsed_url = urlsplit(url)
            if not parsed_url.scheme or "." in parsed_url.scheme or parsed_url.scheme == "localhost":
                url = f"https://{url.lstrip('/')}"
        try:
            normalized_url = Shortener._normalize_url(url)
            with self.server.shortener_lock:
                if self.server.strategy == "selectable":
                    linear_shortener = self.server.shortener_for("linear")
                    if (
                        normalized_url not in linear_shortener.table
                        and len(linear_shortener.table)
                        >= linear_shortener.table.capacity
                    ):
                        self._send_form_page(
                            507,
                            "선형 탐지 테이블이 가득 찼습니다.",
                            selected_strategy,
                        )
                        return

                code = shortener.shorten(normalized_url)
                if self.server.strategy == "selectable":
                    mirror_strategy = (
                        "linear" if selected_strategy == "chaining" else "chaining"
                    )
                    mirror_code = self.server.shortener_for(mirror_strategy).shorten(
                        normalized_url
                    )
                    if mirror_code != code:
                        raise RuntimeError("hash table code sequences diverged")
        except ValueError as error:
            self._send_form_page(400, str(error), selected_strategy)
            return
        except OverflowError:
            self._send_form_page(
                507,
                "선형 탐지 테이블이 가득 찼습니다.",
                selected_strategy,
            )
            return

        short_path = f"/{html.escape(code)}"
        original_url = html.escape(shortener.expand(code), quote=True)
        strategy_label = "선형 탐지" if selected_strategy == "linear" else "개별 체이닝"
        table_url = (
            f"/table?strategy={selected_strategy}"
            if self.server.strategy == "selectable"
            else "/table"
        )
        content = f"""<p>선택한 방식: {strategy_label}</p>
<p>짧은 링크가 준비되었습니다.</p>
<p>짧은 링크: <a id="short-link" href="{short_path}">{short_path}</a></p>
<script>
  const shortLink = document.getElementById("short-link");
  shortLink.textContent = new URL(shortLink.href, window.location.origin).href;
</script>
<p>원래 주소: <a href="{original_url}" target="_blank" rel="noopener noreferrer">{original_url}</a></p>
<p><a href="{table_url}">선택한 방식의 테이블 보기</a></p>
<p><a href="/">다른 URL 줄이기</a></p>"""
        self._send_html(200, _page("짧은 링크", content))


def _make_shortener(strategy: str) -> Shortener:
    if strategy == "linear":
        return Shortener(
            table_type=LinearProbingHashTable,
            table_capacity=_DEFAULT_TABLE_CAPACITY,
        )
    if strategy == "chaining":
        return Shortener(table_capacity=_DEFAULT_TABLE_CAPACITY)
    raise ValueError(f"unknown hash table strategy: {strategy}")


def main() -> None:
    parser = argparse.ArgumentParser(description="URL 단축기 웹 서버")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="서버 포트 (기본값: PORT 환경 변수 또는 8000)",
    )
    parser.add_argument(
        "--strategy",
        choices=("chaining", "linear", "selectable"),
        default="chaining",
        help="해시 테이블 방식 (chaining, linear, selectable)",
    )
    args = parser.parse_args()

    if args.strategy == "selectable":
        server = ShortenerServer(("0.0.0.0", args.port), strategy="selectable")
    else:
        server = ShortenerServer(
            ("0.0.0.0", args.port),
            _make_shortener(args.strategy),
            strategy=args.strategy,
        )
    print(f"URL 단축기 실행 중: http://0.0.0.0:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
