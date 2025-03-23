import sys
import time
import json
from datetime import datetime
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (NavigationInterface, NavigationItemPosition, MessageBox,
                          PushButton, ProgressBar, TextEdit, InfoBar, InfoBarPosition,
                          FluentIcon, isDarkTheme, CardWidget, SwitchButton, 
                          TitleLabel, StrongBodyLabel, SettingCardGroup, SwitchSettingCard,
                          qconfig, ConfigItem, QConfig)
from qfluentwidgets import FluentWindow, SubtitleLabel, setTheme, Theme, NavigationWidget
from cursor_auth import CursorAuthBot

# 创建配置项
class Config(QConfig):
    darkMode = ConfigItem("Theme", "DarkMode", False)

# 初始化配置
qconfig.load('config.json', Config)

class AuthWorker(QThread):
    """认证工作线程"""
    progress_updated = pyqtSignal(str, int)  # 进度信息和百分比
    finished = pyqtSignal(bool, str)  # 成功/失败状态和消息
    log_updated = pyqtSignal(str)  # 详细日志信息

    def log(self, message):
        """输出带时间戳的日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_updated.emit(f"[{timestamp}] {message}")

    def run(self):
        try:
            bot = CursorAuthBot()
            
            # 初始化浏览器
            self.progress_updated.emit("正在初始化浏览器...", 10)
            self.log("开始初始化浏览器...")
            bot.init_browser()
            self.log("浏览器初始化完成")
            
            # 第一次登录
            self.progress_updated.emit("正在获取GitHub认证链接...", 20)
            self.log("正在获取GitHub认证链接...")
            auth_link = bot.get_github_auth_link()
            self.log(f"获取到认证链接: {auth_link}")
            
            self.progress_updated.emit("正在打开认证链接...", 30)
            self.log("正在打开认证链接...")
            bot.tab.get(auth_link)
            
            self.progress_updated.emit("等待获取cookies...", 40)
            self.log("正在获取第一次登录的cookies...")
            cookies = bot.get_cursor_cookies()
            
            if not cookies:
                self.log("无法获取cookies，认证失败")
                self.finished.emit(False, "无法获取cookies")
                return
            
            self.log(f"成功获取cookies: {json.dumps(cookies, indent=2, ensure_ascii=False)}")
                
            # 发送删除请求
            self.progress_updated.emit("正在发送删除请求...", 50)
            self.log("正在发送删除账号请求...")
            bot.send_delete_request(cookies)
            self.log("删除请求已发送")
            
            # 第二次登录
            self.progress_updated.emit("正在进行第二次登录...", 60)
            self.log("开始第二次登录流程...")
            auth_link = bot.get_github_auth_link()
            bot.tab.get(auth_link)
            
            self.progress_updated.emit("正在获取新的cookies...", 70)
            self.log("正在获取第二次登录的cookies...")
            new_cookies = bot.get_cursor_cookies(max_retries=5)
            
            if not new_cookies:
                self.log("无法获取新的cookies，认证失败")
                self.finished.emit(False, "无法获取新的cookies")
                return
            
            self.log(f"成功获取新cookies: {json.dumps(new_cookies, indent=2, ensure_ascii=False)}")
                
            # 获取用户信息
            self.progress_updated.emit("正在获取用户信息...", 80)
            self.log("正在获取用户信息...")
            user_info = bot.get_user_info(new_cookies)
            
            if not user_info or 'email' not in user_info:
                self.log("无法获取用户邮箱信息")
                self.finished.emit(False, "无法获取用户邮箱")
                return
            
            self.log(f"获取到用户信息: {json.dumps(user_info, indent=2, ensure_ascii=False)}")
                
            # 重置机器码
            self.progress_updated.emit("正在重置机器码...", 90)
            self.log("正在重置机器码...")
            bot.machine_resetter.reset_machine_ids()
            self.log("机器码重置完成")
            
            # 更新认证信息
            self.progress_updated.emit("正在更新认证信息...", 95)
            self.log("正在更新认证信息...")
            if not bot.update_auth_info(user_info['email'], new_cookies):
                self.log("更新认证信息失败")
                self.finished.emit(False, "更新认证信息失败")
                return
            
            self.log("认证信息更新成功")
            self.progress_updated.emit("操作完成！", 100)
            self.finished.emit(True, "认证过程完成！")
            
        except Exception as e:
            self.log(f"发生错误: {str(e)}")
            self.finished.emit(False, f"发生错误: {str(e)}")
        finally:
            try:
                self.log("正在关闭浏览器...")
                bot.browser_manager.quit()
                self.log("浏览器已关闭")
            except:
                pass

class SettingsInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('settingsInterface')
        
        # 创建布局
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(36, 30, 36, 0)
        
        # 创建设置组
        self.settingGroup = SettingCardGroup(self.tr("外观"), self)
        
        # 创建深色模式设置卡片
        self.darkModeCard = SwitchSettingCard(
            FluentIcon.CONSTRACT,
            "深色模式",
            "切换应用的深色/浅色主题",
            Config.darkMode,
            self.settingGroup
        )
        
        # 连接深色模式切换信号
        self.darkModeCard.switchButton.checkedChanged.connect(self.toggleTheme)
        
        # 添加设置卡片到设置组
        self.settingGroup.addSettingCard(self.darkModeCard)
        
        # 添加设置组到布局
        self.vBoxLayout.addWidget(self.settingGroup)
        self.vBoxLayout.addStretch(1)
        
        # 设置初始主题
        self.toggleTheme(Config.darkMode.value)
        
    def toggleTheme(self, isChecked):
        """切换主题"""
        setTheme(Theme.DARK if isChecked else Theme.LIGHT)
        Config.darkMode.value = isChecked
        qconfig.save()

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cursor无限试用")
        
        # 设置窗口大小
        self.resize(1000, 700)
        
        # 设置初始主题
        setTheme(Theme.DARK if Config.darkMode.value else Theme.LIGHT)
        
        # 创建主界面
        self.main_widget = QWidget()
        self.main_widget.setObjectName("homeInterface")
        
        # 创建卡片容器
        self.card = CardWidget(self)
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(20, 10, 20, 20)
        
        # 创建标题区域
        self.title_widget = QWidget()
        self.title_layout = QVBoxLayout(self.title_widget)
        self.title_layout.setSpacing(0)
        
        # 主标题
        self.title = TitleLabel("Cursor无限试用工具", self)
        self.title.setObjectName("titleLabel")
        self.title_layout.addWidget(self.title)
        
        # 副标题
        self.subtitle = StrongBodyLabel("让你的Cursor永远保持Pro", self)
        self.subtitle.setObjectName("subtitleLabel")
        self.title_layout.addWidget(self.subtitle)
        
        self.card_layout.addWidget(self.title_widget)
        
        # 创建进度条
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setValue(0)
        self.card_layout.addWidget(self.progress_bar)
        
        # 创建进度状态标签
        self.progress_label = SubtitleLabel("准备就绪", self)
        self.progress_label.setObjectName("progressLabel")
        self.card_layout.addWidget(self.progress_label)
        
        # 创建日志显示区域
        self.log_edit = TextEdit(self)
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("等待开始...\n\n提示：点击\"开始认证\"按钮开始无限试用流程")
        self.log_edit.setMinimumHeight(400)
        self.card_layout.addWidget(self.log_edit)
        
        # 创建按钮区域
        self.button_layout = QHBoxLayout()
        self.start_button = PushButton("开始认证", self, icon=FluentIcon.PLAY)
        self.start_button.setFixedWidth(150)
        self.start_button.clicked.connect(self.start_auth)
        self.button_layout.addWidget(self.start_button, alignment=Qt.AlignCenter)
        self.card_layout.addLayout(self.button_layout)
        
        # 设置主布局
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.addWidget(self.card)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        
        # 创建导航栏
        self.navigation = NavigationInterface(self, showReturnButton=True)
        self.navigation.setExpandWidth(300)  # 设置展开宽度
        
        # 创建设置界面
        self.settings_interface = SettingsInterface(self)
        
        # 添加主界面到导航
        self.addSubInterface(
            self.main_widget,
            icon=FluentIcon.HOME,
            text="主页",
            position=NavigationItemPosition.TOP
        )
        
        # 添加设置界面
        self.addSubInterface(
            self.settings_interface,
            icon=FluentIcon.SETTING,
            text="设置",
            position=NavigationItemPosition.BOTTOM
        )
        
        # 初始化工作线程
        self.worker = None
        
        # 设置样式
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
            #titleLabel {
                font-size: 33px;
                font-weight: bold;
                margin-bottom: 5px;
                color: #1a73e8;
            }
            #subtitleLabel {
                font-size: 14px;
                color: #666666;
                margin-bottom: 20px;
            }
            #progressLabel {
                font-size: 14px;
                color: #666666;
                margin-top: 5px;
                margin-bottom: 10px;
            }
            TextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        
    def start_auth(self):
        """开始认证流程"""
        if self.worker and self.worker.isRunning():
            return
            
        self.start_button.setEnabled(False)
        self.log_edit.clear()
        self.progress_bar.setValue(0)
        self.progress_label.setText("准备开始...")
        
        self.worker = AuthWorker()
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.log_updated.connect(self.update_log)
        self.worker.finished.connect(self.auth_finished)
        self.worker.start()
        
    def update_progress(self, message, value):
        """更新进度信息"""
        self.progress_bar.setValue(value)
        self.progress_label.setText(message)
        
    def update_log(self, message):
        """更新日志信息"""
        self.log_edit.append(message)
        # 自动滚动到底部
        self.log_edit.verticalScrollBar().setValue(
            self.log_edit.verticalScrollBar().maximum()
        )
        
    def auth_finished(self, success, message):
        """认证完成处理"""
        self.start_button.setEnabled(True)
        self.progress_bar.setValue(100 if success else 0)
        self.progress_label.setText("操作完成" if success else "操作失败")
        
        if success:
            InfoBar.success(
                title='成功',
                content=message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        else:
            InfoBar.error(
                title='错误',
                content=message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 