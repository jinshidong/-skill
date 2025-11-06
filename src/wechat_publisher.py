#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号发布器 - 基于 Playwright

使用 Playwright 控制浏览器，实现微信公众号文章的自动发布。
支持登录态持久化、HTML 插入、定时发布等功能。
"""

import json
import time
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from playwright.sync_api import sync_playwright, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# JavaScript 代码片段 - 查找编辑器（基于实际 XPath）
JS_FIND_EDITOR = r'''
(function findEditorRoot(){
    // 基于用户提供的实际 XPath 和元素信息
    
    // 1. 查找标题框
    const titleEl = document.querySelector('#title, textarea[name="title"]');
    
    // 2. 查找作者框
    const authorEl = document.querySelector('#author, input[name="author"]');
    
    // 3. 查找正文编辑器（uEditor - edui1）
    // 先查找 edui1 相关的 iframe 或 contenteditable
    let contentEditor = null;
    
    // 尝试查找 edui1 相关的 iframe
    const eduiIframes = document.querySelectorAll('iframe[id*="edui"], iframe[class*="edui"]');
    for (let i = 0; i < eduiIframes.length; i++) {
        const ifr = eduiIframes[i];
        try {
            if (ifr.contentDocument) {
                const ifrDoc = ifr.contentDocument;
                const ifrBody = ifrDoc.body;
                if (ifrBody && ifrBody.contentEditable === 'true') {
                    contentEditor = {type:'iframe', element:ifr, iframeDoc:ifrDoc, iframeBody:ifrBody};
                    break;
                }
            }
        } catch (e) {
            // 跨域限制
        }
    }
    
    // 如果没找到 iframe，查找 edui1 相关的 contenteditable
    if (!contentEditor) {
        const eduiSelectors = [
            '#edui1',
            '[id*="edui1"]',
            '.edui-editor-body',
            '.edui-editor-content',
            '[class*="edui"]'
        ];
        
        for (const sel of eduiSelectors) {
            const elem = document.querySelector(sel);
            if (elem) {
                // 查找 contenteditable 子元素
                const contentEditable = elem.querySelector('[contenteditable="true"], [contenteditable=""]');
                if (contentEditable) {
                    const style = window.getComputedStyle(contentEditable);
                    if (contentEditable.offsetWidth > 0 && contentEditable.offsetHeight > 0 && style.display !== 'none') {
                        contentEditor = {type:'element', element:contentEditable, parent:sel};
                        break;
                    }
                }
            }
        }
    }
    
    // 如果还是找不到，查找所有 contenteditable（找最大的）
    if (!contentEditor) {
        const all = document.querySelectorAll('[contenteditable="true"], [contenteditable=""]');
        let maxArea = 0;
        let maxEditor = null;
        for (let i = 0; i < all.length; i++) {
            const ed = all[i];
            const style = window.getComputedStyle(ed);
            if (ed.offsetWidth > 0 && ed.offsetHeight > 0 && style.display !== 'none') {
                const area = ed.offsetWidth * ed.offsetHeight;
                if (area > maxArea) {
                    maxArea = area;
                    maxEditor = ed;
                }
            }
        }
        if (maxEditor) {
            contentEditor = {type:'element', element:maxEditor, selector:'largest contenteditable'};
        }
    }
    
    return {
        found: !!(titleEl || authorEl || contentEditor),
        title: titleEl ? {found:true, id:titleEl.id, name:titleEl.name} : {found:false},
        author: authorEl ? {found:true, id:authorEl.id, name:authorEl.name} : {found:false},
        content: contentEditor ? {
            found:true,
            type:contentEditor.type,
            id:contentEditor.element.id || '',
            className:contentEditor.element.className || ''
        } : {found:false}
    };
})();
'''

# JavaScript 代码片段 - 插入标题和作者
JS_SET_TITLE_AUTHOR = r'''
(function(title, author){
    try {
        const titleEl = document.querySelector('#title, textarea[name="title"]');
        const authorEl = document.querySelector('#author, input[name="author"]');
        
        let result = {title: false, author: false};
        
        if (titleEl && title) {
            titleEl.value = title;
            titleEl.dispatchEvent(new Event('input', { bubbles: true }));
            titleEl.dispatchEvent(new Event('change', { bubbles: true }));
            result.title = true;
        }
        
        if (authorEl && author) {
            authorEl.value = author;
            authorEl.dispatchEvent(new Event('input', { bubbles: true }));
            authorEl.dispatchEvent(new Event('change', { bubbles: true }));
            result.author = true;
        }
        
        return result;
    } catch (e) {
        return {ok: false, error: String(e)};
    }
})
'''

# JavaScript 代码片段 - 在光标处插入 HTML（基于实际 XPath）
JS_INSERT_AT_CURSOR = r'''
(function(html){
    // 基于实际 XPath 查找编辑器并插入 HTML
    try {
        let ed = null;
        
        // 1. 优先查找 edui1 相关的 iframe
        const eduiIframes = document.querySelectorAll('iframe[id*="edui"], iframe[class*="edui"]');
        for (let i = 0; i < eduiIframes.length; i++) {
            const ifr = eduiIframes[i];
            try {
                if (ifr.contentDocument) {
                    const ifrDoc = ifr.contentDocument;
                    const ifrBody = ifrDoc.body;
                    if (ifrBody && (ifrBody.contentEditable === 'true' || ifrBody.contentEditable === '')) {
                        ed = ifrBody;
                        break;
                    }
                    // 查找 iframe 内的 contenteditable
                    const ifrEditable = ifrBody.querySelector('[contenteditable="true"], [contenteditable=""]');
                    if (ifrEditable) {
                        ed = ifrEditable;
                        break;
                    }
                }
            } catch (e) {
                // 跨域限制
            }
        }
        
        // 2. 如果没找到 iframe，查找 edui1 相关的元素
        if (!ed) {
            const eduiSelectors = [
                '#edui1',
                '[id*="edui1"]',
                '.edui-editor-body',
                '.edui-editor-content',
                '[class*="edui"]'
            ];
            
            for (const sel of eduiSelectors) {
                const elem = document.querySelector(sel);
                if (elem) {
                    const contentEditable = elem.querySelector('[contenteditable="true"], [contenteditable=""]');
                    if (contentEditable) {
                        const style = window.getComputedStyle(contentEditable);
                        if (contentEditable.offsetWidth > 0 && contentEditable.offsetHeight > 0 && style.display !== 'none') {
                            ed = contentEditable;
                            break;
                        }
                    }
                }
            }
        }
        
        // 3. 兜底：查找所有 contenteditable（找最大的）
        if (!ed) {
            const all = document.querySelectorAll('[contenteditable="true"], [contenteditable=""]');
            let maxArea = 0;
            for (let i = 0; i < all.length; i++) {
                const elem = all[i];
                const style = window.getComputedStyle(elem);
                if (elem.offsetWidth > 0 && elem.offsetHeight > 0 && style.display !== 'none') {
                    const area = elem.offsetWidth * elem.offsetHeight;
                    if (area > maxArea) {
                        maxArea = area;
                        ed = elem;
                    }
                }
            }
        }
        
        if (!ed) {
            return {ok:false, error:'no editor found'};
        }
        
        // 获取正确的 selection 对象（可能是 iframe 内的）
        let sel, doc;
        if (ed.tagName === 'BODY' && ed.ownerDocument) {
            doc = ed.ownerDocument;
            sel = doc.defaultView.getSelection();
        } else {
            doc = document;
            sel = window.getSelection();
        }
        
        if (!sel) {
            return {ok:false, error:'no selection'};
        }
        
        // 聚焦编辑器
        ed.focus();
        
        // 创建 Range 并插入
        let range = sel.rangeCount ? sel.getRangeAt(0) : null;
        if (!range) {
            range = doc.createRange();
            range.selectNodeContents(ed);
            range.collapse(false);  // 移动到末尾
            sel.removeAllRanges();
            sel.addRange(range);
        }
        
        // create fragment and insert
        var frag = range.createContextualFragment(html);
        range.deleteContents();
        range.insertNode(frag);
        
        // 将光标移动到插入节点后面
        range.setStartAfter(frag.lastChild || frag);
        range.collapse(true);
        sel.removeAllRanges();
        sel.addRange(range);
        
        // 触发输入事件（模拟用户输入）
        ed.dispatchEvent(new Event('input', { bubbles: true }));
        ed.dispatchEvent(new Event('change', { bubbles: true }));
        
        return {ok:true, editor: ed.tagName, id: ed.id || '', className: ed.className || ''};
    } catch (e) {
        return {ok:false, error: String(e)};
    }
})
'''

# JavaScript 代码片段 - 注入 bridge
JS_INJECT_BRIDGE = r'''
(function(){
    if (window.__WX_INJECT_BRIDGE__) return true;
    var s = document.createElement('script');
    s.textContent = `
    window.__WX_INJECT_BRIDGE__ = {
        pasteHtml: function(html){
            try {
                const sel = window.getSelection();
                if (!sel || !sel.rangeCount) {
                    var ed = document.querySelector('[contenteditable="true"], .weui-desktop-editor__inner, .editor-inner, .appmsg_editor');
                    if (!ed) return false;
                    ed.focus();
                    var range = document.createRange();
                    range.selectNodeContents(ed);
                    range.collapse(false);
                    sel.removeAllRanges();
                    sel.addRange(range);
                }
                var range = sel.getRangeAt(0);
                range.deleteContents();
                var frag = range.createContextualFragment(html);
                range.insertNode(frag);
                range.setStartAfter(frag.lastChild || frag);
                range.collapse(true);
                sel.removeAllRanges();
                sel.addRange(range);
                return true;
            } catch (e) {
                console.error('pasteHtml error:', e);
                return false;
            }
        },
        getEditorHtml: function(){
            var ed = document.querySelector('[contenteditable="true"], .weui-desktop-editor__inner, .editor-inner, .appmsg_editor');
            return ed ? ed.innerHTML : null;
        },
        clearEditor: function(){
            var ed = document.querySelector('[contenteditable="true"], .weui-desktop-editor__inner, .editor-inner, .appmsg_editor');
            if (ed) {
                ed.innerHTML = '';
                ed.focus();
            }
            return ed !== null;
        }
    };
    `;
    (document.head || document.documentElement).appendChild(s);
    s.remove();
    return true;
})();
'''

# JavaScript 代码片段 - 查找并点击发布按钮
JS_FIND_PUBLISH_BUTTON = r'''
(function(){
    // 查找发布相关按钮
    const buttonSelectors = [
        'button:has-text("发布")',
        'button:has-text("群发")',
        'a:has-text("发布")',
        'a:has-text("群发")',
        '.btn_publish',
        '.btn_publish_msg',
        '[data-action="publish"]',
        'button[class*="publish"]',
        'a[class*="publish"]'
    ];
    
    for (const sel of buttonSelectors) {
        try {
            const btn = document.querySelector(sel);
            if (btn && btn.offsetParent !== null) {  // 检查是否可见
                return {found: true, selector: sel, text: btn.textContent.trim()};
            }
        } catch (e) {
            // 某些选择器可能不支持，继续尝试
        }
    }
    
    // 尝试通过文本内容查找
    const allButtons = document.querySelectorAll('button, a');
    for (const btn of allButtons) {
        const text = btn.textContent.trim();
        if (text === '发布' || text === '群发' || text.includes('发布') || text.includes('群发')) {
            if (btn.offsetParent !== null) {
                return {found: true, selector: 'text_match', text: text};
            }
        }
    }
    
    return {found: false};
})();
'''

# JavaScript 代码片段 - 设置定时发布（同步版本，支持日期选择）
JS_SET_SCHEDULED_PUBLISH = r'''
(function(enableScheduled, scheduledDate, scheduledTime, enableGroupNotify){
    // enableScheduled: 是否启用定时发布
    // scheduledDate: 日期，格式 "YYYY-MM-DD" 或 "today" 或 "tomorrow"，如 "2024-12-25" 或 "today"
    // scheduledTime: 定时时间，格式 "HH:MM"，如 "20:30"
    // enableGroupNotify: 是否启用群发通知（默认false）
    
    // 同步等待函数（使用 busy-wait）
    function sleep(ms) {
        const start = Date.now();
        while (Date.now() - start < ms) {}
    }
    
    // 解析日期
    function parseDate(dateStr) {
        if (!dateStr || dateStr === 'today' || dateStr === '今天') {
            return {type: 'today', text: '今天'};
        }
        if (dateStr === 'tomorrow' || dateStr === '明天') {
            return {type: 'tomorrow', text: '明天'};
        }
        // 解析 YYYY-MM-DD 格式
        const dateMatch = dateStr.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
        if (dateMatch) {
            const year = parseInt(dateMatch[1]);
            const month = parseInt(dateMatch[2]);
            const day = parseInt(dateMatch[3]);
            const date = new Date(year, month - 1, day);
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            date.setHours(0, 0, 0, 0);
            
            if (date.getTime() === today.getTime()) {
                return {type: 'today', text: '今天', date: date};
            }
            const tomorrow = new Date(today);
            tomorrow.setDate(tomorrow.getDate() + 1);
            if (date.getTime() === tomorrow.getTime()) {
                return {type: 'tomorrow', text: '明天', date: date};
            }
            // 格式化日期为 "M月D日"
            return {type: 'specific', text: month + '月' + day + '日', date: date};
        }
        return {type: 'today', text: '今天'};
    }
    
    try {
        // 等待对话框出现（同步等待）
        let modal = null;
        let attempts = 0;
        while (attempts < 20) {
            modal = document.querySelector('.weui_dialog, .dialog, [class*="modal"], [class*="dialog"]');
            if (modal && modal.offsetParent !== null) {
                break;
            }
            sleep(200);
            attempts++;
        }
        
        if (!modal) {
            return {ok: false, error: '未找到发布对话框'};
        }
        
        // 查找"定时发表"开关
        let scheduledToggle = null;
        const scheduledLabels = modal.querySelectorAll('label, span, div');
        for (const label of scheduledLabels) {
            const text = label.textContent.trim();
            if (text.includes('定时发表') || text.includes('定时发布')) {
                // 查找附近的开关
                let parent = label.parentElement;
                for (let i = 0; i < 3; i++) {
                    if (parent) {
                        const toggle = parent.querySelector('input[type="checkbox"], .switch, [class*="toggle"], [class*="switch"]');
                        if (toggle) {
                            scheduledToggle = toggle;
                            break;
                        }
                        parent = parent.parentElement;
                    }
                }
                if (scheduledToggle) break;
            }
        }
        
        // 如果找不到，尝试通过类名查找
        if (!scheduledToggle) {
            const toggles = modal.querySelectorAll('input[type="checkbox"], .switch, [class*="toggle"]');
            // 通常第二个开关是定时发布
            if (toggles.length >= 2) {
                scheduledToggle = toggles[1];
            }
        }
        
        // 查找"群发通知"开关（第一个开关）
        let groupNotifyToggle = null;
        if (enableGroupNotify !== undefined) {
            const toggles = modal.querySelectorAll('input[type="checkbox"], .switch, [class*="toggle"]');
            if (toggles.length >= 1) {
                groupNotifyToggle = toggles[0];
            }
        }
        
        // 设置群发通知开关
        if (groupNotifyToggle !== null) {
            const isChecked = groupNotifyToggle.checked;
            if (enableGroupNotify && !isChecked) {
                groupNotifyToggle.click();
                sleep(200);
            } else if (!enableGroupNotify && isChecked) {
                groupNotifyToggle.click();
                sleep(200);
            }
        }
        
        // 设置定时发布开关
        if (scheduledToggle) {
            const isChecked = scheduledToggle.checked;
            if (enableScheduled && !isChecked) {
                scheduledToggle.click();
                sleep(300);
                
                // 解析日期
                const dateInfo = parseDate(scheduledDate);
                
                // 设置日期
                if (scheduledDate) {
                    // 查找日期选择器（下拉框或输入框）
                    // 方法1: 查找显示"今天"、"明天"的文本，然后点击
                    const dateLabels = modal.querySelectorAll('span, div, label');
                    for (const label of dateLabels) {
                        const text = label.textContent.trim();
                        if (text === '今天' || text === '明天' || text.match(/^\d{1,2}月\d{1,2}日$/)) {
                            // 检查是否是日期选择器
                            const parent = label.parentElement;
                            if (parent && (parent.classList.contains('dropdown') || parent.querySelector('select') || parent.onclick)) {
                                // 如果目标日期是今天或明天，直接点击
                                if (dateInfo.type === 'today' && text === '今天') {
                                    label.click();
                                    sleep(200);
                                    break;
                                } else if (dateInfo.type === 'tomorrow' && text === '明天') {
                                    label.click();
                                    sleep(200);
                                    break;
                                } else if (dateInfo.type === 'specific' && text === dateInfo.text) {
                                    // 点击打开下拉框
                                    label.click();
                                    sleep(200);
                                    // 在下拉框中查找并点击目标日期
                                    const dropdown = modal.querySelector('.dropdown-menu, [class*="dropdown"], [class*="select"]');
                                    if (dropdown) {
                                        const options = dropdown.querySelectorAll('span, div, li, option');
                                        for (const opt of options) {
                                            if (opt.textContent.trim() === dateInfo.text) {
                                                opt.click();
                                                sleep(200);
                                                break;
                                            }
                                        }
                                    }
                                    break;
                                }
                            }
                        }
                    }
                    
                    // 方法2: 查找日期输入框
                    const dateInputs = modal.querySelectorAll('input[type="date"], input[type="datetime-local"]');
                    if (dateInputs.length > 0 && dateInfo.date) {
                        const input = dateInputs[0];
                        const dateStr = dateInfo.date.toISOString().split('T')[0];
                        if (input.type === 'datetime-local') {
                            input.value = dateStr + 'T' + (scheduledTime || '20:30');
                        } else {
                            input.value = dateStr;
                        }
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        sleep(200);
                    }
                }
                
                // 设置时间
                if (scheduledTime) {
                    // 查找时间输入框
                    const timeInputs = modal.querySelectorAll('input[type="time"], input[placeholder*="时间"], input[placeholder*="时"]');
                    for (const input of timeInputs) {
                        input.value = scheduledTime;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        sleep(200);
                        break;
                    }
                    
                    // 如果找不到时间输入框，尝试查找日期时间选择器
                    const dateTimeInputs = modal.querySelectorAll('input[type="datetime-local"]');
                    for (const input of dateTimeInputs) {
                        if (!input.value) {
                            const today = new Date();
                            const dateStr = today.toISOString().split('T')[0];
                            input.value = dateStr + 'T' + scheduledTime;
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            sleep(200);
                            break;
                        }
                    }
                }
            } else if (!enableScheduled && isChecked) {
                scheduledToggle.click();
                sleep(200);
            }
        } else if (enableScheduled) {
            return {ok: false, error: '未找到定时发布开关'};
        }
        
        return {ok: true, scheduledEnabled: enableScheduled, scheduledDate: scheduledDate, scheduledTime: scheduledTime};
    } catch (e) {
        return {ok: false, error: String(e)};
    }
})
'''


class WeChatPublisher:
    """微信公众号发布器"""
    
    def __init__(
        self,
        user_data_dir: str = "./tmp_profile",
        headless: bool = False,
        editor_url: Optional[str] = None
    ):
        """
        初始化发布器
        
        Args:
            user_data_dir: 浏览器用户数据目录（用于持久化登录态）
            headless: 是否使用无头模式（False 表示显示浏览器窗口）
            editor_url: 编辑器页面 URL（默认使用标准编辑页）
        """
        self.user_data_dir = Path(user_data_dir).absolute()
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.editor_url = editor_url or "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit"
        self.browser_context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        logger.info(f"初始化发布器，用户数据目录: {self.user_data_dir}")
        logger.info(f"编辑器 URL: {self.editor_url}")
    
    def start_browser(self, go_to_home: bool = False, auto_create_new: bool = False) -> bool:
        """
        启动浏览器并打开页面
        
        Args:
            go_to_home: 如果为 True，导航到主页而不是编辑器页面（用于登录检测）
            auto_create_new: 如果为 True，自动点击"新的创作" -> "写新文章"进入编辑页面
        
        Returns:
            是否成功启动
        """
        try:
            playwright = sync_playwright().start()
            self.browser_context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=self.headless,
                args=["--start-maximized"],
                viewport={"width": 1920, "height": 1080}
            )
            self.page = self.browser_context.new_page()
            
            if go_to_home:
                # 导航到主页，便于检测登录状态
                home_url = "https://mp.weixin.qq.com"
                logger.info("正在打开主页...")
                self.page.goto(home_url, wait_until="domcontentloaded")
                time.sleep(3)  # 等待页面加载
                
                # 如果需要自动创建新文章
                if auto_create_new:
                    logger.info("正在自动创建新文章...")
                    if not self._create_new_article():
                        logger.warning("自动创建新文章失败，将尝试直接打开编辑器URL")
                        self.page.goto(self.editor_url, wait_until="domcontentloaded")
            else:
                logger.info("正在打开编辑器页面...")
                self.page.goto(self.editor_url, wait_until="domcontentloaded")
            
            time.sleep(3)  # 等待页面加载
            
            logger.info("页面加载完成")
            return True
        except Exception as e:
            logger.error(f"启动浏览器失败: {e}")
            return False
    
    def _create_new_article(self) -> bool:
        """
        自动点击"新的创作" -> "写新文章"进入编辑页面
        
        Returns:
            是否成功创建新文章并进入编辑页面
        """
        if not self.page:
            return False
        
        try:
            # 等待页面完全加载
            logger.info("等待主页加载完成...")
            time.sleep(3)
            
            # 使用 JavaScript 查找并点击"新的创作"按钮
            js_find_and_click_new_creation = r'''
            (function(){
                // 查找"新的创作"元素
                const texts = ['新的创作', '新创作', 'New Creation'];
                let found = null;
                
                // 方法1: 通过文本内容查找
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    const text = el.textContent.trim();
                    if (texts.some(t => text.includes(t))) {
                        // 检查是否可见且可点击
                        const style = window.getComputedStyle(el);
                        if (el.offsetWidth > 0 && el.offsetHeight > 0 && style.display !== 'none') {
                            // 检查是否包含加号图标或看起来像按钮
                            if (el.tagName === 'BUTTON' || el.tagName === 'A' || 
                                el.onclick || el.classList.contains('card') ||
                                text === '新的创作' || text === '新创作') {
                                found = el;
                                break;
                            }
                        }
                    }
                }
                
                if (!found) {
                    // 方法2: 查找包含加号的元素
                    const plusElements = document.querySelectorAll('[class*="plus"], [class*="add"], [class*="create"]');
                    for (const el of plusElements) {
                        if (el.offsetWidth > 50 && el.offsetHeight > 50) {
                            found = el;
                            break;
                        }
                    }
                }
                
                if (found) {
                    found.click();
                    return {found: true, tag: found.tagName, text: found.textContent.trim()};
                }
                return {found: false};
            })();
            '''
            
            result = self.page.evaluate(js_find_and_click_new_creation)
            logger.info(f"🔍 查找'新的创作'按钮结果: {result}")
            
            if not result.get('found'):
                logger.warning("⚠️ JavaScript 方法未找到'新的创作'按钮，尝试使用 Playwright 选择器...")
                # 备用方案：使用 Playwright 选择器
                new_creation_selectors = [
                    'text=新的创作',
                    'text=新创作',
                    'button:has-text("新的创作")',
                    'div:has-text("新的创作")',
                    'a:has-text("新的创作")'
                ]
                
                clicked = False
                for selector in new_creation_selectors:
                    try:
                        btn = self.page.locator(selector).first
                        if btn.is_visible(timeout=3000):
                            btn.click()
                            logger.info(f"使用 Playwright 点击'新的创作': {selector}")
                            clicked = True
                            break
                    except:
                        continue
                
                if not clicked:
                    logger.error("❌ 所有方法都未找到'新的创作'按钮")
                    logger.error("💡 提示: 请确保已登录并在微信公众号后台主页")
                    return False
            else:
                logger.info(f"✅ 成功点击'新的创作'按钮: {result.get('text')}")
            
            # 等待下拉菜单出现
            logger.info("等待下拉菜单展开...")
            time.sleep(2)
            
            # 直接使用XPath点击"文章"选项（不依赖文字内容，支持多语言）
            xpath_article = '/html/body/div[1]/div/div[4]/div/div/div[2]/div[2]/div[3]/div[2]/div/div[2]'
            logger.info(f"🔍 使用XPath查找'文章'选项: {xpath_article}")
            
            clicked = False
            try:
                # 方法1: 使用 Playwright XPath（优先）
                btn = self.page.locator(f'xpath={xpath_article}').first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    logger.info("✅ 使用 Playwright XPath 点击'文章'选项")
                    clicked = True
                else:
                    logger.warning("⚠️ XPath元素不可见，尝试JavaScript方法...")
            except Exception as e:
                logger.warning(f"⚠️ Playwright XPath 点击失败: {e}，尝试JavaScript方法...")
            
            # 方法2: 使用JavaScript XPath（备用）
            if not clicked:
                js_click_by_xpath = f'''
                (function(){{
                    const xpath = '{xpath_article}';
                    const xpathResult = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                    if (xpathResult.singleNodeValue) {{
                        const el = xpathResult.singleNodeValue;
                        const style = window.getComputedStyle(el);
                        if (el.offsetWidth > 0 && el.offsetHeight > 0 && style.display !== 'none') {{
                            el.click();
                            return {{found: true, method: 'js_xpath'}};
                        }}
                    }}
                    return {{found: false}};
                }})();
                '''
                
                try:
                    result2 = self.page.evaluate(js_click_by_xpath)
                    logger.info(f"🔍 JavaScript XPath 点击结果: {result2}")
                    if result2.get('found'):
                        logger.info("✅ 使用 JavaScript XPath 点击'文章'选项")
                        clicked = True
                except Exception as e:
                    logger.warning(f"⚠️ JavaScript XPath 点击失败: {e}")
            
            # 方法3: 使用class选择器（最后备用，不依赖文字）
            if not clicked:
                try:
                    # 查找第一个 .new-creation__menu-content（通常是文章选项）
                    btn = self.page.locator('.new-creation__menu-content').first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        logger.info("✅ 使用 class 选择器点击第一个菜单项（文章）")
                        clicked = True
                except Exception as e:
                    logger.warning(f"⚠️ Class 选择器点击失败: {e}")
            
            if not clicked:
                logger.error("❌ 所有方法都未找到'文章'选项")
                logger.error("💡 提示: 请确保已点击'新的创作'按钮，下拉菜单已展开")
                logger.error(f"💡 XPath: {xpath_article}")
                return False
            
            # 等待编辑页面加载
            logger.info("等待编辑页面加载...")
            time.sleep(5)
            
            # 检查是否成功进入编辑页面
            current_url = self.page.url
            logger.info(f"当前URL: {current_url}")
            
            if 'appmsg_edit' in current_url or 'editor' in current_url.lower() or 'edit' in current_url.lower():
                logger.info("✅ 成功进入编辑页面")
                return True
            else:
                # 即使URL不对，也检查是否有编辑器元素
                editor_found = self.find_editor(wait_time=5)
                if editor_found.get('found'):
                    logger.info("✅ 找到编辑器元素，已进入编辑页面")
                    return True
                else:
                    logger.warning(f"可能未成功进入编辑页面，当前URL: {current_url}")
                    return False
                
        except Exception as e:
            logger.error(f"自动创建新文章失败: {e}", exc_info=True)
            return False
    
    def check_login(self) -> bool:
        """
        检查是否已登录
        
        Returns:
            是否已登录
        """
        if not self.page:
            return False
        
        try:
            # 等待页面加载
            time.sleep(2)
            
            # 检查是否有"请重新登录"提示
            try:
                login_again = self.page.locator('text=Please Log in again').first
                if login_again.is_visible(timeout=1000):
                    logger.warning("检测到需要重新登录")
                    return False
            except:
                pass
            
            # 检查是否有登录提示或登录按钮
            login_indicators = [
                'text=登录',
                'text=扫码登录',
                'text=Please Log in',
                'text=请登录',
                '.login_container',
                '#login',
                '[class*="login"]'
            ]
            
            for indicator in login_indicators:
                try:
                    element = self.page.locator(indicator).first
                    if element.is_visible(timeout=1000):
                        logger.warning(f"检测到登录界面元素: {indicator}")
                        return False
                except:
                    continue
            
            # 检查是否能找到编辑器相关元素或后台主页
            # 如果能找到这些元素，说明已登录
            logged_in_indicators = [
                '[contenteditable="true"]',
                '[contenteditable=""]',
                '.weui-desktop-editor__inner',
                '.rich_editor',
                '.editor-inner',
                '.appmsg_editor',
                '.js_appmsg_editor',
                '#js_editor1',
                '#editor1',
                '[id*="editor"]',
                'text=素材管理',
                'text=新建',
                'text=发布',
                'text=新的创作',  # 主页的"新的创作"按钮
                'text=新创作',
                '.new-creation__menu-content',  # 下拉菜单
                'text=首页',
                'text=内容',
                '[class*="new-creation"]',  # 新的创作相关元素
                'text=新建消息',
                'text=Input a title here',
                'text=Start text here'
            ]
            
            for indicator in logged_in_indicators:
                try:
                    element = self.page.locator(indicator).first
                    if element.is_visible(timeout=1000):
                        logger.info("检测到已登录状态")
                        return True
                except:
                    continue
            
            # 检查URL，如果在微信公众号后台主页，认为已登录
            current_url = self.page.url
            if 'mp.weixin.qq.com' in current_url:
                # 如果在主页（不是编辑页面），检查是否有"新的创作"按钮
                if 'appmsg_edit' not in current_url:
                    # 尝试查找"新的创作"按钮
                    try:
                        new_creation_btn = self.page.locator('text=新的创作, text=新创作').first
                        if new_creation_btn.is_visible(timeout=2000):
                            logger.info("✅ 已登录（在主页，找到'新的创作'按钮）")
                            return True
                    except:
                        pass
                    # 如果找不到"新的创作"按钮，但URL是微信公众号后台，也认为已登录
                    logger.info("✅ 已登录（在微信公众号后台主页）")
                    return True
                else:
                    # 在编辑页面，尝试查找编辑器
                    found = self.page.evaluate(JS_FIND_EDITOR)
                    if found and found.get('found'):
                        logger.info("✅ 登录状态正常（找到编辑器）")
                        return True
                    else:
                        logger.warning("在编辑页面但未找到编辑器，可能还在加载中")
                        return False
            else:
                logger.warning("不在微信公众号后台页面")
                return False
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False
    
    def wait_for_login(self, timeout: int = 300) -> bool:
        """
        等待用户登录完成
        
        Args:
            timeout: 超时时间（秒）
        
        Returns:
            是否成功登录
        """
        if not self.page:
            return False
        
        logger.info("等待用户登录...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.check_login():
                logger.info("✅ 登录成功！")
                # 等待一下确保登录态已保存
                time.sleep(2)
                return True
            time.sleep(3)  # 每3秒检查一次
        
        logger.warning("等待登录超时")
        return False
    
    def find_editor(self, wait_time: int = 10) -> Dict[str, Any]:
        """
        查找编辑器元素（带等待）
        
        Args:
            wait_time: 等待时间（秒）
        
        Returns:
            查找结果字典
        """
        if not self.page:
            return {"found": False, "error": "页面未初始化"}
        
        # 等待编辑器加载
        logger.info(f"等待编辑器加载（最多 {wait_time} 秒）...")
        start_time = time.time()
        
        while time.time() - start_time < wait_time:
            try:
                result = self.page.evaluate(JS_FIND_EDITOR)
                if result and result.get('found'):
                    logger.info(f"✅ 找到编辑器: {result}")
                    return result
                time.sleep(1)  # 每1秒检查一次
            except Exception as e:
                logger.debug(f"查找编辑器时出错: {e}")
                time.sleep(1)
        
        # 最后一次尝试
        try:
            result = self.page.evaluate(JS_FIND_EDITOR)
            logger.warning(f"编辑器查找结果: {result}")
            return result if result else {"found": False, "error": "超时未找到编辑器"}
        except Exception as e:
            logger.error(f"查找编辑器失败: {e}")
            return {"found": False, "error": str(e)}
    
    def inject_bridge(self) -> bool:
        """
        注入 bridge 到页面
        
        Returns:
            是否成功
        """
        if not self.page:
            return False
        
        try:
            result = self.page.evaluate(JS_INJECT_BRIDGE)
            logger.info(f"Bridge 注入结果: {result}")
            return result
        except Exception as e:
            logger.error(f"注入 bridge 失败: {e}")
            return False
    
    def insert_html(
        self, 
        html: str, 
        clear_first: bool = False,
        title: Optional[str] = None,
        author: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        在编辑器中插入 HTML
        
        Args:
            html: 要插入的 HTML 内容
            clear_first: 是否先清空编辑器
            title: 文章标题（可选，会填充到标题框）
            author: 作者名称（可选，会填充到作者框）
        
        Returns:
            插入结果字典
        """
        if not self.page:
            return {"ok": False, "error": "页面未初始化"}
        
        try:
            # 先查找编辑器，确保能找到
            editor_info = self.find_editor(wait_time=15)
            if not editor_info.get('found'):
                logger.error("无法找到编辑器，无法插入内容")
                return {"ok": False, "error": "编辑器未找到", "editor_info": editor_info}
            
            logger.info(f"编辑器信息: 标题={editor_info.get('title', {}).get('found')}, "
                       f"作者={editor_info.get('author', {}).get('found')}, "
                       f"正文={editor_info.get('content', {}).get('found')}")
            
            # 填充标题和作者
            if title or author:
                title_author_result = self.page.evaluate(JS_SET_TITLE_AUTHOR, title or "", author or "")
                logger.info(f"填充标题和作者: {title_author_result}")
                time.sleep(0.5)
            
            # 注入 bridge
            self.inject_bridge()
            
            # 如果要求先清空
            if clear_first:
                cleared = self.page.evaluate("() => window.__WX_INJECT_BRIDGE__ && window.__WX_INJECT_BRIDGE__.clearEditor()")
                logger.info(f"清空编辑器: {cleared}")
                time.sleep(0.5)
            
            # 方法 A：直接插入
            result = self.page.evaluate(JS_INSERT_AT_CURSOR, html)
            logger.info(f"插入 HTML 结果: {result}")
            
            # 如果失败，尝试通过 bridge
            if not result.get("ok"):
                logger.info("尝试通过 bridge 插入...")
                bridge_result = self.page.evaluate(
                    f"() => window.__WX_INJECT_BRIDGE__ && window.__WX_INJECT_BRIDGE__.pasteHtml({json.dumps(html)})"
                )
                if bridge_result:
                    result = {"ok": True, "method": "bridge"}
                else:
                    result = {"ok": False, "error": "所有插入方法都失败"}
            
            # 验证插入
            if result.get("ok"):
                time.sleep(1)
                editor_html = self.page.evaluate("() => window.__WX_INJECT_BRIDGE__ && window.__WX_INJECT_BRIDGE__.getEditorHtml()")
                if editor_html:
                    logger.info(f"编辑器内容长度: {len(editor_html)} 字符")
                    result["content_length"] = len(editor_html)
            
            return result
        except Exception as e:
            logger.error(f"插入 HTML 失败: {e}")
            return {"ok": False, "error": str(e)}
    
    def get_editor_html(self) -> Optional[str]:
        """
        获取编辑器当前 HTML 内容
        
        Returns:
            HTML 内容，如果获取失败返回 None
        """
        if not self.page:
            return None
        
        try:
            html = self.page.evaluate("() => window.__WX_INJECT_BRIDGE__ && window.__WX_INJECT_BRIDGE__.getEditorHtml()")
            return html
        except Exception as e:
            logger.error(f"获取编辑器内容失败: {e}")
            return None
    
    def find_publish_button(self) -> Dict[str, Any]:
        """
        查找发布按钮
        
        Returns:
            查找结果字典
        """
        if not self.page:
            return {"found": False, "error": "页面未初始化"}
        
        try:
            result = self.page.evaluate(JS_FIND_PUBLISH_BUTTON)
            logger.info(f"发布按钮查找结果: {result}")
            return result
        except Exception as e:
            logger.error(f"查找发布按钮失败: {e}")
            return {"found": False, "error": str(e)}
    
    def publish(
        self, 
        auto_confirm: bool = False,
        scheduled_time: Optional[str] = None,
        scheduled_date: Optional[str] = None,
        enable_group_notify: bool = False
    ) -> Dict[str, Any]:
        """
        发布文章
        
        Args:
            auto_confirm: 是否自动确认（不建议开启，存在风险）
            scheduled_time: 定时发布时间，格式 "HH:MM"，如 "20:30"。如果提供，会自动启用定时发布
            scheduled_date: 定时发布日期，格式 "YYYY-MM-DD" 或 "today" 或 "tomorrow"，如 "2024-12-25"。默认为 "today"
            enable_group_notify: 是否启用群发通知（默认 False）
        
        Returns:
            操作结果字典
        """
        if not self.page:
            return {"ok": False, "error": "页面未初始化"}
        
        try:
            # 查找发布按钮
            button_info = self.find_publish_button()
            if not button_info.get("found"):
                return {"ok": False, "error": "未找到发布按钮"}
            
            # 点击发布按钮
            selector = button_info.get("selector")
            if selector == "text_match":
                # 通过文本匹配点击
                text = button_info.get("text", "")
                self.page.click(f'text="{text}"')
            else:
                try:
                    self.page.click(selector)
                except:
                    # 如果选择器失败，尝试通过文本点击
                    self.page.click(f'text="{button_info.get("text", "发布")}"')
            
            logger.info("已点击发布按钮，等待对话框出现...")
            time.sleep(2)
            
            # 如果设置了定时时间，配置定时发布
            if scheduled_time:
                # 如果没有指定日期，默认为今天
                if not scheduled_date:
                    scheduled_date = "today"
                
                logger.info(f"配置定时发布: {scheduled_date} {scheduled_time}")
                try:
                    # 使用 evaluate 执行 JavaScript 设置定时发布
                    result = self.page.evaluate(
                        JS_SET_SCHEDULED_PUBLISH,
                        True,  # enableScheduled
                        scheduled_date,  # scheduledDate
                        scheduled_time,  # scheduledTime
                        enable_group_notify  # enableGroupNotify
                    )
                    logger.info(f"定时发布配置结果: {result}")
                    if not result.get("ok"):
                        logger.warning(f"定时发布配置失败: {result.get('error')}")
                except Exception as e:
                    logger.warning(f"配置定时发布时出错: {e}")
                    # 继续执行，让用户手动配置
            
            # 查找确认按钮并点击
            if auto_confirm:
                logger.info("查找确认按钮...")
                time.sleep(1)
                
                # 查找确认/发表按钮（绿色按钮）
                confirm_selectors = [
                    'button:has-text("发表")',
                    'button:has-text("确认")',
                    'button:has-text("确定")',
                    'button.btn_primary',
                    'button[class*="primary"]',
                    'button[class*="confirm"]',
                    '.btn_confirm'
                ]
                
                clicked = False
                for btn_sel in confirm_selectors:
                    try:
                        btn = self.page.locator(btn_sel).first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            logger.info(f"已点击确认按钮: {btn_sel}")
                            clicked = True
                            break
                    except:
                        continue
                
                if not clicked:
                    # 尝试查找所有按钮，找到绿色的"发表"按钮
                    try:
                        all_buttons = self.page.locator('button').all()
                        for btn in all_buttons:
                            text = btn.text_content()
                            if text and ('发表' in text or '确认' in text):
                                btn.click()
                                logger.info(f"已点击按钮: {text}")
                                clicked = True
                                break
                    except:
                        pass
                
                if clicked:
                    logger.warning("已自动确认发布（风险操作）")
                    time.sleep(2)
                    return {
                        "ok": True, 
                        "message": "已自动确认发布", 
                        "scheduled_time": scheduled_time,
                        "scheduled_date": scheduled_date
                    }
                else:
                    logger.warning("未找到确认按钮，需要手动确认")
            
            scheduled_info = ""
            if scheduled_time:
                if scheduled_date and scheduled_date != "today":
                    scheduled_info = f"，定时发布时间: {scheduled_date} {scheduled_time}"
                else:
                    scheduled_info = f"，定时发布时间: {scheduled_time}"
            
            return {
                "ok": True, 
                "message": "已点击发布按钮" + scheduled_info + "，请手动确认",
                "scheduled_time": scheduled_time,
                "scheduled_date": scheduled_date
            }
        except Exception as e:
            logger.error(f"发布失败: {e}")
            return {"ok": False, "error": str(e)}
    
    def close(self):
        """关闭浏览器"""
        if self.browser_context:
            try:
                self.browser_context.close()
                logger.info("浏览器已关闭")
            except Exception as e:
                logger.error(f"关闭浏览器失败: {e}")
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start_browser()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


