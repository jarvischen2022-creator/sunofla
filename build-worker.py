#!/usr/bin/env python3
"""Rebuild the full sunofla worker JS from HTML sources in v2/ (Oct 9 production)."""
import re, glob, os

DIR = "/home/hatch/workspace/cloudflare-deploy/v2/"
OUT = "/tmp/sunofla-worker-restructure.js"

def minify(html):
    html = re.sub(r'<!--(?!\[if).*?-->', '', html, flags=re.S)
    html = re.sub(r'>\s+<', '><', html)
    html = re.sub(r'\s{2,}', ' ', html)
    html = re.sub(r'\n\s*', '', html)
    return html.strip()

def js_entry(route, content):
    esc = content.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
    return f"  '{route}': `{esc}`,\n"

route_map = {
 'index.html': '/',
 'workspace.html': '/workspace',
 'how-it-works.html': '/how-it-works',
 'solutions.html': '/solutions',
 'pilot-access.html': '/pilot-access',
 'onsite-it-how-it-works.html': '/onsite-it/how-it-works',
 'booking.html': '/booking',
 'industries.html': '/industries',
 'about.html': '/about',
 'terms.html': '/terms',
 'privacy.html': '/privacy',
}

entries = ""
for fn, route in route_map.items():
    p = DIR + fn
    assert os.path.exists(p), f"missing {fn}"
    entries += js_entry(route, minify(open(p).read()))

# shared css assets
import os as _os
import base64
# Oct 9 UI styles.css (primary for this build)
_old_css = DIR + "styles.css"
if _os.path.exists(_old_css):
    entries += js_entry('/styles.css', open(_old_css).read())
# assets-site.css (only if present, for newer pages)
_new_css = DIR + "assets-site.css"
if _os.path.exists(_new_css):
    entries += js_entry('/assets/site.css', open(_new_css).read())

# image assets (binary, base64 encoded)
def js_binary_entry(route, filepath, content_type):
    data = open(filepath, 'rb').read()
    b64 = base64.b64encode(data).decode('ascii')
    # Store as base64, decode at serve time
    return f"  '{route}': {{ b64: `{b64}`, ct: '{content_type}' }},\n"

_img_dir = DIR + "assets/"
for _fn, _ct in [('network.webp', 'image/webp'),
                 ('sunofla-ai-workspace-hero.webp', 'image/webp'),
                 ('card-practical-ai.webp', 'image/webp'),
                 ('card-studio-network.webp', 'image/webp'),
                 ('card-backup-recovery.webp', 'image/webp')]:
    _p = _img_dir + _fn
    if _os.path.exists(_p):
        entries += js_binary_entry('/assets/' + _fn, _p, _ct)

# sitemap
urls = [""] + [r for r in sorted(route_map.values()) if r != "/"]
sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + \
    "".join(f'  <url><loc>https://sunofla.com{u if u else "/"}</loc></url>\n' for u in urls) + '</urlset>\n'
entries += js_entry('/sitemap.xml', sitemap)

worker = """var PAGES = {
""" + entries + """};

addEventListener('fetch', function(event) {
  event.respondWith(handleRequest(event.request));
});
async function handleRequest(request) {
  var url = new URL(request.url);
  var path = url.pathname;
  if (path.length > 1 && path.endsWith('/')) path = path.slice(0, -1);
  if (path.endsWith('.html')) path = path.slice(0, -5);
  if (path === '/index') path = '/';
  var entry = PAGES[path];
  if (entry) {
    // Binary asset (base64)
    if (entry.b64) {
      var bin = atob(entry.b64);
      var bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      return new Response(bytes, { headers: { 'Content-Type': entry.ct, 'Cache-Control': 'public, max-age=86400' } });
    }
    // Text content
    var html = entry;
    var ct = path === '/sitemap.xml' ? 'application/xml; charset=utf-8' : (path === '/assets/site.css' ? 'text/css; charset=utf-8' : (path === '/styles.css' ? 'text/css; charset=utf-8' : 'text/html; charset=utf-8'));
    return new Response(html, { headers: { 'Content-Type': ct, 'Cache-Control': 'public, max-age=300' } });
  }
  return new Response('Not found', { status: 404 });
}
"""
open(OUT, "w").write(worker)
print("worker rebuilt:", len(worker), "bytes,", len(route_map) + 2, "routes")
