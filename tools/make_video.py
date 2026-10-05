"""
自动录制项目演示视频（无人操作）：后台浏览器按脚本点击页面，叠加字幕和鼠标指针，导出 mp4。

用法（先启动作品网站和看板）：
    python3 -m http.server 8600            # 在 portfolio 目录
    streamlit run app/app.py --server.port 8502
    python tools/make_video.py             # 输出 reports/demo_video.mp4

环境变量 SITE / DASH 可改成线上地址，例如 SITE=http://ltfolio.cn DASH=http://ltfolio.cn/demo
"""
import os
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = os.getenv("SITE", "http://localhost:8600")
DASH = os.getenv("DASH", "http://localhost:8502")
OUT = ROOT / "reports" / "demo_video.mp4"
TMP = Path("/tmp/demo_video_raw")
W, H = 1600, 900

OVERLAY = """
(() => {
  if (document.getElementById('__cap')) return;
  const add = () => {
    const st = document.createElement('style');
    st.textContent = `
      #__cap{position:fixed;left:50%;bottom:34px;transform:translateX(-50%);z-index:2147483647;
        max-width:1100px;padding:14px 28px;border-radius:14px;background:rgba(29,29,31,.88);color:#fff;
        font:500 26px/1.45 "Noto Sans CJK SC","PingFang SC",sans-serif;letter-spacing:.5px;text-align:center;
        box-shadow:0 8px 30px rgba(0,0,0,.25);transition:opacity .35s;opacity:0;pointer-events:none}
      #__cap small{display:block;font-size:18px;color:#c7c7cc;font-weight:400;margin-top:2px}
      #__cur{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;
        transition:transform .7s cubic-bezier(.4,0,.2,1)}
      #__cur.click::after{content:"";position:absolute;left:-14px;top:-14px;width:28px;height:28px;border-radius:50%;
        background:rgba(0,113,227,.35);animation:__p .5s ease-out}
      @keyframes __p{from{transform:scale(.3);opacity:1}to{transform:scale(1.6);opacity:0}}
      #__end{position:fixed;inset:0;z-index:2147483646;background:#f5f5f3;display:flex;flex-direction:column;
        align-items:center;justify-content:center;font-family:"Noto Sans CJK SC",sans-serif;color:#1d1d1f;opacity:0;transition:opacity .6s}
      #__end h1{font-size:54px;margin:0 0 18px;font-weight:600}
      #__end p{font-size:26px;margin:8px 0;color:#424245}
      #__end b{font-family:"Noto Sans Mono CJK SC",monospace;color:#1d1d1f}`;
    document.head.appendChild(st);
    const cap = document.createElement('div'); cap.id = '__cap'; document.body.appendChild(cap);
    const cur = document.createElement('div'); cur.id = '__cur';
    cur.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2l16 10-7 1.5L9.5 21z" fill="#1d1d1f" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>';
    cur.style.transform = `translate(${window.__cx||800}px,${window.__cy||450}px)`;
    document.body.appendChild(cur);
  };
  if (document.body) add(); else document.addEventListener('DOMContentLoaded', add);
})();
"""


class Rec:
    def __init__(self, page):
        self.p = page
        self.cx, self.cy = 800, 450
        self.text = ("", "")

    def ensure(self):
        self.p.evaluate(OVERLAY)
        self.p.evaluate(f"window.__cx={self.cx};window.__cy={self.cy};"
                        f"document.getElementById('__cur').style.transform='translate({self.cx}px,{self.cy}px)'")

    def cap(self, main, sub="", hold=0.0):
        self.ensure()
        self.text = (main, sub)
        self.p.evaluate("""([m,s]) => { const c=document.getElementById('__cap');
            if(!m){c.style.opacity=0;return;} c.innerHTML=m+(s?'<small>'+s+'</small>':''); c.style.opacity=1; }""",
                        [main, sub])
        time.sleep(hold)

    def move(self, x, y, wait=0.8):
        self.ensure()
        self.cx, self.cy = int(x), int(y)
        self.p.evaluate(f"document.getElementById('__cur').style.transform='translate({x}px,{y}px)'")
        self.p.mouse.move(x, y)
        time.sleep(wait)

    def click(self, locator, after=0.6):
        loc = locator.first
        loc.scroll_into_view_if_needed()
        time.sleep(0.3)
        b = loc.bounding_box()
        x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        self.move(x, y)
        self.p.evaluate("(()=>{const c=document.getElementById('__cur');c.classList.remove('click');void c.offsetWidth;c.classList.add('click')})()")
        loc.click()
        time.sleep(after)

    def scroll(self, dy, steps=30, wait=0.5, target="window"):
        for _ in range(steps):
            if target == "window":
                self.p.mouse.wheel(0, dy / steps)
            time.sleep(0.03)
        time.sleep(wait)

    def goto(self, url, settle=3.0):
        self.p.goto(url, wait_until="networkidle")
        time.sleep(settle)
        self.ensure()
        if self.text[0]:
            self.cap(*self.text)


