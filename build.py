import subprocess,re,html
from pathlib import Path
from bs4 import BeautifulSoup
p=Path(__file__).resolve().parent
DOCS=p/'platform/handbook/docs'

# The thematic docs/ set is the single Markdown source of truth; the monolithic
# handbook.md copies were removed. This script concatenates docs into one pandoc run.
def combined_markdown():
    parts=["""# Go Product Platform — руководство по архитектуре и разработке с ИИ {#top}

**Версия 15.0 · 20 ноября 2026 · Go-first · Модульный монолит · LOCAL-NATIVE / VM-first · Навыки агентов**

Канонический источник — тематические документы в `platform/handbook/docs/`; эта страница собирается из них командой `python3 build.py`.
"""]
    for f in sorted(DOCS.glob('[0-9][0-9]-*.md')):
        num=f.name[:2]
        text=f.read_text('utf-8')
        text=re.sub(r'\A---\n.*?\n---\n+','',text,flags=re.S)          # YAML frontmatter
        text=re.sub(r'\n(---\n+)?Навигация:.*\Z','\n',text,flags=re.S)   # prev/next footer
        # Cross-document links become in-page anchors of the combined HTML.
        text=re.sub(r'\]\((\d{2})-[a-z0-9-]+\.md(#[^)]*)?\)',
                    lambda m:'](%s)'%(m.group(2) or '#doc-'+m.group(1)),text)
        if not text.startswith('# '):
            raise RuntimeError(f'{f.name}: expected the document H1 title first')
        text=re.sub(r'\A(# [^\n{]*)',r'\1 {#doc-'+num+'}',text,count=1)
        parts.append(text.strip())
    return '\n\n'.join(parts)+'\n'

combined=combined_markdown()
body=subprocess.run(['pandoc','-f','markdown+raw_html+fenced_code_attributes','-t','html5','--no-highlight'],input=combined,text=True,capture_output=True,check=True).stdout
soup=BeautifulSoup(body,'html.parser')
heads=[]
for h in soup.find_all(['h2','h3']):
    anchor=h.get('id')
    if not anchor:
        anchor=re.sub(r'[^\w-]','-',h.get_text().lower()).strip('-');h['id']=anchor
    heads.append((h.name,anchor,h.get_text(' ',strip=True)))
nav='\n'.join(f'<a class="nav-link {"nav-sub" if lvl=="h3" else ""}" href="#{html.escape(a)}" data-search="{html.escape(label.lower())}">{html.escape(label)}</a>' for lvl,a,label in heads)
# All fenced code blocks are optional, collapsed by default.
for pre in soup.find_all('pre'):
    language=next((c for c in pre.get('class',[]) if c not in ('codeblock',)), 'text')
    pre['class']=pre.get('class',[])+['codeblock']
    details=soup.new_tag('details',attrs={'class':'code-accordion'})
    summary=soup.new_tag('summary')
    name=soup.new_tag('span',attrs={'class':'code-title'})
    name.string='Показать пример кода'
    language_tag=soup.new_tag('span',attrs={'class':'code-lang'})
    language_tag.string=language.upper()
    summary.append(name)
    summary.append(language_tag)
    pre.wrap(details)
    details.insert(0,summary)
    button=soup.new_tag('button',attrs={'type':'button','class':'copy-code','aria-label':'Копировать код'})
    button.string='Копировать'
    pre.insert_before(button)
