# Playwright 历史方案说明

> 本文档对应仓库早期的浏览器自动化发布方案。
> 当前默认发布链路已经改为微信官方草稿箱 API，请优先参考 [README.md](../README.md)、[QUICK_START.md](QUICK_START.md) 和 [PUBLISH_GUIDE.md](PUBLISH_GUIDE.md)。

太好了 — 既然你已经把**选择器适配 / 图片/公式上传替换 / 代码微信化 / 鲁棒性**这些难点准备好了，下面我给你一套**基于 Python（Playwright）**的实战方案与完整示例代码，能在**真实登录的浏览器会话**里注入脚本、读写编辑器 DOM、在光标处粘入 HTML 模板、并做回执与错误处理。
方案可靠、易复用，也能把你的后端上传、替换流水线无缝接入。

我把要点分成：思路 + 环境准备 + 核心 API（带完整 Playwright Python 示例）+ 注意事项 / 工程化建议。直接可以拷贝运行并改造到你现有流水线中。

---

## 思路回顾（为什么用 Playwright）

* 你要在“真实的用户页面”操作 DOM（不是做浏览器扩展），Playwright 能**在已登录会话/持久化 profile 下以 headful 模式控制浏览器**，并能在页面上下文 `evaluate` 任意 JS（等同注入 content script）。
* 和 Selenium 比，Playwright 的 `evaluate`、frame 处理、等待、选择器语义更现代、稳定。
* 我们用 **持久化 profile（user_data_dir）**，这样你可以手动先登录公众号后台，然后脚本复用该登录态去操作。

---

## 环境准备（推荐）

1. 安装 Playwright 与依赖：

```bash
pip install playwright
playwright install
```

2. 准备一个 user data 目录（例如 `./tmp_profile`），第一次运行用 headful 浏览器手动登录 mp.weixin.qq.com 并登录你的公众号账号，登陆后关闭浏览器，后续脚本会复用该 profile（保持登录态）。
3. 确保你的后端图片/公式上传接口可用（你已有）。脚本只负责替换 HTML 中的 `src` 为微信托管 URL（若你要自动上传，也可把上传 API 调用并替换逻辑并入）。

---

## 核心功能（目标实现）

* `open_wechat_editor(url)`：在持久化profile中打开页面并等待编辑器加载。
* `find_editor_root()`：跨 iframe 查找 `contenteditable` 容器。
* `read_editor_html()`：读取当前编辑器 `innerHTML`。
* `insert_html_at_cursor(html)`：在当前光标位置插入我们生成的 HTML（使用 Range + createContextualFragment），并返回成功/错误。
* `paste_via_clipboard(html)`：备用方式，写入剪贴板再触发粘贴（需手势许可/headful 模式）。
* `inject_bridge()`：注入 page-level bridge（可供后续 JS 调用）。
* 错误处理/返回值。

---

## Playwright Python 示例（一套可运行的最小实现）

> 说明：示例默认你已经通过 `user_data_dir` 登录过 mp.weixin.qq.com。把示例中的 `EDITOR_URL` 换成你要编辑的图文编辑页 URL（或主页然后导航）。

