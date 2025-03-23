from DrissionPage import ChromiumOptions, Chromium
import sys
import os
import logging
from dotenv import load_dotenv

load_dotenv()


class BrowserManager:
    def __init__(self):
        self.browser = None

    def init_browser(self, user_agent=None):
        """初始化浏览器"""
        co = self._get_browser_options(user_agent)
        self.browser = Chromium(co)
        return self.browser

    def _get_browser_options(self, user_agent=None):
        """获取浏览器配置"""
        co = ChromiumOptions()
        
        # 设置Chrome路径
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome_path):
            print(f"使用系统Chrome: {chrome_path}")
            co.set_paths(browser_path=chrome_path)
        
        try:
            extension_path = self._get_extension_path("turnstilePatch")
            co.add_extension(extension_path)
        except FileNotFoundError as e:
            logging.warning(f"警告: {e}")

        # 设置用户配置文件路径
        user_data_dir = os.path.expanduser('~') + r'\AppData\Local\Google\Chrome\User Data'
        if os.path.exists(user_data_dir):
            print(f"使用默认Chrome配置文件: {user_data_dir}")
            # 使用Windows路径格式，不要给路径加引号
            co.set_argument(f'--user-data-dir={user_data_dir}')
            co.set_argument('--profile-directory=Default')
            co.set_argument('--enable-sync')
            co.set_argument('--no-first-run')
            co.set_argument('--no-default-browser-check')
            co.set_argument('--disable-web-security')
            co.set_argument('--remote-debugging-port=0')

        co.set_pref("credentials_enable_service", True)
        co.set_pref("profile.password_manager_enabled", True)
        co.set_argument("--hide-crash-restore-bubble")
        
        proxy = os.getenv("BROWSER_PROXY")
        if proxy:
            co.set_proxy(proxy)

        if user_agent:
            co.set_user_agent(user_agent)

        co.headless(
            os.getenv("BROWSER_HEADLESS", "True").lower() == "true"
        )

        # Mac 系统特殊处理
        if sys.platform == "darwin":
            co.set_argument("--no-sandbox")
            co.set_argument("--disable-gpu")

        return co

    def _get_extension_path(self,exname='turnstilePatch'):
        """获取插件路径"""
        root_dir = os.getcwd()
        extension_path = os.path.join(root_dir, exname)

        if hasattr(sys, "_MEIPASS"):
            extension_path = os.path.join(sys._MEIPASS, exname)

        if not os.path.exists(extension_path):
            raise FileNotFoundError(f"插件不存在: {extension_path}")

        return extension_path

    def quit(self):
        """关闭浏览器"""
        if self.browser:
            try:
                self.browser.quit()
            except:
                pass
