#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import time
import shutil
import warnings
import logging
from pathlib import Path

# 完全禁用所有警告
warnings.filterwarnings("ignore")
os.environ['PYTHONWARNINGS'] = 'ignore'

# 禁用各种日志
logging.getLogger('selenium').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('undetected_chromedriver').setLevel(logging.ERROR)

def ensure_uc():
    try:
        import undetected_chromedriver as uc
        return uc
    except ImportError:
        print("🔧 未安装 undetected-chromedriver，正在自动安装…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "setuptools", "packaging"], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "undetected_chromedriver", "selenium"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for i in range(3, 0, -1):
            print_single_line(f"🔧 安装完成，{i} 秒后重启脚本…")
            time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

uc = ensure_uc()

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import InvalidArgumentException, WebDriverException, TimeoutException

def find_browser_binary(preferred="chrome") -> str:
    """
    查找浏览器二进制文件：严格区分 Chrome/Edge，避免路径混淆。
    支持环境变量 BROWSER_PATH 覆盖。
    """
    env_path = os.environ.get("BROWSER_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    candidates = {}
    if sys.platform.startswith("win"):
        candidates = {
            "chrome": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files\Chromium\Application\chrome.exe",
            ],
            "edge": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ]
        }
        # Windows: 只查对应命令，避免混淆
        if preferred == "chrome":
            path = shutil.which("chrome")
            if path and "msedge" not in path.lower():
                return path
        elif preferred == "edge":
            path = shutil.which("msedge")
            if path:
                return path
    elif sys.platform.startswith("linux"):
        candidates = {
            "chrome": ["google-chrome", "chrome", "chromium", "chromium-browser"],
            "edge": ["microsoft-edge", "msedge"]
        }
    elif sys.platform.startswith("darwin"):
        candidates = {
            "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                       "/Applications/Chromium.app/Contents/MacOS/Chromium"],
            "edge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
        }

    # 检查 candidates 中的路径
    if preferred in candidates:
        for name in candidates[preferred]:
            if shutil.which(name) or Path(name).exists():
                return str(name) if isinstance(name, Path) else name

    return None

def countdown(seconds: int, prefix: str = ""):
    for i in range(seconds, 0, -1):
        print_single_line(f"{prefix}{i} 秒…")
        time.sleep(1)
    clear_single_line()

def build_chrome_options_simple():
    """
    构建极简 Chrome 选项，避免兼容性问题
    """
    options = uc.ChromeOptions()
    
    # 极简参数设置
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-translate")
    
    # 性能参数
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # 反检测
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    return options

def build_chrome_options_advanced():
    """
    构建高级 Chrome 选项，包含更多优化
    """
    options = uc.ChromeOptions()
    
    # 基础参数
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-popup-blocking")
    
    # 性能优化
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-software-rasterizer")
    
    # 反检测
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 实验性选项 - 使用更安全的方式
    try:
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
    except:
        pass
    
    return options

def build_edge_options():
    options = webdriver.EdgeOptions()
    
    # 基础参数
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 禁用日志
    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    return options