```python
# file: wechat_editor_controller.py
from playwright.sync_api import sync_playwright, Page, Frame
import time, json
from typing import Optional

USER_DATA_DIR = "./tmp_profile"   # 持久化 profile（第一次手动登录）
EDITOR_URL = "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit"  # 或者你的具体编辑 URL

JS_FIND_EDITOR = r'''
(function findEditorRoot(doc){
    // 递归查找 contenteditable 元素或常见编辑器容器 (iframe 内优先)
    function findInDocument(d) {
        // 常见编辑器 iframe/容器选择器列表 (可扩展)
        const iframeSelectors = [
            'iframe[id*="ueditor"]', 
            'iframe[class*="editor"]', 
            'iframe'
        ];
        // 首先尝试在 iframe 中找
        for (const sel of iframeSelectors) {
            const ifr = d.querySelector(sel);
            if (ifr && ifr.contentDocument) {
                const rec = findInDocument(ifr.contentDocument);
                if (rec) return rec;
            }
        }
        // 找 contenteditable 真正编辑区
        const ed = d.querySelector('[contenteditable="true"], .weui-desktop-editor__inner, .rich_editor, .editor-inner');
        if (ed) return {type:'element', path:null, found:true};
        // 兜底：在 body 里查找第一个 contenteditable
        const all = d.querySelectorAll('[contenteditable="true"]');
        if (all && all.length) return {type:'element', path:null, found:true};
        return null;
    }
    return findInDocument(document);
})();
'''

# JS 插入 HTML 在光标处（Range 插入）
JS_INSERT_AT_CURSOR = r'''
(function(html){
    // 尝试找到当前 selection 的 Range，并在其位置插入 html 片段
    try {
        var sel = window.getSelection();
        if (!sel) {
            return {ok:false, error:'no selection'};
        }
        var range = sel.rangeCount ? sel.getRangeAt(0) : null;
        if (!range) {
            // 找到 editor 并 append
            var ed = document.querySelector('[contenteditable="true"], .weui-desktop-editor__inner, .editor-inner');
            if (!ed) { return {ok:false, error:'no editor found'}; }
            ed.focus();
            range = document.createRange();
            range.selectNodeContents(ed);
            range.collapse(false);
            sel.removeAllRanges();
            sel.addRange(range);
        }
        // create fragment and insert
        var frag = range.createContextualFragment(html);
        range.deleteContents();
        range.insertNode(frag);
        // 将光标移动到插入节点后面
        sel.collapseToEnd();
        return {ok:true};
    } catch (e) {
        return {ok:false, error: String(e)};
    }
})
'''

# 可选：在页面注入 bridge（主世界）以便跨隔离世界进行更复杂调用
JS_INJECT_BRIDGE = r'''
(function(){
    if (window.__WX_INJECT_BRIDGE__) return true;
    var s = document.createElement('script');
    s.textContent = `
    window.__WX_INJECT_BRIDGE__ = {
        pasteHtml: function(html){
            try {
                const sel = window.getSelection();
                if (!sel || !sel.rangeCount) return false;
                var range = sel.getRangeAt(0);
                range.deleteContents();
                var frag = range.createContextualFragment(html);
                range.insertNode(frag);
                sel.collapseToEnd();
                return true;
            } catch (e) {
                return false;
            }
        }
    };
    `;
    (document.head || document.documentElement).appendChild(s);
    s.remove();
    return true;
})();
'''

def open_editor_and_inject(html_to_insert: str):
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(USER_DATA_DIR, headless=False, args=["--start-maximized"])
        page = browser.new_page()
        page.goto(EDITOR_URL)
        # 等页面加载（根据你实现可更智能等待编辑器容器）
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)

        # 可选：注入 bridge 到页面主世界（更稳定地执行粘贴）
        page.evaluate(JS_INJECT_BRIDGE)

        # 检查编辑器是否存在（Debug）
        found = page.evaluate(JS_FIND_EDITOR)
        print("editor found:", found)

        # 方法 A：直接在页面上下文插入（优先）
        res = page.evaluate(JS_INSERT_AT_CURSOR, html_to_insert)
        print("insert result:", res)

        # 方法 B：通过 bridge 粘贴（如果上面失败）
        if not res.get("ok"):
            # 调用 page.evaluate to call the bridge
            ok = page.evaluate("() => { return window.__WX_INJECT_BRIDGE__ && window.__WX_INJECT_BRIDGE__.pasteHtml(%s) }" % json.dumps(html_to_insert))
            print("bridge paste ok:", ok)

        # 读取验证
        time.sleep(1)
        editor_html = None
        try:
            editor_html = page.evaluate("() => { var ed = document.querySelector('[contenteditable=\"true\"], .weui-desktop-editor__inner, .editor-inner'); return ed ? ed.innerHTML : null; }")
        except Exception as e:
            print("read html failed:", e)
        print("editor innerHTML length:", 0 if not editor_html else len(editor_html))

        # 保持窗口打开以便手动检查，或关闭
        # browser.close()
        print("done, keep browser open for inspection")
        return

if __name__ == "__main__":
    sample_html = '<p style="border:1px solid #ddd;padding:8px;border-radius:6px;">Hello 插入测试 <strong>学术灰</strong></p>'
    open_editor_and_inject(sample_html)
```

