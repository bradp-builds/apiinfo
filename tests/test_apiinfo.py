"""Local integration fixtures; Python standard library only."""
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPT = Path(__file__).resolve().parents[1] / 'apiinfo'


class Handler(BaseHTTPRequestHandler):
    requests = []
    user_agents = []

    def log_message(self, *_args):
        pass

    def do_HEAD(self):
        self.respond(head=True)

    def do_OPTIONS(self):
        self.respond()

    def do_GET(self):
        self.respond()

    def respond(self, head=False):
        self.requests.append((self.command, self.path))
        self.user_agents.append(self.headers.get("User-Agent"))
        status, body, content_type = 200, b'{"users":[{"id":1,"name":"Ada"}],"next":null}', 'application/json'
        extra = {}
        if self.path == '/invalid':
            body = b'{broken'
        elif self.path == '/array':
            body = json.dumps({'namespaces': [f'namespace-{i}' for i in range(7)]}).encode()
        elif self.path == '/credentials':
            status, extra['Location'] = 302, 'http://user:private-password@localhost:1/private'
        elif self.path == '/null':
            body = b'null'
        elif self.path == '/stream':
            body = b'{} {}'
        elif self.path == '/large':
            body = b'"' + b'a' * (2 * 1024 * 1024) + b'"'
        elif self.path == '/redirect':
            status, extra['Location'] = 302, '/json'
        elif self.path == '/foreign':
            status, extra['Location'] = 302, 'http://localhost:1/private?secret=hidden'
        elif self.path == '/loop':
            status, extra['Location'] = 302, '/loop'
        elif self.path == '/error':
            status = 500
        elif self.path == '/methods' and self.command != 'GET':
            status = 405
        elif self.path == '/text':
            content_type, body = 'text/html', b'<p>Hello\x1b[31m world</p>'
        elif self.path == '/html':
            content_type = 'text/html; charset=utf-8'
            body = b"""<!doctype html><HTML><HEAD>
                <!-- <meta name=generator content=COMMENT-FAKE> -->
                <script>const fake = '<meta name=generator content=SCRIPT-FAKE>';</script>
                <style>/* <link rel='https://api.w.org/' href='/style-fake'> */</style>
                <TITLE>A &amp; B</TITLE>
                <META CONTENT='Example CMS 1.0'
 NAME=GENERATOR>
                <LINK HREF='/api?token=private-html-token' REL='https://api.w.org/'>
                <link type=application/problem+json rel='other alternate' href='/resource.json'>
                <link rel=stylesheet href='/style.css'>
                <link rel='https://api.w.org/' href='//user:private-html-pass@example.com/api'>
                <link rel='https://api.w.org/' href='javascript:private-script'>
                </HEAD><body>Example</body></HTML>"""
        elif self.path == '/html-limit':
            content_type = 'text/html'
            body = b' ' * 65536 + b'<meta name=generator content=OUTSIDE-SCAN>'
        elif self.path == '/html-many':
            content_type = 'text/html'
            body = (b'<meta name="generator" content="Example > CMS">' +
                    b''.join(f'<link rel="https://api.w.org/" href="/api/{i}">'.encode() for i in range(30)))
        elif self.path == '/html-minimal':
            content_type, body = 'text/html', b'<html><meta charset=utf-8><meta name=description content=test></html>'
        elif self.path == '/html-raw':
            content_type, body = 'text/html', b"<textarea><meta name=generator content=TEXTAREA-FAKE></textarea><script>unclosed <meta name=generator content=UNCLOSED-FAKE>"
        elif self.path == '/duplicate-links':
            content_type = 'text/html'
            body = b'<link rel="https://api.w.org/" href="/api"><link href="/api" rel="https://api.w.org/">'
            extra['Link'] = '</api>; rel="https://api.w.org/", </other-api>; rel="https://api.w.org/"'
        elif self.path == '/links':
            extra['Link'] = ('</api?token=private-header-token>; title="A, B"; rel="https://api.w.org/", '
                             '</resource>; type="application/json"; rel="alternate", '
                             '<https://user:private-header-pass@example.com/api>; rel="https://api.w.org/", '
                             '</style.css>; rel="stylesheet"')
        elif self.path == '/binary':
            content_type, body = 'application/octet-stream', bytes(range(256))
        elif self.path == '/slow':
            time.sleep(2)
        if self.command == 'OPTIONS':
            extra['Allow'] = 'GET, HEAD, OPTIONS'
            extra['Access-Control-Allow-Origin'] = '*'
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Set-Cookie', 'secret=do-not-print')
        for key, value in extra.items():
            self.send_header(key, value)
        self.end_headers()
        if not head:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def run_cli(self, path, *args):
        Handler.requests.clear()
        Handler.user_agents.clear()
        env = dict(os.environ, NO_PROXY='*', no_proxy='*')
        return subprocess.run([str(SCRIPT), '--no-color', *args, self.base + path],
                              capture_output=True, text=True, timeout=12, env=env)

    def test_json_and_methods(self):
        result = self.run_cli('/json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('$["users"]: array (1 elements)', result.stdout)
        self.assertIn('Ada', result.stdout)
        self.assertIn('GET, HEAD, OPTIONS', result.stdout)
        self.assertNotIn('do-not-print', result.stdout)
        self.assertEqual([m for m, _ in Handler.requests], ['GET', 'HEAD', 'OPTIONS'])
        version = subprocess.check_output([str(SCRIPT), '--version'], text=True).split()[1]
        self.assertEqual(Handler.user_agents, [f'apiinfo/{version}'] * 3)

    def test_verbose_arrays(self):
        normal = self.run_cli('/array')
        verbose = self.run_cli('/array', '--verbose')
        self.assertIn('additional elements omitted', normal.stdout)
        self.assertNotIn('namespace-6', normal.stdout)
        self.assertNotIn('additional elements omitted', verbose.stdout)
        self.assertIn('$["namespaces"][6]', verbose.stdout)
        self.assertIn('namespace-6', verbose.stdout)

    def test_redirect_credentials_hidden(self):
        result = self.run_cli('/credentials')
        self.assertIn('origin boundary', result.stdout)
        self.assertNotIn('private-password', result.stdout + result.stderr)
        self.assertEqual(len(Handler.requests), 3)

    def test_json_scalar_and_invalid(self):
        self.assertIn('$: null', self.run_cli('/null').stdout)
        for path in ['/invalid', '/stream']:
            self.assertIn('not one valid JSON value', self.run_cli(path).stdout)

    def test_redirects(self):
        result = self.run_cli('/redirect')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Ada', result.stdout)
        self.assertEqual(len(Handler.requests), 4)
        result = self.run_cli('/foreign')
        self.assertIn('origin boundary', result.stdout)
        self.assertNotIn('secret=hidden', result.stdout)
        self.assertEqual(len(Handler.requests), 3)
        result = self.run_cli('/loop')
        self.assertIn('redirect limit', result.stdout)
        self.assertEqual(len(Handler.requests), 6)

    def test_large_and_timeout(self):
        result = self.run_cli('/large')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Incomplete transfer', result.stdout)
        self.assertNotIn('not one valid JSON value', result.stdout)
        result = self.run_cli('/slow', '--timeout', '1')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Request timed out', result.stdout)

    def test_status_and_content(self):
        result = self.run_cli('/error')
        self.assertEqual(result.returncode, 0)
        self.assertIn('HTTP 500', result.stdout)
        self.assertIn('status codes differ', self.run_cli('/methods').stdout)
        result = self.run_cli('/text')
        self.assertIn('Hello', result.stdout)
        self.assertNotIn('\x1b', result.stdout)
        self.assertIn('Preview omitted', self.run_cli('/binary').stdout)

    def test_html_discovery(self):
        result = self.run_cli('/html')
        self.assertEqual(result.returncode, 0, result.stderr)
        structure = result.stdout.split('4. Response content structure')[1].split('5. Actual response preview')[0]
        self.assertIn('Title: A & B', structure)
        self.assertIn('Generator (self-reported): Example CMS 1.0', structure)
        self.assertIn('API root (HTML; advertised, unverified): /api?[query hidden]', structure)
        self.assertIn('Alternate JSON representation (HTML; advertised, unverified): /resource.json', structure)
        for hidden in ['COMMENT-FAKE', 'SCRIPT-FAKE', 'style-fake', 'private-html-token',
                       'private-html-pass', 'private-script', '/style.css']:
            self.assertNotIn(hidden, structure)
        self.assertEqual(len(Handler.requests), 3)
        self.assertEqual(self.run_cli('/html-minimal').returncode, 0)
        result = self.run_cli('/html-raw')
        structure = result.stdout.split('4. Response content structure')[1].split('5. Actual response preview')[0]
        self.assertNotIn('Generator (self-reported)', structure)

    def test_html_limits(self):
        result = self.run_cli('/html-limit')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('Generator (self-reported)', result.stdout)
        result = self.run_cli('/html-many')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Generator (self-reported): Example > CMS', result.stdout)
        self.assertEqual(result.stdout.count('API root (HTML; advertised, unverified)'), 10)
        self.assertEqual(len(Handler.requests), 3)

    def test_link_header_discovery(self):
        result = self.run_cli('/links')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('API root (GET Link header; advertised, unverified): /api?[query hidden]', result.stdout)
        self.assertIn('Alternate JSON representation (GET Link header', result.stdout)
        self.assertNotIn('HEAD Link header', result.stdout)
        self.assertNotIn('OPTIONS Link header', result.stdout)
        self.assertEqual(result.stdout.count('API root (GET Link header'), 2)
        self.assertNotIn('private-header-token', result.stdout)
        self.assertNotIn('private-header-pass', result.stdout)
        self.assertEqual(len(Handler.requests), 3)

    def test_duplicate_discovery_links(self):
        result = self.run_cli('/duplicate-links')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count('API root ('), 2)
        self.assertIn('API root (HTML; advertised, unverified): /api\n', result.stdout)
        self.assertIn('API root (GET Link header; advertised, unverified): /other-api', result.stdout)
        self.assertEqual(len(Handler.requests), 3)

    def test_usage(self):
        for args in [[], ['--timeout'], ['--timeout', '0', self.base],
                     ['http://user:password@localhost/'], ['file:///etc/passwd']]:
            result = subprocess.run([str(SCRIPT), *args], capture_output=True)
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