def publish_from_markdown(
    md_file: str,
    user_data_dir: str = "./tmp_profile",
    style: str = "academic_gray",
    headless: bool = False,
    clear_editor: bool = True,
    auto_publish: bool = False,
    scheduled_time: Optional[str] = None,
    scheduled_date: Optional[str] = None,
    enable_group_notify: bool = False
) -> Dict[str, Any]:
    """
    从 Markdown 文件发布到微信公众号
    
    Args:
        md_file: Markdown 文件路径
        user_data_dir: 浏览器用户数据目录
        style: HTML 风格
        headless: 是否使用无头模式
        clear_editor: 是否先清空编辑器
        auto_publish: 是否自动发布（不推荐，存在风险）
        scheduled_time: 定时发布时间，格式 "HH:MM"，如 "20:30"。如果提供，会自动启用定时发布
        scheduled_date: 定时发布日期，格式 "YYYY-MM-DD" 或 "today" 或 "tomorrow"，如 "2024-12-25"。默认为 "today"
        enable_group_notify: 是否启用群发通知（默认 False）
    
    Returns:
        操作结果字典
    """
    try:
        from md2wechat import WeChatHTMLConverter, MarkdownParser
    except ImportError:
        # 如果直接导入失败，尝试从当前包导入
        from .md2wechat import WeChatHTMLConverter, MarkdownParser
    
    # 读取并解析 Markdown 文件，提取标题和作者
    logger.info(f"正在读取 Markdown 文件: {md_file}")
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    parser = MarkdownParser(md_content)
    title = parser.get_front_matter("title", "")
    author = parser.get_front_matter("author", "")
    
    logger.info(f"提取元信息: 标题={title}, 作者={author}")
    
    # 转换 Markdown 为 HTML（只转换正文部分）
    base_dir = str(Path(md_file).parent)
    converter = WeChatHTMLConverter(style=style, base_dir=base_dir)
    html_content = converter.convert(md_file)
    
    logger.info(f"HTML 转换完成，长度: {len(html_content)} 字符")
    
    # 发布
    publisher = WeChatPublisher(user_data_dir=user_data_dir, headless=headless)
    
    try:
        # 先导航到主页检查登录状态
        if not publisher.start_browser(go_to_home=True):
            return {"ok": False, "error": "启动浏览器失败"}
        
        # 检查登录状态
        if not publisher.check_login():
            logger.warning("未登录或登录状态异常，等待登录...")
            # 等待用户登录（最多5分钟）
            if not publisher.wait_for_login(timeout=300):
                logger.error("登录超时，请手动登录后重试")
                return {"ok": False, "error": "登录超时"}
            logger.info("登录成功，继续发布流程...")
        
        # 登录成功后，自动创建新文章进入编辑页面
        logger.info("=" * 60)
        logger.info("步骤 3: 正在自动创建新文章进入编辑页面...")
        logger.info("=" * 60)
        
        if not publisher._create_new_article():
            # 如果自动创建失败，尝试直接打开编辑器URL
            logger.warning("=" * 60)
            logger.warning("步骤 3 失败: 自动创建新文章失败，尝试直接打开编辑器URL...")
            logger.warning("=" * 60)
            try:
                logger.info("步骤 4: 导航到编辑器URL...")
                publisher.page.goto(publisher.editor_url, wait_until="domcontentloaded")
                time.sleep(3)  # 等待页面加载
                logger.info("✅ 编辑器页面加载完成")
            except Exception as e:
                logger.error(f"❌ 导航到编辑器页面失败: {e}")
                return {"ok": False, "error": f"导航到编辑器页面失败: {e}"}
        else:
            logger.info("=" * 60)
            logger.info("✅ 步骤 3 完成: 成功进入编辑页面")
            logger.info("=" * 60)
        
        # 插入 HTML，并填充标题和作者
        logger.info("=" * 60)
        logger.info("步骤 4: 正在插入 HTML 内容并填充标题和作者...")
        logger.info("=" * 60)
        result = publisher.insert_html(
            html_content, 
            clear_first=clear_editor,
            title=title,
            author=author
        )
        
        if not result.get("ok"):
            logger.error(f"❌ 步骤 4 失败: {result.get('error', '未知错误')}")
            return result
        
        logger.info("=" * 60)
        logger.info("✅ 步骤 4 完成: HTML 内容已插入，标题和作者已填充")
        logger.info("=" * 60)
        
        # 如果需要自动发布
        if auto_publish:
            logger.info("=" * 60)
            logger.info("步骤 5: 正在执行自动发布...")
            logger.info("=" * 60)
            publish_result = publisher.publish(
                auto_confirm=False,
                scheduled_time=scheduled_time,
                scheduled_date=scheduled_date,
                enable_group_notify=enable_group_notify
            )
            result["publish"] = publish_result
            if publish_result.get("ok"):
                logger.info("=" * 60)
                logger.info("✅ 步骤 5 完成: 发布操作已执行")
                logger.info("=" * 60)
            else:
                logger.warning(f"⚠️ 步骤 5 警告: {publish_result.get('error', '未知错误')}")
        
        return result
    finally:
        publisher.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python wechat_publisher.py <markdown_file> [--style <style>] [--headless] [--auto-publish]")
        sys.exit(1)
    
    md_file = sys.argv[1]
    style = "academic_gray"
    headless = False
    auto_publish = False
    
    if "--style" in sys.argv:
        idx = sys.argv.index("--style")
        if idx + 1 < len(sys.argv):
            style = sys.argv[idx + 1]
    
    if "--headless" in sys.argv:
        headless = True
    
    if "--auto-publish" in sys.argv:
        auto_publish = True
    
    result = publish_from_markdown(
        md_file=md_file,
        style=style,
        headless=headless,
        auto_publish=auto_publish
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))

