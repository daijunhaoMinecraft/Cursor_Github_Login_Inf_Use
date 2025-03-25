import time
from browser_utils import BrowserManager
from urllib.parse import unquote
import re
import json
import os
from reset_machine import MachineIDResetter
from cursor_auth_manager import CursorAuthManager
import sys

# 设置环境变量，默认使用隐藏模式运行浏览器
os.environ['BROWSER_HEADLESS'] = 'True'

class CursorAuthBot:
    def __init__(self):
        self.browser_manager = BrowserManager()
        self.browser = None
        self.machine_resetter = MachineIDResetter()
        self.auth_manager = CursorAuthManager()
        
    def init_browser(self):
        """初始化浏览器"""
        print("正在初始化浏览器...")
        self.browser = self.browser_manager.init_browser()
        self.tab = self.browser.get_tab()
        
    def get_github_auth_link(self):
        """获取GitHub认证链接"""
        print("正在访问认证页面...")
        self.tab.get("https://authenticator.cursor.sh/")
        time.sleep(3)  # 等待页面加载
        
        print("正在查找GitHub登录按钮...")
        try:
            # 使用XPath精确定位包含GitHub文本的链接
            github_link = self.tab.ele('xpath://a[contains(@class, "rt-Button") and contains(., "Continue with GitHub")]')
            
            if not github_link:
                # 备选方案：使用href属性定位
                github_link = self.tab.ele('xpath://a[contains(@href, "GitHubOAuth")]')
                
            if not github_link:
                # 最后尝试使用组合条件
                github_link = self.tab.ele('xpath://a[contains(@class, "auth-method-button_AuthMethodButton__irESX")]//*[contains(text(), "GitHub")]/ancestor::a')
                
        except Exception as e:
            print(f"查找过程中出错: {e}")
            github_link = None
                
        if not github_link:
            raise Exception("未找到GitHub登录链接")
            
        href = github_link.attr('href')
        if href.startswith('api/'):
            href = 'https://authenticator.cursor.sh/' + href
            
        # 验证是否是GitHub链接
        if 'GitHubOAuth' not in href:
            raise Exception("找到的不是GitHub认证链接")
            
        # 解析redirect_uri
        redirect_uri = re.search(r'redirect_uri=([^&]+)', href)
        if redirect_uri:
            redirect_uri = unquote(redirect_uri.group(1))
            print(f"找到redirect_uri: {redirect_uri}")
            
        print(f"找到GitHub认证链接: {href}")
        return href
        
    def handle_reauthorization(self):
        """处理GitHub重新授权页面"""
        print("等待5秒后检查是否需要重新授权...")
        time.sleep(5)  # 先等待5秒
        
        try:
            # 检查各种可能的元素
            selectors = [
                ('xpath', '//h2[contains(text(), "Reauthorization required")]'),
                ('css', 'button.js-oauth-authorize-btn'),
                ('xpath', '//button[contains(text(), "Authorize getcursor")]'),
                ('xpath', '//button[contains(@class, "btn-primary") and contains(@class, "width-full")]'),
                ('xpath', '//button[contains(@class, "js-oauth-authorize-btn")]'),
                ('xpath', '//div[contains(@class, "Box-footer")]//button[contains(@class, "btn-primary")]')
            ]
            
            for selector_type, selector in selectors:
                try:
                    if selector_type == 'xpath':
                        element = self.tab.ele(f'xpath:{selector}')
                    else:
                        element = self.tab.ele(selector)
                        
                    if element:
                        print(f"找到目标元素: {selector}")
                        if "button" in selector or "btn" in selector:
                            print("找到授权按钮，等待10秒后点击...")
                            time.sleep(10)  # 等待10秒后再点击
                            element.click()
                            print("已点击授权按钮，等待页面跳转...")
                            time.sleep(10)  # 增加等待时间到10秒
                            return True
                except Exception as e:
                    print(f"使用选择器 {selector} 查找元素失败: {e}")
                    continue
                    
            print("未找到需要授权的元素")
            return False
            
        except Exception as e:
            print(f"检查重新授权页面时出错: {e}")
        return False

    def wait_page_load(self, timeout=10):
        """等待页面加载完成"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 检查页面加载状态
                ready_state = self.tab.run_js('return document.readyState')
                if ready_state == 'complete':
                    return True
            except:
                pass
            time.sleep(0.5)
        return False

    def check_page_loading(self):
        """检查页面是否正在加载"""
        try:
            ready_state = self.tab.run_js('return document.readyState')
            return ready_state == 'loading'
        except:
            return False

    def wait_for_auth_completion(self, max_wait_time=60):
        """等待GitHub授权完成"""
        print("等待GitHub授权完成...")
        start_time = time.time()
        last_url = None
        
        while time.time() - start_time < max_wait_time:
            current_url = self.tab.url
            
            # 只在URL变化时打印
            if current_url != last_url:
                print(f"当前页面URL: {current_url}")
                last_url = current_url
                # 当URL变化时，等待页面加载完成
                print("等待页面加载完成...")
                self.wait_page_load()
            
            # 如果已经跳转到cursor.com，直接进入下一步
            if "cursor.com" in current_url:
                print("检测到已成功跳转到Cursor页面")
                return True
            
            # 如果在GitHub页面
            if "github.com" in current_url:
                # 检查是否遇到速率限制
                try:
                    rate_limit_text = self.tab.ele('xpath://p[contains(text(), "You have exceeded a secondary rate limit")]')
                    if rate_limit_text:
                        print("检测到GitHub速率限制提示")
                        print("等待30秒后重试...")
                        time.sleep(30)
                        continue
                except:
                    pass
                
                # 检查是否在授权页面
                if "authorize" in current_url:
                    print("检测到GitHub授权页面，等待页面元素加载...")
                    time.sleep(2)  # 额外等待一下以确保按钮可点击
                    
                    try:
                        # 移除按钮的hover限制
                        js_code = """
                        var style = document.createElement('style');
                        style.innerHTML = `
                            .btn-primary:not(:disabled):hover {
                                background-color: var(--color-btn-primary-bg) !important;
                            }
                            .btn-primary {
                                pointer-events: auto !important;
                                opacity: 1 !important;
                            }
                        `;
                        document.head.appendChild(style);
                        
                        // 移除所有按钮的disabled属性和hover限制
                        document.querySelectorAll('button').forEach(button => {
                            button.disabled = false;
                            button.style.pointerEvents = 'auto';
                            button.style.opacity = '1';
                        });
                        """
                        self.tab.run_js(js_code)
                        print("已移除按钮限制")
                        
                        # 尝试查找并点击授权按钮
                        selectors = [
                            'button.js-oauth-authorize-btn.btn.btn-primary.width-full.ws-normal',
                            'xpath://button[contains(@class, "js-oauth-authorize-btn")]',
                            'xpath://button[contains(text(), "Authorize getcursor")]',
                            'xpath://button[contains(@class, "btn-primary") and contains(@class, "width-full")]',
                            'xpath://div[contains(@class, "Box-footer")]//button[contains(@class, "btn-primary")]'
                        ]
                        
                        for selector in selectors:
                            try:
                                button = self.tab.ele(selector)
                                if button:
                                    print(f"找到授权按钮 [{selector}]")
                                    
                                    # 检查按钮是否被禁用
                                    is_disabled = button.attr('disabled')
                                    if is_disabled:
                                        print("授权按钮当前处于禁用状态，尝试启用...")
                                        # 使用JavaScript启用按钮
                                        self.tab.run_js(f"""
                                            document.querySelector('{selector}').disabled = false;
                                            document.querySelector('{selector}').style.pointerEvents = 'auto';
                                            document.querySelector('{selector}').style.opacity = '1';
                                        """)
                                        time.sleep(1)
                                    
                                    print("等待3秒后点击授权按钮...")
                                    time.sleep(3)
                                    button.click()
                                    print("已点击授权按钮，等待页面响应...")
                                    time.sleep(2)
                                    
                                    # 检查按钮是否还存在
                                    try:
                                        button_still_exists = self.tab.ele(selector)
                                        if button_still_exists:
                                            print("授权按钮仍然存在，尝试再次点击...")
                                            # 再次移除限制并点击
                                            self.tab.run_js(js_code)
                                            time.sleep(1)
                                            button_still_exists.click()
                                            print("已再次点击授权按钮，等待页面响应...")
                                            time.sleep(2)
                                            
                                            # 最后检查按钮是否还存在
                                            try:
                                                if self.tab.ele(selector):
                                                    print("授权按钮依然存在，可能存在问题，等待5秒后继续...")
                                                    time.sleep(5)
                                            except:
                                                print("授权按钮已消失，继续等待跳转...")
                                    except:
                                        print("授权按钮已消失，继续等待跳转...")
                                    
                                    break
                            except Exception as e:
                                print(f"使用选择器 {selector} 查找或点击按钮失败: {e}")
                                continue
                    except Exception as e:
                        print(f"处理授权按钮时出错: {e}")
                
                # 只有在登录页面时才检查登录状态
                elif "login" in current_url and not "oauth" in current_url:
                    print("检测到可能是登录页面，等待页面元素加载...")
                    time.sleep(2)  # 额外等待一下以确保表单加载完成
                    
                    # 检查是否有登录表单
                    login_form = self.tab.ele('xpath://form[contains(@action, "session")]')
                    if login_form:
                        print("检测到GitHub登录页面，用户未登录GitHub")
                        raise Exception("用户未登录GitHub，请先登录后再试")
            
            time.sleep(2)  # 每2秒检查一次
            
        print("等待授权完成超时")
        return False

    def get_cursor_cookies(self, max_retries=5):
        """获取Cursor网站的cookie，最多重试5次"""
        print("正在获取Cursor的cookies...")
        
        # 先等待授权完成
        if not self.wait_for_auth_completion():
            print("授权未完成，无法获取cookies")
            return []
            
        for attempt in range(max_retries):
            print(f"\n=== 第 {attempt + 1} 次尝试获取cookies ===")
            
            # 确保在cursor.com域名下
            if "cursor.com" not in self.tab.url:
                self.tab.get("https://cursor.com")
                print("等待页面加载...")
                time.sleep(5)
            
            # 获取所有cookies并过滤
            all_cookies = self.tab.cookies()
            print(f"获取到 {len(all_cookies)} 个cookies")
            
            # 查找WorkosCursorSessionToken
            for cookie in all_cookies:
                if isinstance(cookie, dict) and cookie.get('name') == 'WorkosCursorSessionToken':
                    print("找到 WorkosCursorSessionToken!")
                    return [cookie]  # 只返回需要的cookie
            
            if attempt < max_retries - 1:  # 如果不是最后一次尝试
                print("未找到 WorkosCursorSessionToken，等待10秒后重试...")
                time.sleep(10)
            else:
                print("已达到最大重试次数，仍未找到 WorkosCursorSessionToken")
                return []
        
        return []

    def send_delete_request(self, cookies):
        """发送删除账号的请求"""
        print("正在发送删除账号请求...")
        url = "https://www.cursor.com/api/dashboard/delete-account"
        
        # 构建cookie字符串
        cookie_str = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])
        
        # 设置请求头
        headers = {
            'Cookie': cookie_str,
            'Content-Type': 'application/json'
        }
        
        # 发送POST请求
        response = self.tab.post(
            url=url,
            data='{}',
            headers=headers
        )
        
        print(f"删除请求响应状态: {response.status_code}")
        print(f"删除请求响应内容: {response.text}")
        return response

    def get_user_info(self, cookies):
        """获取用户信息"""
        print("\n=== 获取用户信息 ===")
        url = "https://www.cursor.com/api/auth/me"
        
        # 构建cookie字符串
        cookie_str = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])
        
        # 设置请求头
        headers = {
            'Cookie': cookie_str,
            'Content-Type': 'application/json'
        }
        
        # 发送GET请求
        self.tab.get(url)  # 先访问页面
        time.sleep(1)  # 等待页面加载
        
        # 获取页面内容
        try:
            page_text = self.tab.run_js('return document.body.innerText')
            print(f"获取到的响应内容: {page_text}")
            user_info = json.loads(page_text)
            print(f"用户信息: {json.dumps(user_info, indent=2, ensure_ascii=False)}")
            return user_info
        except json.JSONDecodeError as e:
            print(f"解析JSON失败: {e}")
            print(f"原始内容: {page_text}")
            return None
        except Exception as e:
            print(f"获取用户信息失败: {e}")
            return None

    def update_auth_info(self, email, cookies):
        """更新认证信息"""
        print("\n=== 更新认证信息 ===")
        # 获取WorkosCursorSessionToken
        session_token = None
        for cookie in cookies:
            if cookie['name'] == 'WorkosCursorSessionToken':
                # 分割token值，获取第二部分
                token_value = cookie['value']
                print(f"找到WorkosCursorSessionToken: {token_value}")
                try:
                    session_token = token_value.split("%3A%3A")[1]
                    print(f"处理后的token: {session_token}")
                except IndexError:
                    print("token格式不正确")
                break
                
        if not session_token:
            print("未找到WorkosCursorSessionToken或token格式不正确")
            return False
            
        # 更新认证信息
        return self.auth_manager.update_auth(
            email=email,
            access_token=session_token,
            refresh_token=session_token
        )
        
    def run(self):
        """运行完整的认证流程"""
        try:
            # 第一次登录
            print("\n=== 第一次登录 ===")
            self.init_browser()
            auth_link = self.get_github_auth_link()
            
            print("正在打开认证链接...")
            self.tab.get(auth_link)
            print("等待页面加载...")
            time.sleep(5)
            
            cookies = self.get_cursor_cookies()
            if cookies:
                print("获取到的cursor.com cookies:")
                print(json.dumps(cookies, indent=2, ensure_ascii=False))
                
                # 发送删除请求
                print("\n=== 发送删除请求 ===")
                response = self.send_delete_request(cookies)
                time.sleep(2)  # 等待请求完成
                
                # 第二次登录
                print("\n=== 第二次登录 ===")
                auth_link = self.get_github_auth_link()
                print("正在打开认证链接...")
                self.tab.get(auth_link)
                print("等待页面加载...")
                time.sleep(5)
                
                # 获取新的cookies（带重试机制）
                new_cookies = self.get_cursor_cookies(max_retries=5)
                if new_cookies:
                    print("获取到的新cursor.com cookies:")
                    print(json.dumps(new_cookies, indent=2, ensure_ascii=False))
                    
                    # 获取用户信息
                    user_info = self.get_user_info(new_cookies)
                    if user_info and 'email' in user_info:
                        # 重置机器码
                        print("\n=== 重置机器码 ===")
                        self.machine_resetter.reset_machine_ids()
                        
                        # 更新认证信息
                        self.update_auth_info(user_info['email'], new_cookies)
                    else:
                        print("未能获取用户邮箱")
                        return False
                else:
                    print("无法获取必要的cookies，程序退出")
                    return False
            else:
                print("没有找到cursor.com相关的cookies")
                return False
            
            return True
            
        finally:
            print("正在关闭浏览器...")
            self.browser_manager.quit()

if __name__ == "__main__":
    bot = CursorAuthBot()
    success = bot.run()
    if not success:
        print("\n程序执行失败！")
        input()
        sys.exit(1)
    else:
        print("\n程序执行成功！") 
        input()