### 代码要点说明

* `launch_persistent_context(USER_DATA_DIR, headless=False)`：使用持久化 profile，第一次运行会打开浏览器让你手动登录；之后复用登录会话。
* `JS_INSERT_AT_CURSOR`：在页面上下文用 Range 插入 HTML（更像用户粘贴，比直接 `innerHTML=` 更温和）。
* `JS_INJECT_BRIDGE`：把一个主世界的 global `__WX_INJECT_BRIDGE__` 注入页面（用于在隔离环境也能调用主世界 API）。
* 如果第一种插入失败（微信可能清洗或光标不在编辑器），脚本还尝试通过 bridge 粘贴。
* 最后读取编辑器 `innerHTML` 做回执 / 校验。

---

## 进阶：把图片替换 + 上传并插入微信托管 URL

你说你已有图片/公式上传替换逻辑。常见做法：

1. 在 HTML 模板里把 `<img src="local://...">` 或占位符（`data-src` 或 `data-wx-upload-id`）先留好。
2. 在入库前或插入后，用 Playwright 读取 `editor.innerHTML` → 在 Python 端做替换：调用你的图片上传 API（返回微信 `img_url`），用 `page.evaluate("() => editor.innerHTML = ...")` 或用 Range 定位替换节点的 `src`。
3. 推荐：**先把图片上传换成微信托管 URL，再插入**，这样插入时不会被再次清洗为外链或丢失。

示例伪流程：

```python
# 伪代码流程
html = render_template(...)  # 你生成的微信兼容 HTML，内部 img src 指向本地临时 URL
# 批量 findall local src
local_srcs = extract_image_srcs(html)
for src in local_srcs:
    wx_url = my_upload_image_to_wechat(src)  # 你后端实现
    html = html.replace(src, wx_url)
# 插入 html 到编辑器
page.evaluate(JS_INSERT_AT_CURSOR, html)
```

---

## 其他实现选项（如果你更偏好 Selenium / CDP）

* Selenium 也能通过 `driver.execute_script(js)` 做同样工作，但对跨 iframe、持久 profile、等待等细节处理上 Playwright 更方便；若你已有 Selenium 框架，也可把 JS insert 片段直接复用。
* 还可以用 Chrome DevTools Protocol（`pyppeteer` / `cdp`）实现更底层控制（比如写 clipboard、触发 paste event），但实现复杂度更高。

---

## 注意事项（必须留意）

1. **登录态**：用 `user_data_dir` 保存登录态，首次运行必须人工登录并通过 MFA/验证码。
2. **微信清洗**：即便插入 HTML，微信服务器在保存或发表时仍会按其白名单和清洗规则处理（移除 class、style 属性）。你需要把 `html` 预处理成“微信兼容白名单 HTML”（你已有这部分）。
3. **节奏与重试**：写入可能失败，请实现重试机制和读取回执（`innerHTML` 对比，或寻找插入的独特标记）。
4. **合规/风险**：批量自动化发表、匿名代发等可能触发风控，请确保操作有人工确认环节并遵守微信平台规则。
5. **权限**：若希望用系统剪贴板方式（`navigator.clipboard`），有些浏览器版本要求用户手势许可（即必须在用户点击事件内触发），所以脚本不能总是静默写剪贴板。Range 插入更稳。
6. **版本差异**：微信公众号后台 DOM 结构会变，做好选择器 fallback 与 `MutationObserver` 监控变化。

---

## 工程化建议（把这套接入你现有流水线）