def dash_page(r, slug, settle=4.0, sel=".js-plotly-plot, [data-testid='stDataFrame'], table"):
    r.goto(f"{DASH}/{slug}", settle=0.5)
    try:
        r.p.wait_for_selector(sel, timeout=30000)
    except Exception:  # noqa: BLE001
        pass
    time.sleep(settle)


def dash_scroll(r, dy, steps=40, wait=1.5):
    """Streamlit 的滚动发生在主区域容器里，把鼠标放在内容区再滚轮"""
    r.move(900, 500, wait=0.2)
    for _ in range(steps):
        r.p.mouse.wheel(0, dy / steps)
        time.sleep(0.035)
    time.sleep(wait)


def run():
    if TMP.exists():
        shutil.rmtree(TMP)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                            record_video_dir=str(TMP), record_video_size={"width": W, "height": H}, locale="zh-CN")
        p = ctx.new_page()
        r = Rec(p)

        # 1. 首页
        r.goto(SITE + "/", settle=1.5)
        r.cap("电商 AI 运营助手", "1 亿条淘宝用户行为数据 · 分析看板 + AI 问数 + 自动周报 + 智能客服", 4)
        r.move(700, 300)
        r.cap("问题：运营每天都在问同样的问题", "用户在哪一步流失？谁是核心用户？哪个品类掉了？", 4)

        # 2. 首页 AI 问数回放
        r.scroll(380, wait=1)
        r.cap("AI 问数：用中文提问，AI 写 SQL、查数据库、总结结论", "", 1.5)
        chips = p.locator("#ask-chips .chip")
        r.click(chips.nth(1), after=1)
        time.sleep(9)
        r.cap("每条回答都附带 SQL，可以核对", "23 道标准题测试，准确率 95.7%", 4)
        r.click(chips.nth(2), after=1)
        time.sleep(9)

        # 3. 经营看板
        r.cap("经营总览：核心指标和每日趋势", "数据分四层建表，16 项自动质量检查全部通过", 0)
        dash_page(r, "", settle=6)
        r.move(600, 260, 2)
        dash_scroll(r, 650, wait=3)
        r.move(1000, 420, 2)
        dash_scroll(r, 650, wait=2.5)

        r.cap("用户转化：漏斗和购买路径", "按次数算转化率 2.2%，按用户算 61%：先问清口径", 0)
        dash_page(r, "conversion")
        r.move(700, 400, 2)
        dash_scroll(r, 700, wait=3)
        dash_scroll(r, 700, wait=2.5)

        r.cap("用户分层：RFM 模型把用户分成 8 类", "不同用户群用不同的运营动作", 0)
        dash_page(r, "users")
        dash_scroll(r, 600, wait=3)
        dash_scroll(r, 700, wait=2.5)

        r.cap("品类分析：流量 × 转化四象限", "找到“流量大、转化低”的机会品类", 0)
        dash_page(r, "category")
        r.move(900, 450, 2)
        dash_scroll(r, 700, wait=3.5)

        # 4. 自动周报
        r.cap("自动周报：SQL 算数，AI 写分析，自动核对数字后推送飞书", "数字全部来自 SQL，AI 只负责写文字", 0)
        dash_page(r, "report", settle=1.5, sel="button:has-text('生成本周周报')")
        r.click(p.get_by_role("button", name="生成本周周报"), after=4)
        dash_scroll(r, 500, wait=3)
        dash_scroll(r, 600, wait=3)
        dash_scroll(r, 600, wait=3)

        # 5. 智能客服（首页回放）
        r.cap("智能客服：先检索店铺规则，只根据规则回答", "回答标注出处，查不到就转人工", 0)
        r.goto(SITE + "/", settle=1)
        r.scroll(380, wait=0.8)
        r.click(p.locator('[data-tab="svc"]'), after=1)
        sc = p.locator("#svc-chips .chip")
        r.click(sc.nth(0), after=1)
        time.sleep(7)
        n = sc.count()
        r.click(sc.nth(n - 1), after=1)
        r.cap("问到规则里没有的内容，不编造，直接转人工", "", 7)

        # 6. 项目页
        r.cap("项目页：架构、评测结果和局限性都写清楚", "", 0)
        r.goto(SITE + "/ecom.html", settle=1.5)
        for _ in range(4):
            r.scroll(700, wait=2.2)

        # 7. 结尾
        r.cap("", "", 0)
        p.evaluate("""() => { const e=document.createElement('div'); e.id='__end';
            e.innerHTML='<h1>电商 AI 运营助手</h1><p>在线体验　<b>ltfolio.cn</b></p><p>代码　<b>github.com/Lt0226-Win/ecom-ai-assistant</b></p>';
            document.body.appendChild(e); requestAnimationFrame(()=>e.style.opacity=1);
            document.getElementById('__cur').style.display='none'; }""")
        time.sleep(5)
        video = p.video.path()
        ctx.close()
        b.close()

    OUT.parent.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video,
                    "-vf", "scale=1920:1080:flags=lanczos,fps=30", "-c:v", "libx264", "-preset", "slow",
                    "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(OUT)], check=True)
    print("输出：", OUT)


if __name__ == "__main__":
    run()