body=str(soup)
css='''
:root{--bg:#fff;--panel:#f9fafb;--paper:#fff;--ink:#172b3f;--muted:#64748b;--line:#dbe2e8;--link:#1769b0;--accent:#00a98f;--code:#152433;--codeink:#e7f0ff;--shadow:0 7px 20px #102b4412}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:28px}body{font:15px/1.68 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;color:var(--ink);background:var(--bg);margin:0}a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}.top{height:64px;position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:18px;padding:0 25px;background:var(--paper);border-bottom:1px solid var(--line)}.brand{font-weight:800;font-size:16px;white-space:nowrap;color:var(--ink)}.brand-mark{display:inline-flex;background:var(--accent);height:26px;width:26px;border-radius:6px;color:white;align-items:center;justify-content:center;margin-right:8px}.brand small{color:var(--muted);font-size:11px;margin-left:8px;font-weight:500}.top-right{margin-left:auto;display:flex;align-items:center;gap:8px}.button{border:1px solid var(--line);background:var(--paper);color:var(--ink);border-radius:8px;padding:8px 12px;cursor:pointer;font:inherit;font-size:12px}.button:hover{border-color:var(--link)}.app{display:grid;grid-template-columns:285px minmax(0,950px) minmax(0,1fr);min-height:calc(100vh - 64px)}aside{border-right:1px solid var(--line);background:var(--panel);padding:20px 12px 25px 18px;position:sticky;top:64px;height:calc(100vh - 64px);overflow:auto}.search{width:100%;padding:10px 12px;border:1px solid var(--line);outline:none;background:var(--paper);color:var(--ink);border-radius:8px;font-size:13px;margin-bottom:18px}.nav-heading{font-size:10px;text-transform:uppercase;letter-spacing:1.1px;color:var(--muted);font-weight:800;margin:14px 8px 10px}.nav-link{display:block;font-size:12.5px;line-height:1.4;padding:7px 10px;border-radius:7px;color:var(--ink);margin-bottom:2px}.nav-link.active,.nav-link:hover{background:#e6edf5;color:#15558e;text-decoration:none}.nav-sub{font-size:11.5px;padding-left:23px;color:var(--muted)}main{padding:47px 55px 95px;max-width:1000px;width:100%}.article h1{font-size:37px;letter-spacing:-1.4px;line-height:1.13;margin:0 0 20px;font-weight:800}.article h2{font-size:24px;letter-spacing:-.6px;margin:48px 0 17px;line-height:1.25;border-top:1px solid var(--line);padding-top:28px}.article h3{font-size:17px;margin:29px 0 10px;line-height:1.35}.article p{margin:11px 0 16px}.article p:first-of-type{color:var(--muted)}.article blockquote{margin:24px 0;background:#f6f9fc;border-left:4px solid var(--accent);border-radius:0 8px 8px 0;padding:14px 18px}.article blockquote p{color:var(--ink)!important;margin:0}.article strong{font-weight:700}.article table{border-collapse:separate;border-spacing:0;width:100%;font-size:12.5px;margin:16px 0 25px;border:1px solid var(--line);border-radius:9px;overflow:hidden;display:table}.article th{background:#eff3f7;color:#324b65;text-align:left;font-weight:700;font-size:12px}.article th,.article td{padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:top}.article tr:last-child td{border-bottom:0}.article tr:hover td{background:rgba(120,160,195,.06)}.article ul,.article ol{padding-left:24px}.article li{margin:5px 0}.codeblock{font-size:12px;line-height:1.65;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;background:var(--code);color:var(--codeink);padding:20px;overflow:auto;border-radius:9px;margin:10px 0 24px;white-space:pre;tab-size:2}.copy-code{display:block;position:relative;float:right;margin:10px 10px -41px 0;z-index:2;background:#33475c;color:#edf5ff;border:1px solid #5c6f83;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:11px}.diagram{border:1px solid var(--line);border-radius:11px;padding:18px 16px;margin:22px 0 28px;background:#fcfdff;box-shadow:var(--shadow)}.diagram svg{width:100%;max-height:500px}.diagram-title{font-weight:750;font-size:13px;margin-bottom:13px}.diagram-note{font-size:12px;color:var(--muted);margin-top:9px}.flowboxes{display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap}.flowboxes.stack{flex-direction:column}.node{border:1px solid #a4b7c9;background:#ecf2f9;border-radius:9px;padding:14px 16px;min-width:170px;text-align:center;font-size:13px;font-weight:750}.node small{font-size:11px;display:block;margin-top:5px;font-weight:400;color:#64748b}.node.accent{background:#e8f5ec;border-color:#8ab99e}.footer-note{font-size:12px;color:var(--muted);margin-top:55px;padding-top:25px;border-top:1px solid var(--line)}.right{padding:30px 18px}.right-note{position:sticky;top:90px;max-width:220px;font-size:12px;color:var(--muted);line-height:1.6}.muted{color:var(--muted)}.codeblock code{color:inherit}.print-only{display:none}
@media(max-width:1200px){.app{grid-template-columns:255px minmax(0,1fr)}.right{display:none}main{padding:40px 40px 90px}}@media(max-width:780px){.top{height:58px;padding:0 10px;gap:8px}.top-right{gap:5px}.top-right .button:last-child{display:none}.brand{font-size:14px}.brand-mark{margin-right:5px}.brand small{display:none}.app{display:block}aside{display:none;position:fixed;z-index:40;left:0;top:58px;width:285px;height:calc(100vh - 58px);box-shadow:var(--shadow)}aside.open{display:block}main{padding:25px 18px 70px}.article h1{font-size:29px}.article h2{font-size:21px;margin-top:35px}.article table{display:block;overflow-x:auto;white-space:normal}.article th,.article td{min-width:110px}.diagram{overflow:auto}.diagram svg{min-width:660px}.node{min-width:135px}.button{padding:6px 9px}}@media print{.top,aside,.right,.copy-code{display:none!important}.app{display:block}main{max-width:none;padding:0}.article h2{page-break-after:avoid}.diagram,.codeblock,table{break-inside:avoid}.codeblock{white-space:pre-wrap;color:#172b3f;background:#f1f4f7}a{color:var(--ink)}}
[data-theme=dark]{--bg:#0c1723;--panel:#111e2b;--paper:#132231;--ink:#e3edf5;--muted:#a1b2bf;--line:#344454;--link:#83baf4;--code:#07121d;--shadow:none}[data-theme=dark] .nav-link.active,[data-theme=dark] .nav-link:hover{background:#1b3b56;color:#b0dbff}[data-theme=dark] .article th{background:#1d3549;color:#d6e6f5}[data-theme=dark] .article blockquote{background:#192c3d}[data-theme=dark] .diagram{background:#132536}[data-theme=dark] .node{background:#20374b;color:#e3edf5}[data-theme=dark] .node.accent{background:#174537}[data-theme=dark] .article tr:hover td{background:#183349}
'''
css += """
.code-accordion{border:1px solid var(--line);border-radius:9px;margin:12px 0 22px;background:var(--panel);overflow:hidden}
.code-accordion summary{display:flex;align-items:center;gap:12px;padding:11px 14px;cursor:pointer;list-style:none;font-size:13px;font-weight:650;user-select:none}
.code-accordion summary::-webkit-details-marker{display:none}
.code-accordion summary:before{content:'▸';font-size:15px;color:var(--muted);transition:transform .15s}
.code-accordion[open] summary:before{transform:rotate(90deg)}
.code-accordion summary:hover{background:rgba(125,155,180,.09)}
.code-accordion summary:focus-visible{outline:2px solid var(--link);outline-offset:-2px}
.code-lang{margin-left:auto;border:1px solid var(--line);border-radius:5px;padding:1px 7px;font-size:10px;letter-spacing:.4px;color:var(--muted)}
.code-accordion[open] summary{border-bottom:1px solid var(--line)}
.code-accordion .codeblock{margin:0;border-radius:0;padding-top:42px}
.code-accordion .copy-code{float:right;margin:9px 10px -38px 0}
@media print{.code-accordion:not([open]){display:none}.code-accordion[open] .codeblock{white-space:pre-wrap}}
"""
# Prevent inline code and long identifiers from expanding the mobile document width.
css += """
main,.article{min-width:0;overflow-wrap:anywhere}
.article :not(pre)>code{white-space:normal;overflow-wrap:anywhere;word-break:break-word}
.article .code-accordion{max-width:100%}
"""
js='''
const root=document.documentElement,sidebar=document.getElementById('sidebar');
document.getElementById('theme').onclick=()=>{const d=root.dataset.theme==='dark'?'light':'dark';root.dataset.theme=d;document.getElementById('theme').textContent=d==='dark'?'☀ Светлая':'◐ Тёмная'};
document.getElementById('menu').onclick=()=>sidebar.classList.toggle('open');
document.querySelectorAll('aside a').forEach(a=>a.addEventListener('click',()=>sidebar.classList.remove('open')));
document.getElementById('search').addEventListener('input',e=>{const q=e.target.value.toLowerCase().trim();document.querySelectorAll('.nav-link').forEach(a=>{a.style.display=a.dataset.search.includes(q)?'block':'none'})});
const links=[...document.querySelectorAll('.nav-link')];const observed=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){links.forEach(a=>a.classList.toggle('active',a.hash==='#'+e.target.id))}})},{rootMargin:'-80px 0px -70% 0px'});document.querySelectorAll('h2[id],h3[id]').forEach(h=>observed.observe(h));
document.querySelectorAll('.copy-code').forEach(b=>b.onclick=async()=>{const code=b.nextElementSibling?.textContent||'';try{await navigator.clipboard.writeText(code);b.textContent='Скопировано';setTimeout(()=>b.textContent='Копировать',1400)}catch(e){b.textContent='Выделите код'}});
'''
out=f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Go Product Platform — Руководство по архитектуре</title><meta name="description" content="Руководство v15 с приоритетом Go: модульный монолит, локальные ИИ-агенты, навыки агентов, нативные рабочие деревья, фоновые E2E, PostgreSQL, Wails, Connect RPC, приоритет библиотек при развёртывании."><style>{css}</style></head><body><header class="top"><button class="button" id="menu" aria-label="Меню">☰</button><a href="#" class="brand"><span class="brand-mark">G</span>Go Product Platform<small>Руководство по архитектуре / 15.0</small></a><div class="top-right"><button class="button" id="theme">◐ Тёмная</button><button class="button" onclick="window.print()">⎙ Печать / PDF</button></div></header><div class="app"><aside id="sidebar"><input id="search" class="search" placeholder="Найти раздел…" aria-label="Поиск разделов"><div class="nav-heading">Содержание</div><nav>{nav}</nav></aside><main><article class="article">{body}</article><div class="footer-note">Go Product Platform · v15.0 · 20.11.2026 · Документация как код. Внешние ссылки ведут на первоисточники.</div></main><div class="right"><div class="right-note"><strong>Цель платформы</strong><p>Приоритет Go · Встроенные модули · Нативные рабочие деревья на Mac и фоновые E2E · Минимальное развёртывание через Compose.</p><p>Для изменения документа редактируй `platform/handbook/docs/`, затем собирай HTML: `python3 build.py`.</p><p><a href="#decision">К решению ↑</a></p></div></div></div><script>{js}</script></body></html>'''
(p/'index.html').write_text(out)
(p/'platform/handbook/index.html').write_text(out)
print('sections',len(heads),'HTML KB',round(len(out)/1024),'MD KB',round(len(combined)/1024))