* 把 Playwright 脚本做成一个**可调用服务**（microservice），接受 `POST`：`{html, images: [{id, path}], callback_url}`。服务会：

  1. 上传图片（返回微信 URL）；2. 替换 HTML；3. 在浏览器会话插入 HTML；4. 读取回执并 POST 回调结果（成功/失败 + 编辑器 innerHTML snippet）。
* 为稳定性：把插入动作封装成事务：先在 DOM 插入占位 `<!-- MY_TOOL_INSERT:UUID -->`，确认后再把真实 HTML 片段替换进占位；若失败可回滚或提示人工处理。
* 实现一个 dashboard（本地 Web UI）供人工触发/审核，避免全自动发表导致风控。

---

## 已实现的功能

基于上述设计，我们已经实现了一个完整的发表模块：

### 实现的功能

✅ **完整的 Python 模块**（`src/wechat_publisher.py`）：
- 图片批量上传接口调用（预留接口）
- 模板替换（Markdown 转 HTML）
- 插入后校验与重试策略
- 完整的日志记录

✅ **关键 JS 封装**：
- `JS_FIND_EDITOR` - 基于实际 XPath 的编辑器查找
- `JS_INSERT_AT_CURSOR` - 使用 Range API 插入内容（支持 iframe）
- `JS_SET_TITLE_AUTHOR` - 自动填充标题和作者
- `JS_INJECT_BRIDGE` - 注入全局桥接函数

✅ **命令行工具**：
- `publish_wechat.py` - 发表命令行工具
- `schedule_publish.py` - 定时发表工具

✅ **完整文档**：
- `docs/PUBLISH_GUIDE.md` - 详细发表指南
- `docs/QUICK_START.md` - 快速开始指南

### 改进点

相比原始设计，实际实现增加了以下改进：

1. **智能编辑器查找**：基于实际 DOM 结构，支持 uEditor/edui1 iframe
2. **自动填充标题和作者**：从 Markdown front matter 提取并填充
3. **登录状态检测**：自动检测登录状态，支持等待登录完成
4. **错误处理**：完善的错误处理和日志记录
5. **定时发表**：支持多任务批量定时发表

### 使用方式

```bash
# 基本发表
python publish_wechat.py article.md

# 定时发表
python schedule_publish.py --config publish_config.json
```

详细使用说明请参考 `docs/PUBLISH_GUIDE.md` 和 `docs/QUICK_START.md`。


Title:
XPath:/html/body/div[2]/div/div/div/div/div[4]/div/div/div[1]/div[3]/div/div[1]/div[3]/div/div/div/div[8]/textarea
element:<textarea id="title" type="text" placeholder="请在这里输入标题" class="frm_input js_title js_counter js_field js_article_title edui-default" name="title" max-length="64"></textarea>

Author:
XPath:/html/body/div[2]/div/div/div/div/div[4]/div/div/div[1]/div[3]/div/div[1]/div[3]/div/div/div/div[10]/input[1]element::<input id="author" type="text" placeholder="请输入作者" class="frm_input js_author js_counter js_field edui-default" name="author" max-length="8" autocomplete="off">

Context:
XPath:/html/body/div[2]/div/div/div/div/div[4]/div/div/div[1]/div[3]/div/div[1]/div[3]/div/div/div/div[13]/div[7]/div[1]
element:<div id="edui1_contentplaceholder" class="editor_content_placeholder edui-default" style="display:none">从这里开始写正文</div>

新文章（下拉菜单中的"文章"选项）：
- 有效点击区域 XPath：`/html/body/div[1]/div/div[4]/div/div/div[2]/div[2]/div[3]/div[2]/div/div[2]`
- 文章文字 XPath：`/html/body/div[1]/div/div[4]/div/div/div[2]/div[2]/div[3]/div[2]/div/div[2]/div/div`
- Element：`<div class="new-creation__menu-content">...<div class="new-creation__menu-title">文章</div></div>`