def start_driver_with_fallback(profile_dir: str = None, fast_mode: bool = False):
    """
    启动驱动：优先 Chrome（undetected），失败/无则回退 Edge（标准）。
    """
    chrome_bin = find_browser_binary("chrome")
    # 额外检查：确保不是 Edge 路径伪装
    if chrome_bin and "msedge" in chrome_bin.lower():
        print("⚠️ 检测到路径疑似 Edge，强制切换到 Edge 模式。")
        chrome_bin = None

    # Chrome 尝试 - 使用全新的启动策略
    if chrome_bin:
        attempts = [
            {"name": "极简模式", "builder": build_chrome_options_simple},
            {"name": "高级模式", "builder": build_chrome_options_advanced},
        ]
        
        for attempt in attempts:
            try:
                start_ts = time.time()
                print_single_line(f"🔧 启动 Chrome（{attempt['name']}）...")
                
                # 构建选项
                options = attempt['builder']()
                options.binary_location = chrome_bin
                
                # 处理用户数据目录
                if profile_dir:
                    options.add_argument(f"--user-data-dir={profile_dir}")
                else:
                    # 使用临时目录避免冲突
                    import tempfile
                    temp_profile = tempfile.mkdtemp()
                    options.add_argument(f"--user-data-dir={temp_profile}")
                
                # 禁用日志输出
                options.add_argument("--log-level=3")
                options.add_argument("--silent")
                
                # 使用最简化的启动方式
                driver = uc.Chrome(
                    options=options,
                    version_main=None,
                    headless=False,
                    log_level=0  # 禁用 undetected_chromedriver 日志
                )
                
                elapsed = time.time() - start_ts
                clear_single_line()
                print(f"✅ Chrome 启动成功（{attempt['name']}），耗时 {elapsed:.1f} 秒")
                
                # 反检测
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                return driver, "chrome"
                
            except Exception as e:
                clear_single_line()
                err_msg = str(e).splitlines()[0] if len(str(e).splitlines()) > 0 else str(e)
                print(f"❌ Chrome 启动失败（{attempt['name']}）: {err_msg}")
                
                # 如果不是最后一次尝试，等待一下再重试
                if attempt != attempts[-1]:
                    print_single_line("🔄 准备下一次尝试...")
                    time.sleep(2)
                    clear_single_line()
                continue

        print("🔄 所有 Chrome 尝试失败，切换到 Edge...")

    # Edge 回退
    edge_bin = find_browser_binary("edge")
    if edge_bin:
        options = build_edge_options()
        options.binary_location = edge_bin
        
        if profile_dir:
            options.add_argument(f"--user-data-dir={profile_dir}")

        try:
            start_ts = time.time()
            print_single_line("🔧 启动 Edge ...")
            
            # 禁用 Edge 服务日志
            from selenium.webdriver.edge.service import Service
            service = Service(log_path=os.devnull)
            
            driver = webdriver.Edge(options=options, service=service)
            
            # 反检测
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            elapsed = time.time() - start_ts
            clear_single_line()
            print(f"✅ Edge 启动成功，耗时 {elapsed:.1f} 秒")
            return driver, "edge"
        except Exception as e:
            clear_single_line()
            err_msg = str(e).splitlines()[0] if len(str(e).splitlines()) > 0 else str(e)
            print(f"❌ Edge 启动失败: {err_msg}")
            raise RuntimeError("Edge 启动失败。") from e
    else:
        raise RuntimeError("❌ 未检测到 Chrome 或 Edge！")

# ---------------- 单行覆盖输出 ----------------
def _get_term_width(default: int = 120):
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return default

def print_single_line(msg: str):
    """
    单行输出，清除当前行后输出新内容
    """
    msg = msg.replace("\n", " ")
    width = _get_term_width(120)
    
    if len(msg) > width - 3:
        msg = msg[:width - 3] + "..."
    
    try:
        sys.stdout.write("\x1b[2K\x1b[0G")
        sys.stdout.write(msg)
        sys.stdout.flush()
    except Exception:
        try:
            pad = max(0, width - len(msg))
            sys.stdout.write("\r" + msg + " " * pad)
            sys.stdout.flush()
        except Exception:
            print(msg)

def clear_single_line():
    """清除当前行内容"""
    try:
        sys.stdout.write("\x1b[2K\x1b[0G")
        sys.stdout.flush()
    except Exception:
        try:
            width = _get_term_width(120)
            sys.stdout.write("\r" + " " * width + "\r")
            sys.stdout.flush()
        except Exception:
            pass

