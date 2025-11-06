#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号发表器 - 基于 Playwright

使用 Playwright 控制浏览器，实现微信公众号文章的自动发表。
支持登录态持久化、HTML 插入、定时发表等功能。
"""

import json
import time
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from playwright.sync_api import sync_playwright, BrowserContext, Page, Frame, TimeoutError as PlaywrightTimeoutError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# JavaScript 代码片段 - 查找编辑器（使用四种方法：ID、class、属性、文本）
JS_FIND_EDITOR = r'''
(function findEditorRoot(){
    // 使用四种方法查找：ID -> class -> 属性 -> 文本（类似查找"新的创作"的方式）
    
    // XPath定义（最后备用）
    const xpathTitle = '/html/body/div[2]/div/div/div/div/div[4]/div/div/div[1]/div[3]/div/div[1]/div[3]/div/div/div/div[8]/textarea';
    const xpathAuthor = '/html/body/div[2]/div/div/div/div/div[4]/div/div/div[1]/div[3]/div/div[1]/div[3]/div/div/div/div[10]/input[1]';
    const xpathContent = '/html/body/div[2]/div/div/div/div/div[4]/div/div/div[1]/div[3]/div/div[1]/div[3]/div/div/div/div[13]/div[7]/div[1]';
    
    // XPath查找函数（最后备用）
    function getElementByXPath(xpath) {
        const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
        return result.singleNodeValue;
    }
    
    // 检查元素是否可见
    function isVisible(el) {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        return el.offsetWidth > 0 && el.offsetHeight > 0 && style.display !== 'none';
    }
    
    // 1. 查找标题框（四种方法）
    let titleEl = null;
    let titleMethod = null;
    
    // 方法1: 通过ID查找
    const titleIds = ['js_title_main', 'title', 'js_title', 'article_title'];
    for (const id of titleIds) {
        const el = document.getElementById(id);
        if (el && isVisible(el)) {
            titleEl = el;
            titleMethod = 'id_' + id;
            break;
        }
    }
    
    // 方法2: 通过class查找
    if (!titleEl) {
        const titleClasses = ['.js_title', '.js_title_main', '.article_title', '.title_input', '[class*="title"]'];
        for (const cls of titleClasses) {
            const el = document.querySelector(cls);
            if (el && el.tagName === 'TEXTAREA' && isVisible(el)) {
                titleEl = el;
                titleMethod = 'class_' + cls;
                break;
            }
        }
    }
    
    // 方法3: 通过属性查找
    if (!titleEl) {
        const titleAttrs = [
            'textarea[name="title"]',
            'textarea[placeholder*="标题"]',
            'textarea[placeholder*="title"]',
            'textarea[class*="title"]'
        ];
        for (const attr of titleAttrs) {
            const el = document.querySelector(attr);
            if (el && isVisible(el)) {
                titleEl = el;
                titleMethod = 'attr_' + attr;
                break;
            }
        }
    }
    
    // 方法4: 使用XPath（最后备用）
    if (!titleEl) {
        const el = getElementByXPath(xpathTitle);
        if (el && isVisible(el)) {
            titleEl = el;
            titleMethod = 'xpath';
        }
    }
    
    // 2. 查找作者框（四种方法）
    let authorEl = null;
    let authorMethod = null;
    
    // 方法1: 通过ID查找
    const authorIds = ['author', 'js_author', 'article_author'];
    for (const id of authorIds) {
        const el = document.getElementById(id);
        if (el && isVisible(el)) {
            authorEl = el;
            authorMethod = 'id_' + id;
            break;
        }
    }
    
    // 方法2: 通过class查找
    if (!authorEl) {
        const authorClasses = ['.js_author', '.article_author', '.author_input', '[class*="author"]'];
        for (const cls of authorClasses) {
            const el = document.querySelector(cls);
            if (el && el.tagName === 'INPUT' && isVisible(el)) {
                authorEl = el;
                authorMethod = 'class_' + cls;
                break;
            }
        }
    }
    
    // 方法3: 通过属性查找
    if (!authorEl) {
        const authorAttrs = [
            'input[name="author"]',
            'input[placeholder*="作者"]',
            'input[placeholder*="author"]',
            'input[type="text"][class*="author"]'
        ];
        for (const attr of authorAttrs) {
            const el = document.querySelector(attr);
            if (el && isVisible(el)) {
                authorEl = el;
                authorMethod = 'attr_' + attr;
                break;
            }
        }
    }
    
    // 方法4: 使用XPath（最后备用）
    if (!authorEl) {
        const el = getElementByXPath(xpathAuthor);
        if (el && isVisible(el)) {
            authorEl = el;
            authorMethod = 'xpath';
        }
    }
    
    // 3. 查找正文编辑器（四种方法）
    let contentEditor = null;
    let contentMethod = null;
    
    // 方法1: 通过ID查找（appmsg_content 和 mock-iframe-body）
    const contentIds = ['appmsg_content', 'edui1_contentplaceholder', 'edui1', 'ueditor_0'];
    for (const id of contentIds) {
        const el = document.getElementById(id);
        if (el) {
            // 如果是 appmsg_content，查找内部的 mock-iframe-body
            if (id === 'appmsg_content') {
                const mockBody = el.querySelector('.mock-iframe-body');
                if (mockBody) {
                    const contentEditable = mockBody.querySelector('[contenteditable="true"]');
                    if (contentEditable && isVisible(contentEditable)) {
                        contentEditor = {type:'element', element:contentEditable, selector:'id_appmsg_content'};
                        contentMethod = 'id_appmsg_content';
                        break;
                    }
                }
            }
            // 如果是 placeholder，查找相关的 contenteditable
            else if (id === 'edui1_contentplaceholder') {
                const contentEditable = el.closest('[contenteditable="true"], [contenteditable=""]') ||
                                       el.parentElement?.querySelector('[contenteditable="true"], [contenteditable=""]') ||
                                       el.nextElementSibling?.querySelector('[contenteditable="true"], [contenteditable=""]');
                if (contentEditable && isVisible(contentEditable)) {
                    contentEditor = {type:'element', element:contentEditable, selector:'id_placeholder'};
                    contentMethod = 'id_placeholder';
                    break;
                }
            }
            // 如果是 edui1 或 ueditor_0，查找内部的 contenteditable
            else {
                const contentEditable = el.querySelector('[contenteditable="true"], [contenteditable=""]');
                if (contentEditable && isVisible(contentEditable)) {
                    contentEditor = {type:'element', element:contentEditable, selector:'id_' + id};
                    contentMethod = 'id_' + id;
                    break;
                }
            }
        }
    }
    
    // 方法2: 通过class查找（mock-iframe-body 和 contenteditable）
    if (!contentEditor) {
        const contentClasses = [
            '.mock-iframe-body',
            '.ProseMirror',
            '.edui-editor-body',
            '.edui-editor-content',
            '[class*="edui"]',
            '[class*="editor"]'
        ];
        for (const cls of contentClasses) {
            const el = document.querySelector(cls);
            if (el) {
                let contentEditable = null;
                // 如果是 mock-iframe-body，查找内部的 contenteditable
                if (cls === '.mock-iframe-body') {
                    contentEditable = el.querySelector('[contenteditable="true"]');
                }
                // 如果本身就是 contenteditable
                else if (el.contentEditable === 'true' || el.contentEditable === '') {
                    contentEditable = el;
                }
                // 否则查找子元素
                else {
                    contentEditable = el.querySelector('[contenteditable="true"], [contenteditable=""]');
                }
                
                if (contentEditable && isVisible(contentEditable)) {
                    contentEditor = {type:'element', element:contentEditable, selector:'class_' + cls};
                    contentMethod = 'class_' + cls;
                    break;
                }
            }
        }
    }
    
    // 方法3: 通过属性查找（contenteditable）
    if (!contentEditor) {
        const contentAttrs = [
            '[contenteditable="true"]',
            '[contenteditable=""]',
            '[contenteditable][class*="ProseMirror"]'
        ];
        for (const attr of contentAttrs) {
            const all = document.querySelectorAll(attr);
            for (const el of all) {
                // 优先选择 ProseMirror 或较大的元素
                if (isVisible(el) && (el.classList.contains('ProseMirror') || el.offsetWidth > 300 || el.offsetHeight > 200)) {
                    contentEditor = {type:'element', element:el, selector:'attr_' + attr};
                    contentMethod = 'attr_' + attr;
                    break;
                }
            }
            if (contentEditor) break;
        }
    }
    
    // 方法4: 使用XPath（最后备用）
    if (!contentEditor) {
        const contentEl = getElementByXPath(xpathContent);
        if (contentEl) {
            const contentEditable = contentEl.querySelector('[contenteditable="true"], [contenteditable=""]') || 
                                    (contentEl.contentEditable === 'true' || contentEl.contentEditable === '' ? contentEl : null) ||
                                    contentEl.closest('[contenteditable="true"], [contenteditable=""]');
            
            if (contentEditable && isVisible(contentEditable)) {
                contentEditor = {type:'element', element:contentEditable, selector:'xpath'};
                contentMethod = 'xpath';
            }
        }
    }
    
    // 如果XPath找不到，尝试查找 edui1 相关的 iframe
    if (!contentEditor) {
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
    }
    
    // 如果还是找不到，查找 edui1 相关的 contenteditable
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
    
    // 最后备用：查找所有 contenteditable（找最大的）
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
        title: titleEl ? {found:true, id:titleEl.id, name:titleEl.name, method: titleMethod} : {found:false},
        author: authorEl ? {found:true, id:authorEl.id, name:authorEl.name, method: authorMethod} : {found:false},
        content: contentEditor ? {
            found:true,
            type:contentEditor.type,
            id:contentEditor.element.id || '',
            className:contentEditor.element.className || '',
            method: contentMethod || 'fallback'
        } : {found:false}
    };
})();
'''

# JavaScript 代码片段 - 插入标题和作者（使用四种方法查找）
JS_SET_TITLE_AUTHOR = r'''
(function(args){
    const title = args.title || '';
    const author = args.author || '';
    try {
        // XPath定义（最后备用）
        const xpathTitle = '/html/body/div[2]/div/div/div/div/div[4]/div/div/div[1]/div[3]/div/div[1]/div[3]/div/div/div/div[8]/textarea';
        const xpathAuthor = '/html/body/div[2]/div/div/div/div/div[4]/div/div/div[1]/div[3]/div/div[1]/div[3]/div/div/div/div[10]/input[1]';
        
        // XPath查找函数（最后备用）
        function getElementByXPath(xpath) {
            const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
            return result.singleNodeValue;
        }
        
        // 检查元素是否可见
        function isVisible(el) {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            return el.offsetWidth > 0 && el.offsetHeight > 0 && style.display !== 'none';
        }
        
        // 1. 查找标题框（四种方法）
        let titleEl = null;
        let titleMethod = null;
        
        // 方法1: 通过ID查找
        const titleIds = ['js_title_main', 'title', 'js_title', 'article_title'];
        for (const id of titleIds) {
            const el = document.getElementById(id);
            if (el && isVisible(el)) {
                titleEl = el;
                titleMethod = 'id_' + id;
                break;
            }
        }
        
        // 方法2: 通过class查找
        if (!titleEl) {
            const titleClasses = ['.js_title', '.js_title_main', '.article_title', '.title_input'];
            for (const cls of titleClasses) {
                const el = document.querySelector(cls);
                if (el && el.tagName === 'TEXTAREA' && isVisible(el)) {
                    titleEl = el;
                    titleMethod = 'class_' + cls;
                    break;
                }
            }
        }
        
        // 方法3: 通过属性查找
        if (!titleEl) {
            const titleAttrs = [
                'textarea[name="title"]',
                'textarea[placeholder*="标题"]',
                'textarea[placeholder*="title"]'
            ];
            for (const attr of titleAttrs) {
                const el = document.querySelector(attr);
                if (el && isVisible(el)) {
                    titleEl = el;
                    titleMethod = 'attr_' + attr;
                    break;
                }
            }
        }
        
        // 方法4: 使用XPath（最后备用）
        if (!titleEl) {
            const el = getElementByXPath(xpathTitle);
            if (el && isVisible(el)) {
                titleEl = el;
                titleMethod = 'xpath';
            }
        }
        
        // 2. 查找作者框（四种方法）
        let authorEl = null;
        let authorMethod = null;
        
        // 方法1: 通过ID查找
        const authorIds = ['author', 'js_author', 'article_author'];
        for (const id of authorIds) {
            const el = document.getElementById(id);
            if (el && isVisible(el)) {
                authorEl = el;
                authorMethod = 'id_' + id;
                break;
            }
        }
        
        // 方法2: 通过class查找
        if (!authorEl) {
            const authorClasses = ['.js_author', '.article_author', '.author_input'];
            for (const cls of authorClasses) {
                const el = document.querySelector(cls);
                if (el && el.tagName === 'INPUT' && isVisible(el)) {
                    authorEl = el;
                    authorMethod = 'class_' + cls;
                    break;
                }
            }
        }
        
        // 方法3: 通过属性查找
        if (!authorEl) {
            const authorAttrs = [
                'input[name="author"]',
                'input[placeholder*="作者"]',
                'input[placeholder*="author"]'
            ];
            for (const attr of authorAttrs) {
                const el = document.querySelector(attr);
                if (el && isVisible(el)) {
                    authorEl = el;
                    authorMethod = 'attr_' + attr;
                    break;
                }
            }
        }
        
        // 方法4: 使用XPath（最后备用）
        if (!authorEl) {
            const el = getElementByXPath(xpathAuthor);
            if (el && isVisible(el)) {
                authorEl = el;
                authorMethod = 'xpath';
            }
        }
        
        let result = {title: false, author: false, titleMethod: null, authorMethod: null};
        
        if (titleEl && title) {
            titleEl.value = title;
            titleEl.dispatchEvent(new Event('input', { bubbles: true }));
            titleEl.dispatchEvent(new Event('change', { bubbles: true }));
            result.title = true;
            result.titleMethod = titleMethod;
        }
        
        if (authorEl && author) {
            authorEl.value = author;
            authorEl.dispatchEvent(new Event('input', { bubbles: true }));
            authorEl.dispatchEvent(new Event('change', { bubbles: true }));
            result.author = true;
            result.authorMethod = authorMethod;
        }
        
        return result;
    } catch (e) {
        return {ok: false, error: String(e)};
    }
})
'''

# JavaScript 代码片段 - 在光标处插入 HTML（优先使用ID）
JS_INSERT_AT_CURSOR = r'''
(function(html){
    // 优先使用ID查找编辑器并插入 HTML
    try {
        // XPath定义（备用）
        const xpathContent = '/html/body/div[2]/div/div/div/div/div[4]/div/div/div[1]/div[3]/div/div[1]/div[3]/div/div/div/div[13]/div[7]/div[1]';
        
        // XPath查找函数（备用）
        function getElementByXPath(xpath) {
            const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
            return result.singleNodeValue;
        }
        
        let ed = null;
        
        // 1. 优先通过 edui1_contentplaceholder ID 查找（用户提供的element id）
        const placeholderEl = document.getElementById('edui1_contentplaceholder');
        if (placeholderEl) {
            // 查找父级或兄弟元素中的 contenteditable
            const contentEditable = placeholderEl.closest('[contenteditable="true"], [contenteditable=""]') ||
                                    placeholderEl.parentElement?.querySelector('[contenteditable="true"], [contenteditable=""]') ||
                                    placeholderEl.nextElementSibling?.querySelector('[contenteditable="true"], [contenteditable=""]');
            
            if (contentEditable) {
                const style = window.getComputedStyle(contentEditable);
                if (contentEditable.offsetWidth > 0 && contentEditable.offsetHeight > 0 && style.display !== 'none') {
                    ed = contentEditable;
                }
            }
        }
        
        // 2. 如果方法1失败，查找 edui1 相关的元素（通过ID）
        if (!ed) {
            const edui1El = document.getElementById('edui1') || document.querySelector('[id*="edui1"]');
            if (edui1El) {
                const contentEditable = edui1El.querySelector('[contenteditable="true"], [contenteditable=""]');
                if (contentEditable) {
                    const style = window.getComputedStyle(contentEditable);
                    if (contentEditable.offsetWidth > 0 && contentEditable.offsetHeight > 0 && style.display !== 'none') {
                        ed = contentEditable;
                    }
                }
            }
        }
        
        // 3. 如果ID找不到，查找 edui1 相关的 iframe
        if (!ed) {
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
        }
        
        // 4. 如果还是找不到，使用XPath查找（备用）
        if (!ed) {
            const contentEl = getElementByXPath(xpathContent);
            if (contentEl) {
                const contentEditable = contentEl.querySelector('[contenteditable="true"], [contenteditable=""]') || 
                                        (contentEl.contentEditable === 'true' || contentEl.contentEditable === '' ? contentEl : null) ||
                                        contentEl.closest('[contenteditable="true"], [contenteditable=""]');
                
                if (contentEditable) {
                    const style = window.getComputedStyle(contentEditable);
                    if (contentEditable.offsetWidth > 0 && contentEditable.offsetHeight > 0 && style.display !== 'none') {
                        ed = contentEditable;
                    }
                }
            }
        }
        
        // 5. 如果还是找不到，查找 edui1 相关的元素（class选择器）
        if (!ed) {
            const eduiSelectors = [
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
        
        // 6. 最后兜底：查找所有 contenteditable（找最大的）
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

# JavaScript 代码片段 - 查找并点击发表按钮
JS_FIND_PUBLISH_BUTTON = r'''
(function(){
    // 查找发表相关按钮
    const buttonSelectors = [
        'button:has-text("发表")',
        'button:has-text("群发")',
        'a:has-text("发表")',
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
        if (text === '发表' || text === '群发' || text.includes('发表') || text.includes('群发')) {
            if (btn.offsetParent !== null) {
                return {found: true, selector: 'text_match', text: text};
            }
        }
    }
    
    return {found: false};
})();
'''

# JavaScript 代码片段 - 设置定时发表（同步版本，支持日期选择）
JS_SET_SCHEDULED_PUBLISH = r'''
(function(enableScheduled, scheduledDate, scheduledTime, enableGroupNotify){
    // enableScheduled: 是否启用定时发表
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
            return {ok: false, error: '未找到发表对话框'};
        }
        
        // 查找"定时发表"开关
        let scheduledToggle = null;
        const scheduledLabels = modal.querySelectorAll('label, span, div');
        for (const label of scheduledLabels) {
            const text = label.textContent.trim();
            if (text.includes('定时发表') || text.includes('定时发表')) {
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
            // 通常第二个开关是定时发表
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
        
        // 设置定时发表开关
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
            return {ok: false, error: '未找到定时发表开关'};
        }
        
        return {ok: true, scheduledEnabled: enableScheduled, scheduledDate: scheduledDate, scheduledTime: scheduledTime};
    } catch (e) {
        return {ok: false, error: String(e)};
    }
})
'''


class WeChatPublisher:
    """微信公众号发表器"""
    
    def __init__(
        self,
        user_data_dir: str = "./tmp_profile",
        headless: bool = False,
        editor_url: Optional[str] = None
    ):
        """
        初始化发表器
        
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
        self.editor_frame = None  # UEditor iframe 对象（如果是真正的 iframe）
        self.editor_content_element = None  # 编辑器内容元素（mock-iframe-body 或 contenteditable）
        
        logger.info(f"初始化发表器，用户数据目录: {self.user_data_dir}")
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
            
            # 使用 JavaScript 查找并点击"新的创作"按钮（优先使用ID和class）
            js_find_and_click_new_creation = r'''
            (function(){
                let found = null;
                let method = null;
                
                // 方法1: 通过ID查找（最可靠）
                const possibleIds = ['new-creation', 'newCreation', 'new_creation', 'create-new', 'createNew'];
                for (const id of possibleIds) {
                    const el = document.getElementById(id);
                    if (el) {
                        const style = window.getComputedStyle(el);
                        if (el.offsetWidth > 0 && el.offsetHeight > 0 && style.display !== 'none') {
                            found = el;
                            method = 'id_' + id;
                            break;
                        }
                    }
                }
                
                // 方法2: 通过class查找（new-creation相关）
                if (!found) {
                    const classSelectors = [
                        '.new-creation',
                        '.new-creation__button',
                        '.new-creation__trigger',
                        '[class*="new-creation"]',
                        '[class*="newCreation"]',
                        '[class*="new_creation"]'
                    ];
                    
                    for (const selector of classSelectors) {
                        const el = document.querySelector(selector);
                        if (el) {
                            const style = window.getComputedStyle(el);
                            if (el.offsetWidth > 0 && el.offsetHeight > 0 && style.display !== 'none') {
                                found = el;
                                method = 'class_' + selector;
                                break;
                            }
                        }
                    }
                }
                
                // 方法3: 查找包含加号的元素（通过class）
                if (!found) {
                    const plusElements = document.querySelectorAll('[class*="plus"], [class*="add"], [class*="create"]');
                    for (const el of plusElements) {
                        const style = window.getComputedStyle(el);
                        if (el.offsetWidth > 50 && el.offsetHeight > 50 && style.display !== 'none') {
                            // 检查是否在"新的创作"相关区域
                            const parent = el.closest('[class*="new-creation"], [class*="create"]');
                            if (parent || el.classList.contains('new-creation') || el.closest('.new-creation')) {
                                found = el;
                                method = 'icon_plus';
                                break;
                            }
                        }
                    }
                }
                
                // 方法4: 通过文本内容查找（最后备用，支持多语言）
                if (!found) {
                    const texts = ['新的创作', '新创作', 'New Creation'];
                    const allElements = document.querySelectorAll('button, a, div[role="button"]');
                    for (const el of allElements) {
                        const text = el.textContent.trim();
                        if (texts.some(t => text === t || text.includes(t))) {
                            const style = window.getComputedStyle(el);
                            if (el.offsetWidth > 0 && el.offsetHeight > 0 && style.display !== 'none') {
                                found = el;
                                method = 'text';
                                break;
                            }
                        }
                    }
                }
                
                if (found) {
                    found.click();
                    return {found: true, tag: found.tagName, text: found.textContent.trim(), method: method};
                }
                return {found: false};
            })();
            '''
            
            result = self.page.evaluate(js_find_and_click_new_creation)
            logger.info(f"🔍 查找'新的创作'按钮结果: {result}")
            
            if not result.get('found'):
                logger.warning("⚠️ JavaScript 方法未找到'新的创作'按钮，尝试使用 Playwright 选择器...")
                # 备用方案：使用 Playwright 选择器（优先ID和class）
                new_creation_selectors = [
                    '#new-creation',
                    '#newCreation',
                    '#new_creation',
                    '.new-creation',
                    '.new-creation__button',
                    '[class*="new-creation"]',
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
                            logger.info(f"✅ 使用 Playwright 点击'新的创作': {selector}")
                            clicked = True
                            break
                    except:
                        continue
                
                if not clicked:
                    logger.error("❌ 所有方法都未找到'新的创作'按钮")
                    logger.error("💡 提示: 请确保已登录并在微信公众号后台主页")
                    return False
            else:
                logger.info(f"✅ 成功点击'新的创作'按钮: {result.get('text')} (方法: {result.get('method')})")
            
            # 等待下拉菜单出现
            logger.info("等待下拉菜单展开...")
            time.sleep(2)
            
            # 记录点击前的URL
            initial_url = self.page.url
            logger.info(f"点击前URL: {initial_url}")
            
            # 直接使用XPath点击"文章"选项（不依赖文字内容，支持多语言）
            xpath_article = '/html/body/div[1]/div/div[4]/div/div/div[2]/div[2]/div[3]/div[2]/div/div[2]'
            logger.info(f"🔍 使用XPath查找'文章'选项: {xpath_article}")
            
            clicked = False
            # 监听是否会在新标签页打开（有时会打开新标签）
            new_page_created = False
            try:
                # 方法1: 使用 Playwright XPath（优先）
                # 先监听可能的页面创建事件
                with self.page.context.expect_page(timeout=5000) as new_page_info:
                    btn = self.page.locator(f'xpath={xpath_article}').first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        logger.info("✅ 使用 Playwright XPath 点击'文章'选项")
                        clicked = True
                    else:
                        logger.warning("⚠️ XPath元素不可见，尝试JavaScript方法...")
                        # 取消监听
                        new_page_info = None
            except Exception as e:
                logger.warning(f"⚠️ Playwright XPath 点击失败: {e}，尝试JavaScript方法...")
                new_page_info = None
            
            # 检查是否创建了新页面
            if clicked and new_page_info:
                try:
                    new_page = new_page_info.value
                    if new_page:
                        logger.info("✅ 检测到新标签页打开，切换到新页面")
                        self.page = new_page
                        new_page_created = True
                except:
                    pass
            
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
                    # 监听可能的页面创建
                    with self.page.context.expect_page(timeout=5000) as new_page_info:
                        result2 = self.page.evaluate(js_click_by_xpath)
                        logger.info(f"🔍 JavaScript XPath 点击结果: {result2}")
                        if result2.get('found'):
                            logger.info("✅ 使用 JavaScript XPath 点击'文章'选项")
                            clicked = True
                    # 检查是否创建了新页面
                    if clicked and new_page_info:
                        try:
                            new_page = new_page_info.value
                            if new_page:
                                logger.info("✅ 检测到新标签页打开，切换到新页面")
                                self.page = new_page
                                new_page_created = True
                        except:
                            pass
                except Exception as e:
                    logger.warning(f"⚠️ JavaScript XPath 点击失败: {e}")
            
            # 方法3: 使用class选择器（最后备用，不依赖文字）
            if not clicked:
                try:
                    # 监听可能的页面创建
                    with self.page.context.expect_page(timeout=5000) as new_page_info:
                        # 查找第一个 .new-creation__menu-content（通常是文章选项）
                        btn = self.page.locator('.new-creation__menu-content').first
                        if btn.is_visible(timeout=3000):
                            btn.click()
                            logger.info("✅ 使用 class 选择器点击第一个菜单项（文章）")
                            clicked = True
                    # 检查是否创建了新页面
                    if clicked and new_page_info:
                        try:
                            new_page = new_page_info.value
                            if new_page:
                                logger.info("✅ 检测到新标签页打开，切换到新页面")
                                self.page = new_page
                                new_page_created = True
                        except:
                            pass
                except Exception as e:
                    logger.warning(f"⚠️ Class 选择器点击失败: {e}")
            
            if not clicked:
                logger.error("❌ 所有方法都未找到'文章'选项")
                logger.error("💡 提示: 请确保已点击'新的创作'按钮，下拉菜单已展开")
                logger.error(f"💡 XPath: {xpath_article}")
                return False
            
            # 等待编辑页面加载（等待URL变化）
            logger.info("等待编辑页面加载（等待URL变化）...")
            
            # 记录点击前的URL
            initial_url = self.page.url
            logger.info(f"点击前URL: {initial_url}")
            
            # 等待URL变化到编辑页面（最多等待15秒）
            # 方法1: 等待当前页面URL变化
            url_changed = False
            try:
                # 使用 wait_for_url 等待URL包含 appmsg_edit 或 media/appmsg
                self.page.wait_for_url(
                    lambda url: 'appmsg_edit' in url or 'media/appmsg' in url or 'action=edit' in url,
                    timeout=15000
                )
                url_changed = True
                logger.info(f"✅ URL已变化（wait_for_url）: {self.page.url}")
            except Exception as e:
                logger.warning(f"⚠️ wait_for_url 超时: {e}，尝试轮询检查...")
                # 方法2: 轮询检查URL变化（最多等待15秒）
                for i in range(30):  # 15秒，每0.5秒检查一次
                    time.sleep(0.5)
                    current_url_check = self.page.url
                    if 'appmsg_edit' in current_url_check or 'media/appmsg' in current_url_check or 'action=edit' in current_url_check:
                        url_changed = True
                        logger.info(f"✅ URL已变化（轮询检测）: {current_url_check}")
                        break
                    if current_url_check != initial_url:
                        logger.info(f"🔍 URL已变化但不匹配编辑页面: {current_url_check}")
                        # 即使不完全匹配，也继续等待
                        if i > 10:  # 5秒后如果URL变化了，也认为可能已跳转
                            url_changed = True
                            logger.info("✅ URL已变化（部分匹配）")
                            break
            
            # 检查所有打开的页面，看是否有新标签页
            if not url_changed:
                try:
                    pages = self.page.context.pages
                    for page in pages:
                        page_url = page.url
                        if 'appmsg_edit' in page_url or 'media/appmsg' in page_url or 'action=edit' in page_url:
                            logger.info(f"✅ 在新标签页找到编辑页面: {page_url}")
                            self.page = page
                            url_changed = True
                            break
                except Exception as e:
                    logger.warning(f"⚠️ 检查新标签页失败: {e}")
            
            # 等待页面加载完成
            if url_changed:
                logger.info("等待页面加载完成...")
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                    time.sleep(2)  # 额外等待2秒确保编辑器初始化
                except:
                    time.sleep(3)  # 如果wait_for_load_state失败，至少等待3秒
            
            # 检查当前URL
            current_url = self.page.url
            logger.info(f"当前URL: {current_url}")
            
            # 检查是否成功进入编辑页面
            if 'appmsg_edit' in current_url or 'media/appmsg' in current_url or 'action=edit' in current_url:
                logger.info("✅ 成功进入编辑页面（URL确认）")
                return True
            elif url_changed:
                # URL已变化但可能不是标准的编辑页面URL，检查编辑器元素
                logger.info("✅ URL已变化，检查编辑器元素...")
                editor_found = self.find_editor(wait_time=5)
                if editor_found.get('found'):
                    logger.info("✅ 找到编辑器元素，已进入编辑页面")
                    return True
                else:
                    logger.warning(f"URL已变化但未找到编辑器，当前URL: {current_url}")
                    return False
            else:
                # URL未变化，检查是否有编辑器元素（可能是在当前页面打开）
                logger.info("URL未变化，检查是否有编辑器元素...")
                time.sleep(3)
                editor_found = self.find_editor(wait_time=5)
                if editor_found.get('found'):
                    logger.info("✅ 找到编辑器元素，已进入编辑页面（可能在当前标签页）")
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
                'text=发表',
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
        关键：UEditor 使用的是 mock-iframe，不是真正的 iframe
        需要通过 appmsg_content 和 js_title_main 查找，然后进入 mock-iframe-body
        
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
        
        try:
            # 1. 先查找标题和作者（在主文档）
            title_found = False
            author_found = False
            
            while time.time() - start_time < wait_time:
                try:
                    # 查找标题（四种方法）
                    title_selectors = [
                        '#js_title_main',  # 方法1: ID
                        '#title',
                        '.js_title_main',  # 方法2: class
                        '.js_title',
                        'textarea[name="title"]',  # 方法3: 属性
                        'textarea[placeholder*="标题"]'
                    ]
                    for selector in title_selectors:
                        try:
                            title_el = self.page.locator(selector).first
                            if title_el.is_visible(timeout=2000):
                                title_found = True
                                logger.info(f"✅ 找到标题框: {selector}")
                                break
                        except:
                            continue
                    
                    # 查找作者（四种方法）
                    author_selectors = [
                        '#author',  # 方法1: ID
                        '.js_author',  # 方法2: class
                        'input[name="author"]',  # 方法3: 属性
                        'input[placeholder*="作者"]'
                    ]
                    for selector in author_selectors:
                        try:
                            author_el = self.page.locator(selector).first
                            if author_el.is_visible(timeout=2000):
                                author_found = True
                                logger.info(f"✅ 找到作者框: {selector}")
                                break
                        except:
                            continue
                    
                    if title_found or author_found:
                        break
                except:
                    pass
                time.sleep(1)
            
            # 2. 查找内容编辑器（四种方法）
            logger.info("查找内容编辑器...")
            mock_iframe_body = None
            content_method = None
            
            # 方法1: 通过ID查找
            content_id_selectors = [
                '#appmsg_content .mock-iframe-body',
                '#appmsg_content [contenteditable="true"]',
                '#ueditor_0 .mock-iframe-body',
                '#edui1_contentplaceholder',
                '#edui1 [contenteditable="true"]'
            ]
            for selector in content_id_selectors:
                try:
                    el = self.page.locator(selector).first
                    if el.is_visible(timeout=2000):
                        logger.info(f"✅ 找到内容编辑器（ID方法）: {selector}")
                        mock_iframe_body = el
                        content_method = 'id_' + selector
                        break
                except:
                    continue
            
            # 方法2: 通过class查找
            if not mock_iframe_body:
                content_class_selectors = [
                    '.mock-iframe-body [contenteditable="true"]',
                    '.mock-iframe-body',
                    '.ProseMirror',
                    '.edui-editor-body [contenteditable="true"]',
                    '.edui-editor-content [contenteditable="true"]'
                ]
                for selector in content_class_selectors:
                    try:
                        el = self.page.locator(selector).first
                        if el.is_visible(timeout=2000):
                            logger.info(f"✅ 找到内容编辑器（class方法）: {selector}")
                            mock_iframe_body = el
                            content_method = 'class_' + selector
                            break
                    except:
                        continue
            
            # 方法3: 通过属性查找
            if not mock_iframe_body:
                content_attr_selectors = [
                    '[contenteditable="true"].ProseMirror',
                    '[contenteditable="true"]'
                ]
                for selector in content_attr_selectors:
                    try:
                        # 查找所有，选择最大的或包含 ProseMirror 的
                        all_editors = self.page.locator(selector).all()
                        for el in all_editors:
                            if el.is_visible(timeout=1000):
                                # 优先选择 ProseMirror
                                try:
                                    if 'ProseMirror' in el.get_attribute('class') or '':
                                        mock_iframe_body = el
                                        content_method = 'attr_' + selector + '_ProseMirror'
                                        logger.info(f"✅ 找到内容编辑器（属性方法-ProseMirror）: {selector}")
                                        break
                                except:
                                    pass
                        if mock_iframe_body:
                            break
                    except:
                        continue
                
                # 如果还没找到，选择最大的
                if not mock_iframe_body:
                    try:
                        all_editors = self.page.locator('[contenteditable="true"]').all()
                        max_area = 0
                        max_editor = None
                        for el in all_editors:
                            try:
                                if el.is_visible(timeout=1000):
                                    box = el.bounding_box()
                                    if box:
                                        area = box['width'] * box['height']
                                        if area > max_area:
                                            max_area = area
                                            max_editor = el
                            except:
                                continue
                        if max_editor:
                            mock_iframe_body = max_editor
                            content_method = 'attr_largest'
                            logger.info("✅ 找到内容编辑器（属性方法-最大元素）")
                    except:
                        pass
            
            # 方法4: 使用文本查找（最后备用，查找包含"从这里开始写正文"的区域）
            if not mock_iframe_body:
                try:
                    placeholder = self.page.locator('text=从这里开始写正文').first
                    if placeholder.is_visible(timeout=2000):
                        # 查找附近的 contenteditable
                        parent = placeholder.locator('..')
                        nearby = parent.locator('[contenteditable="true"]').first
                        if nearby.is_visible(timeout=2000):
                            mock_iframe_body = nearby
                            content_method = 'text_placeholder'
                            logger.info("✅ 找到内容编辑器（文本方法）")
                except:
                    pass
            
            if not mock_iframe_body:
                logger.error("❌ 未找到编辑器内容区域")
                return {
                    "found": False,
                    "error": "未找到编辑器内容区域",
                    "title": {"found": title_found},
                    "author": {"found": author_found}
                }
            
            # 4. 保存 mock-iframe-body 元素引用（用于后续操作）
            self.editor_frame = None  # mock-iframe 不是真正的 frame
            self.editor_content_element = mock_iframe_body  # 保存元素引用
            
            logger.info("✅ 编辑器查找完成")
            return {
                "found": True,
                "title": {"found": title_found},
                "author": {"found": author_found},
                "content": {
                    "found": True,
                    "type": "mock-iframe"
                }
            }
            
        except Exception as e:
            logger.error(f"查找编辑器失败: {e}", exc_info=True)
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
        关键：UEditor 编辑器在 iframe 中，需要在 frame 内插入
        
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
            # 先查找编辑器，确保能找到（包括 iframe）
            editor_info = self.find_editor(wait_time=15)
            if not editor_info.get('found'):
                logger.error("无法找到编辑器，无法插入内容")
                return {"ok": False, "error": "编辑器未找到", "editor_info": editor_info}
            
            logger.info(f"编辑器信息: 标题={editor_info.get('title', {}).get('found')}, "
                       f"作者={editor_info.get('author', {}).get('found')}, "
                       f"正文={editor_info.get('content', {}).get('found')}")
            
            # 填充标题和作者（在主文档）
            if title or author:
                title_author_result = self.page.evaluate(JS_SET_TITLE_AUTHOR, {
                "title": title or "",
                "author": author or ""
            })
                logger.info(f"填充标题和作者: {title_author_result}")
                time.sleep(0.5)
            
            # 获取编辑器内容元素（可能是 mock-iframe-body 或 contenteditable）
            content_element = self.editor_content_element
            
            if not content_element:
                logger.error("❌ 未找到编辑器内容元素，尝试重新查找...")
                # 尝试重新查找
                editor_info = self.find_editor(wait_time=5)
                if editor_info.get('found'):
                    content_element = self.editor_content_element
                
                if not content_element:
                    logger.error("❌ 重新查找后仍未找到编辑器内容元素")
                    return {"ok": False, "error": "未找到编辑器内容元素"}
            
            # 在编辑器内容元素中插入 HTML
            logger.info("在编辑器内容区域插入 HTML...")
            
            # JavaScript 代码：在 mock-iframe-body 或 contenteditable 中插入 HTML
            js_insert_in_editor = r'''
            (function(args){
                const html = args.html || '';
                const clearFirst = args.clearFirst || false;
                try {
                    // 查找实际的 contenteditable 元素（可能在 mock-iframe-body 内部）
                    let editor = null;
                    
                    // 方法1: 查找 contenteditable
                    const contenteditables = document.querySelectorAll('[contenteditable="true"]');
                    for (const ed of contenteditables) {
                        // 优先选择 ProseMirror 或包含实际内容的
                        if (ed.classList.contains('ProseMirror') || 
                            ed.offsetWidth > 300 || 
                            ed.offsetHeight > 200) {
                            editor = ed;
                            break;
                        }
                    }
                    
                    // 方法2: 如果当前元素就是 contenteditable
                    if (!editor && document.contentEditable === 'true') {
                        editor = document.body;
                    }
                    
                    // 方法3: 查找 mock-iframe-body 内的 contenteditable
                    if (!editor) {
                        const mockBody = document.querySelector('.mock-iframe-body');
                        if (mockBody) {
                            const ed = mockBody.querySelector('[contenteditable="true"]');
                            if (ed) {
                                editor = ed;
                            }
                        }
                    }
                    
                    if (!editor) {
                        return {ok: false, error: '未找到 contenteditable 编辑器'};
                    }
                    
                    // 聚焦编辑器
                    editor.focus();
                    
                    // 如果要求先清空
                    if (clearFirst) {
                        editor.innerHTML = '';
                    }
                    
                    // 获取 selection 和 range
                    const doc = editor.ownerDocument || document;
                    let sel = doc.getSelection();
                    
                    if (!sel || !sel.rangeCount) {
                        const r = doc.createRange();
                        r.selectNodeContents(editor);
                        r.collapse(false);  // 移动到末尾
                        sel.removeAllRanges();
                        sel.addRange(r);
                        sel = doc.getSelection();
                    }
                    
                    const range = sel.getRangeAt(0);
                    
                    try {
                        // 方法1: 使用 createContextualFragment（最可靠）
                        const frag = range.createContextualFragment(html);
                        range.deleteContents();
                        range.insertNode(frag);
                        
                        // 将光标移动到插入内容后面
                        // 确保 fragment 有子节点
                        if (frag.lastChild) {
                            range.setStartAfter(frag.lastChild);
                        } else if (frag.firstChild) {
                            range.setStartAfter(frag.firstChild);
                        } else {
                            // 如果 fragment 为空，尝试移动到编辑器末尾
                            range.selectNodeContents(editor);
                            range.collapse(false);
                        }
                        range.collapse(true);
                        sel.removeAllRanges();
                        sel.addRange(range);
                        
                        // 触发输入事件
                        editor.dispatchEvent(new Event('input', { bubbles: true }));
                        editor.dispatchEvent(new Event('change', { bubbles: true }));
                        
                        return {ok: true, method: 'createContextualFragment', bodyLength: editor.innerHTML.length, editorTag: editor.tagName, editorClass: editor.className};
                    } catch (e1) {
                        console.log('方法1失败:', e1);
                        try {
                            // 方法2: 使用 insertAdjacentHTML（备用）
                            // 先获取光标位置
                            const range2 = doc.createRange();
                            range2.selectNodeContents(editor);
                            range2.collapse(false);
                            
                            // 在末尾插入HTML
                            editor.insertAdjacentHTML('beforeend', html);
                            
                            // 将光标移动到插入内容后面
                            range2.selectNodeContents(editor);
                            range2.collapse(false);
                            sel.removeAllRanges();
                            sel.addRange(range2);
                            
                            // 触发输入事件
                            editor.dispatchEvent(new Event('input', { bubbles: true }));
                            editor.dispatchEvent(new Event('change', { bubbles: true }));
                            
                            return {ok: true, method: 'insertAdjacentHTML', bodyLength: editor.innerHTML.length, editorTag: editor.tagName, editorClass: editor.className};
                        } catch (e2) {
                            console.log('方法2失败:', e2);
                            try {
                                // 方法3: 直接追加（最后备用）
                                const tempDiv = doc.createElement('div');
                                tempDiv.innerHTML = html;
                                
                                // 将内容追加到编辑器
                                while (tempDiv.firstChild) {
                                    editor.appendChild(tempDiv.firstChild);
                                }
                                
                                // 将光标移动到末尾
                                const range3 = doc.createRange();
                                range3.selectNodeContents(editor);
                                range3.collapse(false);
                                sel.removeAllRanges();
                                sel.addRange(range3);
                                
                                // 触发输入事件
                                editor.dispatchEvent(new Event('input', { bubbles: true }));
                                editor.dispatchEvent(new Event('change', { bubbles: true }));
                                
                                return {ok: true, method: 'appendChild', bodyLength: editor.innerHTML.length, editorTag: editor.tagName, editorClass: editor.className};
                            } catch (e3) {
                                console.log('方法3失败:', e3);
                                return {ok: false, error: '所有插入方法都失败: ' + String(e1) + '; ' + String(e2) + '; ' + String(e3)};
                            }
                        }
                    }
                } catch (e) {
                    return {ok: false, error: String(e)};
                }
            })
            '''
            
            # 在页面中执行插入（mock-iframe-body 在主文档中，不是真正的 iframe）
            result = self.page.evaluate(js_insert_in_editor, {
                "html": html,
                "clearFirst": clear_first
            })
            logger.info(f"✅ 编辑器内容区域插入 HTML 结果: {result}")
            
            if result.get("ok"):
                time.sleep(1)
                # 验证插入：获取编辑器内的 HTML
                try:
                    editor_html = self.page.evaluate('''
                        () => {
                            const editor = document.querySelector('[contenteditable="true"].ProseMirror, [contenteditable="true"]');
                            return editor ? editor.innerHTML : '';
                        }
                    ''')
                    if editor_html:
                        logger.info(f"✅ 编辑器内容长度: {len(editor_html)} 字符")
                        result["content_length"] = len(editor_html)
                except Exception as e:
                    logger.warning(f"获取编辑器内容时出错: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"插入 HTML 失败: {e}", exc_info=True)
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
        查找发表按钮
        
        Returns:
            查找结果字典
        """
        if not self.page:
            return {"found": False, "error": "页面未初始化"}
        
        try:
            result = self.page.evaluate(JS_FIND_PUBLISH_BUTTON)
            logger.info(f"发表按钮查找结果: {result}")
            return result
        except Exception as e:
            logger.error(f"查找发表按钮失败: {e}")
            return {"found": False, "error": str(e)}
    
    def publish(
        self, 
        auto_confirm: bool = False,
        scheduled_time: Optional[str] = None,
        scheduled_date: Optional[str] = None,
        enable_group_notify: bool = False
    ) -> Dict[str, Any]:
        """
        发表文章
        
        Args:
            auto_confirm: 是否自动确认（不建议开启，存在风险）
            scheduled_time: 定时发表时间，格式 "HH:MM"，如 "20:30"。如果提供，会自动启用定时发表
            scheduled_date: 定时发表日期，格式 "YYYY-MM-DD" 或 "today" 或 "tomorrow"，如 "2024-12-25"。默认为 "today"
            enable_group_notify: 是否启用群发通知（默认 False）
        
        Returns:
            操作结果字典
        """
        if not self.page:
            return {"ok": False, "error": "页面未初始化"}
        
        try:
            # 查找发表按钮
            button_info = self.find_publish_button()
            if not button_info.get("found"):
                return {"ok": False, "error": "未找到发表按钮"}
            
            # 点击发表按钮
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
                    self.page.click(f'text="{button_info.get("text", "发表")}"')
            
            logger.info("已点击发表按钮，等待对话框出现...")
            time.sleep(2)
            
            # 如果设置了定时时间，配置定时发表
            if scheduled_time:
                # 如果没有指定日期，默认为今天
                if not scheduled_date:
                    scheduled_date = "today"
                
                logger.info(f"配置定时发表: {scheduled_date} {scheduled_time}")
                try:
                    # 使用 evaluate 执行 JavaScript 设置定时发表
                    result = self.page.evaluate(
                        JS_SET_SCHEDULED_PUBLISH,
                        True,  # enableScheduled
                        scheduled_date,  # scheduledDate
                        scheduled_time,  # scheduledTime
                        enable_group_notify  # enableGroupNotify
                    )
                    logger.info(f"定时发表配置结果: {result}")
                    if not result.get("ok"):
                        logger.warning(f"定时发表配置失败: {result.get('error')}")
                except Exception as e:
                    logger.warning(f"配置定时发表时出错: {e}")
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
                    logger.warning("已自动确认发表（风险操作）")
                    time.sleep(2)
                    return {
                        "ok": True, 
                        "message": "已自动确认发表", 
                        "scheduled_time": scheduled_time,
                        "scheduled_date": scheduled_date
                    }
                else:
                    logger.warning("未找到确认按钮，需要手动确认")
            
            scheduled_info = ""
            if scheduled_time:
                if scheduled_date and scheduled_date != "today":
                    scheduled_info = f"，定时发表时间: {scheduled_date} {scheduled_time}"
                else:
                    scheduled_info = f"，定时发表时间: {scheduled_time}"
            
            return {
                "ok": True, 
                "message": "已点击发表按钮" + scheduled_info + "，请手动确认",
                "scheduled_time": scheduled_time,
                "scheduled_date": scheduled_date
            }
        except Exception as e:
            logger.error(f"发表失败: {e}")
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
    从 Markdown 文件发表到微信公众号
    
    Args:
        md_file: Markdown 文件路径
        user_data_dir: 浏览器用户数据目录
        style: HTML 风格
        headless: 是否使用无头模式
        clear_editor: 是否先清空编辑器
        auto_publish: 是否自动发表（不推荐，存在风险）
        scheduled_time: 定时发表时间，格式 "HH:MM"，如 "20:30"。如果提供，会自动启用定时发表
        scheduled_date: 定时发表日期，格式 "YYYY-MM-DD" 或 "today" 或 "tomorrow"，如 "2024-12-25"。默认为 "today"
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
    
    # 发表
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
            logger.info("登录成功，继续发表流程...")
        
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
        
        # 如果需要自动发表
        if auto_publish:
            logger.info("=" * 60)
            logger.info("步骤 5: 正在执行自动发表...")
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
                logger.info("✅ 步骤 5 完成: 发表操作已执行")
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