**注意**：点击"新的创作"按钮后，会展开下拉菜单，需要点击"文章"选项（不是"写新文章"）来进入编辑页面。



你这次“找不到编辑器”的根因有几个很典型的坑（从你的日志和给的 XPath 能准确定位）：

1. 你点了“新的创作 → 文章”后**并没有进入编辑页**，URL 又回到了 `home/index`（日志 13:17:35）。原因通常是：

   * 顶部有一个**遮罩/新手引导**（你日志里出现了 *Broadcast Live Stream … Got It* 的浮层）。不先点 “Got It/我知道了”，菜单点击就会被拦。
   * “文章”菜单会在**当前页打开、或在新标签页打开**（小概率）。你只盯着原 `page` 就会以为没跳转。

2. 你后面**直接跳 `action=edit` 的裸 URL**，但微信会校验 token/上下文，往往重定向回首页，所以还是找不到编辑器。

3. 即使到了编辑页，正文区一开始是你贴出来的这个**“占位节点”**：

   ```
   <div id="edui1_contentplaceholder" class="editor_content_placeholder" style="display:none">从这里开始写正文</div>
   ```

   真正的编辑器在一个 **UEditor 的 iframe** 里，需要先**点击正文区域**，等 `iframe[id^="ueditor"]` 挂载，再切 frame 操作。否则你在主文档里永远找不到 contenteditable。

---

下面给你一段“能打通”的修复版流程（Playwright / Python），解决以上三点：

```python
from playwright.sync_api import sync_playwright, expect
import time

USER_DATA_DIR = "./tmp_profile"
HOME_URL = "https://mp.weixin.qq.com/"

def goto_new_article(page):
    page.goto(HOME_URL, wait_until="domcontentloaded")

    # 1) 处理可能出现的引导/遮罩
    for text in ["Got It", "我知道了", "知道了", "关闭"]:
        loc = page.get_by_text(text, exact=True)
        if loc.count():
            try:
                loc.first.click(timeout=1000)
                time.sleep(0.3)
            except: pass

    # 2) 打开“新的创作”菜单
    new_creation = page.locator('[class*="new-creation"], [data-test-id="new-creation"]')
    if not new_creation.count():
        # 备用入口：左侧“新建图文素材”
        alt = page.get_by_text("新建图文", exact=False)
        if alt.count():
            alt.first.click()
    else:
        new_creation.first.click()
        # 菜单里点击“文章”
        # 用 visible + 文本定位，避免依赖易变的 XPath
        article = page.get_by_text("文章", exact=True)
        expect(article).to_be_visible(timeout=5000)
        # 有时会打开**新标签**，要监听是否有新 page
        with page.context.expect_page() as newp:
            article.click()
        try:
            new_page = newp.value  # 如果真的弹了新页
            page = new_page
        except:
            pass

    # 3) 等真正进入编辑页面（URL 会含 appmsg_edit 或 media/appmsg）
    page.wait_for_url(lambda url: "appmsg_edit" in url or "media/appmsg" in url, timeout=20000)

    return page

def wait_editor_ready(page):
    # 标题与作者在主文档
    title = page.locator('#title, textarea[placeholder*="标题"]')
    expect(title).to_be_visible(timeout=15000)

    # 4) 点击正文占位，让 UEditor 挂载 iframe
    placeholder = page.locator('#edui1_contentplaceholder, .editor_content_placeholder')
    if placeholder.count():
        placeholder.first.click()
    else:
        # 也可能正文区域是一个可点击块
        page.get_by_text("从这里开始写正文").first.click(timeout=2000)

    # 5) 等待 UEditor 的 iframe 出现
    # 选择器做得宽一点，兼容不同版本
    iframe_loc = page.frame_locator('iframe[id^="ueditor"], iframe[id*="ueditor"], .edui-editor-iframeholder iframe')
    expect(iframe_loc.first).to_be_visible(timeout=15000)

    # 拿到 Frame 对象
    frame = iframe_loc.first.frame
    # 等 body 可编辑
    frame.wait_for_selector('body', timeout=5000)
    return title, frame

def fill_title(page, text):
    t = page.locator('#title, textarea[placeholder*="标题"]')
    t.fill("")
    t.type(text)

def insert_html(frame, html):
    # 在 frame 里用 Range 插入 HTML 片段
    js = r'''
    (html) => {
      const doc = document;
      const body = doc.body;
      body.focus();
      const sel = doc.getSelection();
      if (!sel || !sel.rangeCount) {
        const r = doc.createRange();
        r.selectNodeContents(body);
        r.collapse(false);
        sel.removeAllRanges();
        sel.addRange(r);
      }
      const range = sel.getRangeAt(0);
      const frag = range.createContextualFragment(html);
      range.deleteContents();
      range.insertNode(frag);
      sel.collapseToEnd();
      return true;
    }'''
    frame.evaluate(js, html)

def main():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(USER_DATA_DIR, headless=False, args=["--start-maximized"])
        page = ctx.new_page()

        # 确保已登录（根据你日志，已登录就会有后台菜单）
        page.goto(HOME_URL, wait_until="domcontentloaded")
        try:
            page.wait_for_selector('a[data-id="menu_profile"]', timeout=6000)
        except:
            print("请先在弹出的浏览器完成扫码登录，再回到脚本窗口回车继续…")
            input()

        # 进入新建文章页（关键修复：处理遮罩 + 监听新标签）
        page = goto_new_article(page)

        # 等编辑器真正 ready（关键修复：点击占位 → 等 iframe）
        title, frame = wait_editor_ready(page)

        # 填标题
        fill_title(page, "从神经网络到智能奇点")

        # 插入正文 HTML（你的微信化 HTML）
        content_html = '<p><strong>自动插入测试</strong>：你好，学术灰。</p>'
        insert_html(frame, content_html)

        # 后续：封面 / 保存草稿 / 预览 / 发表…
        # ...

        input("检查无误后回车退出…")
        ctx.close()

if __name__ == "__main__":
    main()
```