# ---------------- 主逻辑 ----------------
def unblock_all_via_browser() -> None:
    print("🚀 启动浏览器，请手动登录 Roblox …")

    profile_dir = os.environ.get("PROFILE_DIR")
    fast_mode = os.environ.get("FAST_MODE", "0") == "1"
    page_load_timeout = 30 if fast_mode else 60
    implicit_wait = 2 if fast_mode else 3

    try:
        driver, browser_type = start_driver_with_fallback(profile_dir=profile_dir, fast_mode=fast_mode)
    except Exception as e:
        print("❌ 无法启动浏览器。建议：")
        print("  🔧 检查浏览器是否已安装")
        print("  🔧 尝试设置 BROWSER_PATH 环境变量")
        print("  🔧 关闭所有浏览器实例后重试")
        raise

    try:
        driver.set_page_load_timeout(page_load_timeout)
        driver.implicitly_wait(implicit_wait)

        target_login = "https://www.roblox.com/login"
        nav_start_ts = time.time()
        print_single_line("🌐 导航到登录页面...")
        try:
            driver.get(target_login)
        except Exception as e:
            print_single_line("⚠️ 导航超时，使用 JS 跳转...")
            driver.execute_script("window.location.href = arguments[0];", target_login)
        nav_time = time.time() - nav_start_ts
        clear_single_line()
        print(f"✅ 导航完成，耗时 {nav_time:.1f} 秒（使用 {browser_type.upper()}）")

        # ===== 登录等待：每十秒更新一次 ======
        max_login_wait = 300 if not fast_mode else 120
        start_wait = time.time()
        end_time = start_wait + max_login_wait
        logged_in = False
        last_update_time = 0
        update_interval = 10

        # 立即检查一次
        try:
            if driver.find_elements(By.CSS_SELECTOR, "meta[data-userid]"):
                logged_in = True
        except Exception:
            pass

        while not logged_in and time.time() < end_time:
            current_time = time.time()
            remaining = int(end_time - current_time)
            
            if current_time - last_update_time >= update_interval or remaining <= 10:
                print_single_line(f"🔑 登录中... 剩余 {remaining} 秒")
                last_update_time = current_time
            
            try:
                if driver.find_elements(By.CSS_SELECTOR, "meta[data-userid]"):
                    logged_in = True
                    break
            except Exception:
                pass
            time.sleep(1)

        clear_single_line()

        if not logged_in:
            print(f"⏰ 超时：在 {max_login_wait} 秒内未检测到登录")
            return
        else:
            print("✅ 登录成功，准备解除屏蔽...")

        # 等待页面加载
        print_single_line("🔄 加载解除页面...")
        round_no = 0
        max_rounds = 20
        
        while round_no < max_rounds:
            round_no += 1
            driver.execute_script("window.location.href = arguments[0];", "https://www.roblox.com/my/account#!/privacy/BlockedUsers")
            
            # 等待页面加载完成
            load_start = time.time()
            page_loaded = False
            while time.time() - load_start < 15:
                try:
                    WebDriverWait(driver, 3).until(
                        EC.any_of(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "button.user-blocking-btn")),
                            EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'尚无已屏蔽用户') or contains(text(),'No users blocked')]"))
                        )
                    )
                    page_loaded = True
                    break
                except TimeoutException:
                    print_single_line(f"🔄 等待页面加载... {int(time.time() - load_start)}秒")
                    continue
            
            clear_single_line()
            
            if not page_loaded:
                print("⚠️ 页面加载超时，刷新重试...")
                driver.refresh()
                time.sleep(2)
                continue

            # 检查是否为空列表
            empty = driver.find_elements(By.XPATH, "//*[contains(text(),'尚无已屏蔽用户') or contains(text(),'No users blocked')]")
            if empty:
                print_single_line("👻 列表为空，5秒后重试…")
                countdown(5, prefix="👻 重试倒计时 ")
                driver.refresh()
                time.sleep(2)
                empty = driver.find_elements(By.XPATH, "//*[contains(text(),'尚无已屏蔽用户') or contains(text(),'No users blocked')]")
                if empty:
                    print("🎉 确认列表已空，任务完成！")
                    break
                continue

            btns = driver.find_elements(By.CSS_SELECTOR, "button.user-blocking-btn")
            if not btns:
                print("🎉 无解除按钮，任务完成！")
                break

            total = len(btns)
            print(f"🔄 第 {round_no} 轮，发现 {total} 个屏蔽用户")

            # 单行进度更新
            processed_count = 0
            for idx, btn in enumerate(btns, 1):
                print_single_line(f"🔄 [{idx}/{total}] 解除中...")
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    confirm = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.modal-half-width-button.btn-primary-md"))
                    )
                    driver.execute_script("arguments[0].click();", confirm)
                    processed_count += 1
                    print_single_line(f"✅ [{idx}/{total}] 已解除 ({processed_count}/{total})")
                except Exception as e:
                    err_short = str(e).splitlines()[0] if str(e).splitlines() else str(e)
                    print_single_line(f"❌ [{idx}/{total}] 失败: {err_short}")
                time.sleep(0.5)

            # 本轮结束
            clear_single_line()
            if processed_count > 0:
                print(f"✅ 第 {round_no} 轮完成，成功解除 {processed_count}/{total} 个用户")
            else:
                print(f"⚠️ 第 {round_no} 轮完成，但未能解除任何用户")
            
            driver.refresh()
            time.sleep(1)

        if round_no >= max_rounds:
            print("⚠️ 已达到最大轮次限制，任务终止")

    finally:
        try:
            print_single_line("🔄 关闭浏览器...")
            driver.quit()
            clear_single_line()
            print("✅ 浏览器已关闭")
        except Exception:
            print("⚠️ 关闭浏览器时出现异常")

def main():
    try:
        unblock_all_via_browser()
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断，已退出")
    except Exception as e:
        print(f"❌ 脚本异常结束: {e}")
    input("⏎ 按回车键退出…")

if __name__ == "__main__":
    main()