### 要点对应你的报错

* **“编辑器查找 found: False”**：因为你停留在 `home/index` 或未切到**新打开的编辑页**。上面用 `context.expect_page()` 兜住了。
* **“直接打开编辑器 URL 也不行”**：大概率被重定向（token/上下文）。正确姿势是**通过菜单跳转**。
* **“content 未找到”**：正文一开始是**占位 div**，必须**点击后等待 `iframe[id^=ueditor]`**，再用 `frame_locator` 进入 frame 操作 `body`。

---

### 额外建议

* 你已经拿到了标题/作者/正文的 XPath，那是**在编辑页 DOM**里；用上面这套“菜单跳转 + 监听新页 + 点击占位 → 切 frame”后，就能稳定命中。
* 如果“新的创作”菜单的结构又变了，可以改成更粗暴但稳定的：左侧“内容管理 → 素材库 → 新建图文”。
* **强烈建议**：图片/公式先走**微信上传接口**拿 URL，再插入 HTML，发表成功率更高。

把这段替换你现在“步骤 3/4”的逻辑，再跑一遍；如果还卡住，给我你实际后台页面的一个 DOM 结构截图（“新的创作”和编辑器上半部分），我帮你把选择器精确到你账号的版本。

封面的选择方式：1.点击“拖拽或选择封面”;2.两种方式:（1）AI配图：a.点击弹出的"AI 配图"，b.将tag中的excerpt输入到"请描述你想要创作的内容"，c.点击生成的四个图的左上的图,d.新页面出来后点击"使用",e.新页面出来点击确认；（2）图库配图：a.点击弹出的"从图片库选择",b.新页面出来后点击"上传文件",c.设置上传文件路径,并点击"Open",d.点击第一个图,并下一步,e.新页面出来点击确认；

摘要部分：1.识别“选填，不填写则默认抓取正文开头部分文字，摘要会在转发卡片和公众号会话展示。”区域；2.采用tag中的excerpt修改到对应的框中。
