"""
摄影师客户管理器 v1.0
作者：AI助手
功能：管理摄影师客户，快速访问NAS照片文件夹
日期：2024-03-20
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import sqlite3
from datetime import datetime
from PIL import Image, ImageTk
import shutil
import sys
from pathlib import Path

# ==================== 配置类 ====================
class Config:
    """配置管理"""
    def __init__(self):
        self.app_name = "摄影师客户管理器"
        self.version = "1.0.0"
        self.theme_color = "#A8E6CF"  # 薄荷绿
        self.bg_color = "#FFFFFF"
        self.card_bg = "#FFFFFF"
        self.text_color = "#333333"
        self.border_color = "#F0F0F0"
        
        # 用户数据目录
        self.app_data_dir = Path.home() / "AppData" / "Roaming" / "PhotographerClient"
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        # 数据库路径
        self.db_path = self.app_data_dir / "clients.db"
        self.config_path = self.app_data_dir / "config.json"
        
        # 缓存目录
        self.cache_dir = self.app_data_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # 加载配置
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        default_config = {
            "nas_path": "",
            "card_size": "medium",
            "sort_by": "date",
            "view_mode": "grid",
            "auto_backup": True,
            "backup_path": str(self.app_data_dir / "backups"),
            "last_opened": None
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default_config
        return default_config
    
    def save_config(self):
        """保存配置"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def get(self, key, default=None):
        """获取配置项"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """设置配置项"""
        self.config[key] = value
        self.save_config()

# ==================== 数据库类 ====================
class Database:
    """数据库管理"""
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建客户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                folder_path TEXT NOT NULL,
                type_id INTEGER,
                date TEXT,
                phone TEXT,
                email TEXT,
                notes TEXT,
                avatar_path TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        # 创建类型表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT DEFAULT '#CCCCCC',
                created_at TEXT,
                client_count INTEGER DEFAULT 0
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clients_type ON clients(type_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clients_date ON clients(date)')
        
        conn.commit()
        conn.close()
    
    def execute_query(self, query, params=(), fetch=False):
        """执行SQL查询"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(query, params)
            conn.commit()
            
            if fetch:
                result = cursor.fetchall()
                conn.close()
                return result
            else:
                conn.close()
                return cursor.lastrowid
        except Exception as e:
            conn.close()
            raise e

# ==================== 客户管理类 ====================
class ClientManager:
    """客户管理"""
    def __init__(self, db):
        self.db = db
        self.config = Config()
    
    def add_client(self, name, folder_path, type_name, date=None, phone="", email="", notes=""):
        """添加新客户"""
        # 检查文件夹是否存在
        if not os.path.exists(folder_path):
            raise ValueError(f"文件夹不存在: {folder_path}")
        
        # 获取或创建类型
        type_id = self._get_or_create_type(type_name)
        
        # 生成头像
        avatar_path = self._generate_avatar(folder_path, name)
        
        # 插入数据库
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = '''
            INSERT INTO clients (name, folder_path, type_id, date, phone, email, notes, avatar_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        client_id = self.db.execute_query(query, (name, folder_path, type_id, date, phone, email, notes, avatar_path, now, now))
        
        # 更新类型计数
        self._update_type_count(type_id)
        
        return client_id
    
    def _get_or_create_type(self, type_name):
        """获取或创建类型"""
        # 检查是否已存在
        query = "SELECT id FROM types WHERE name = ?"
        result = self.db.execute_query(query, (type_name,), fetch=True)
        
        if result:
            return result[0][0]
        
        # 创建新类型
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        default_color = self.config.theme_color
        query = "INSERT INTO types (name, color, created_at) VALUES (?, ?, ?)"
        return self.db.execute_query(query, (type_name, default_color, now))
    
    def _generate_avatar(self, folder_path, client_name):
        """从文件夹生成头像"""
        try:
            # 查找文件夹中的图片
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
            for file in os.listdir(folder_path):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_path = os.path.join(folder_path, file)
                    
                    # 创建头像缓存
                    avatar_path = self.config.cache_dir / f"avatar_{client_name}_{hash(file)}.jpg"
                    
                    # 打开并调整图片大小
                    with Image.open(image_path) as img:
                        img = img.convert('RGB')
                        img = img.resize((120, 120), Image.Resampling.LANCZOS)
                        img.save(avatar_path, 'JPEG', quality=85)
                    
                    return str(avatar_path)
        except:
            pass
        
        # 如果没有找到图片，使用默认头像
        return ""
    
    def _update_type_count(self, type_id):
        """更新类型计数"""
        query = """
            UPDATE types 
            SET client_count = (SELECT COUNT(*) FROM clients WHERE type_id = ?)
            WHERE id = ?
        """
        self.db.execute_query(query, (type_id, type_id))
    
    def get_all_clients(self):
        """获取所有客户"""
        query = """
            SELECT c.*, t.name as type_name, t.color as type_color
            FROM clients c
            LEFT JOIN types t ON c.type_id = t.id
            ORDER BY c.date DESC, c.name
        """
        return self.db.execute_query(query, fetch=True)
    
    def search_clients(self, keyword):
        """搜索客户"""
        query = """
            SELECT c.*, t.name as type_name, t.color as type_color
            FROM clients c
            LEFT JOIN types t ON c.type_id = t.id
            WHERE c.name LIKE ? OR c.phone LIKE ? OR c.notes LIKE ? OR t.name LIKE ?
            ORDER BY c.date DESC
        """
        search_term = f"%{keyword}%"
        return self.db.execute_query(query, (search_term, search_term, search_term, search_term), fetch=True)
    
    def get_client_by_id(self, client_id):
        """根据ID获取客户"""
        query = """
            SELECT c.*, t.name as type_name, t.color as type_color
            FROM clients c
            LEFT JOIN types t ON c.type_id = t.id
            WHERE c.id = ?
        """
        result = self.db.execute_query(query, (client_id,), fetch=True)
        return result[0] if result else None
    
    def update_client(self, client_id, **kwargs):
        """更新客户信息"""
        # 构建更新语句
        set_clause = []
        params = []
        
        for key, value in kwargs.items():
            set_clause.append(f"{key} = ?")
            params.append(value)
        
        params.append(client_id)
        set_str = ", ".join(set_clause)
        query = f"UPDATE clients SET {set_str}, updated_at = ? WHERE id = ?"
        params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        params.append(client_id)
        
        self.db.execute_query(query, tuple(params))
    
    def delete_client(self, client_id):
        """删除客户"""
        query = "DELETE FROM clients WHERE id = ?"
        self.db.execute_query(query, (client_id,))
    
    def get_types(self):
        """获取所有类型"""
        query = "SELECT * FROM types ORDER BY client_count DESC"
        return self.db.execute_query(query, fetch=True)
    
    def update_type_color(self, type_id, color):
        """更新类型颜色"""
        query = "UPDATE types SET color = ? WHERE id = ?"
        self.db.execute_query(query, (color, type_id))
    
    def get_stats(self):
        """获取统计信息"""
        stats = {}
        
        # 客户总数
        query = "SELECT COUNT(*) FROM clients"
        stats['total_clients'] = self.db.execute_query(query, fetch=True)[0][0]
        
        # 类型分布
        query = "SELECT name, client_count FROM types ORDER BY client_count DESC"
        stats['type_distribution'] = self.db.execute_query(query, fetch=True)
        
        # 最近添加
        query = "SELECT name, created_at FROM clients ORDER BY created_at DESC LIMIT 5"
        stats['recent_clients'] = self.db.execute_query(query, fetch=True)
        
        return stats

# ==================== 界面组件 ====================
class Card(tk.Frame):
    """客户卡片组件"""
    def __init__(self, parent, client_data, on_click, on_context_menu):
        super().__init__(parent, bg="#FFFFFF", relief=tk.RAISED, bd=1)
        
        self.client_data = client_data
        self.on_click = on_click
        self.on_context_menu = on_context_menu
        
        self.setup_ui()
        self.bind_events()
    
    def setup_ui(self):
        """设置卡片UI"""
        # 卡片标题栏（颜色条）
        title_frame = tk.Frame(self, bg=self.client_data.get('type_color', '#CCCCCC'), height=4)
        title_frame.pack(fill=tk.X)
        
        # 主内容区域
        content_frame = tk.Frame(self, bg="#FFFFFF", padx=10, pady=10)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # 头像
        avatar_label = tk.Label(content_frame, text="👤", font=("Arial", 24), bg="#FFFFFF")
        avatar_label.pack(pady=5)
        
        # 如果有头像图片
        avatar_path = self.client_data.get('avatar_path')
        if avatar_path and os.path.exists(avatar_path):
            try:
                img = Image.open(avatar_path)
                img = img.resize((80, 80), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                avatar_label.config(image=photo, text="")
                avatar_label.image = photo  # 保持引用
            except:
                pass
        
        # 客户姓名
        name_label = tk.Label(
            content_frame, 
            text=self.client_data['name'], 
            font=("Microsoft YaHei", 11, "bold"),
            bg="#FFFFFF",
            fg="#333333"
        )
        name_label.pack(pady=(5, 2))
        
        # 类型
        type_label = tk.Label(
            content_frame,
            text=self.client_data.get('type_name', '未分类'),
            font=("Microsoft YaHei", 9),
            bg="#FFFFFF",
            fg="#666666"
        )
        type_label.pack(pady=(0, 5))
        
        # 照片数量（模拟）
        photo_count = self._count_photos()
        count_label = tk.Label(
            content_frame,
            text=f"📸 {photo_count}张照片",
            font=("Microsoft YaHei", 8),
            bg="#FFFFFF",
            fg="#999999"
        )
        count_label.pack()
        
        # 日期
        date_label = tk.Label(
            content_frame,
            text=f"📅 {self.client_data.get('date', '未知日期')}",
            font=("Microsoft YaHei", 8),
            bg="#FFFFFF",
            fg="#999999"
        )
        date_label.pack()
    
    def _count_photos(self):
        """统计照片数量（模拟）"""
        folder_path = self.client_data.get('folder_path', '')
        if os.path.exists(folder_path):
            try:
                count = len([f for f in os.listdir(folder_path) 
                           if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))])
                return count
            except:
                return 0
        return 0
    
    def bind_events(self):
        """绑定事件"""
        self.bind("<Button-1>", self.on_click)
        self.bind("<Button-3>", self.on_context_menu)
        
        for child in self.winfo_children():
            child.bind("<Button-1>", self.on_click)
            child.bind("<Button-3>", self.on_context_menu)
            for subchild in child.winfo_children():
                subchild.bind("<Button-1>", self.on_click)
                subchild.bind("<Button-3>", self.on_context_menu)

# ==================== 主应用 ====================
class PhotographerClientManager:
    """主应用"""
    def __init__(self):
        self.config = Config()
        self.db = Database(self.config.db_path)
        self.client_manager = ClientManager(self.db)
        
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title(f"{self.config.app_name} v{self.config.version}")
        self.root.geometry("1200x800")
        self.root.configure(bg=self.config.bg_color)
        
        # 设置窗口图标
        try:
            self.root.iconbitmap(default='icon.ico')
        except:
            pass
        
        # 应用主题
        self.setup_theme()
        
        # 初始化UI
        self.setup_ui()
        
        # 加载数据
        self.load_data()
    
    def setup_theme(self):
        """设置主题"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置颜色
        style.configure("TButton", 
                       background=self.config.theme_color,
                       foreground=self.config.text_color,
                       borderwidth=1,
                       focusthickness=3,
                       focuscolor='none')
        
        style.map('TButton',
                 background=[('active', '#8BC5B5')])
    
    def setup_ui(self):
        """设置主界面"""
        # 顶部工具栏
        self.setup_toolbar()
        
        # 左侧边栏
        self.setup_sidebar()
        
        # 主内容区域
        self.setup_main_content()
        
        # 状态栏
        self.setup_statusbar()
    
    def setup_toolbar(self):
        """设置工具栏"""
        toolbar = tk.Frame(self.root, bg=self.config.theme_color, height=60)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        
        # 标题
        title_label = tk.Label(
            toolbar,
            text=self.config.app_name,
            font=("Microsoft YaHei", 16, "bold"),
            bg=self.config.theme_color,
            fg="#FFFFFF"
        )
        title_label.pack(side=tk.LEFT, padx=20)
        
        # 搜索框
        search_frame = tk.Frame(toolbar, bg=self.config.theme_color)
        search_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(search_frame, text="🔍", bg=self.config.theme_color, fg="#FFFFFF").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search)
        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            width=30,
            font=("Microsoft YaHei", 10),
            relief=tk.FLAT
        )
        search_entry.pack(side=tk.LEFT, padx=5)
        
        # 添加按钮
        add_button = tk.Button(
            toolbar,
            text="＋ 添加客户",
            command=self.add_client_dialog,
            bg="#FFFFFF",
            fg=self.config.theme_color,
            font=("Microsoft YaHei", 10, "bold"),
            relief=tk.FLAT,
            padx=15,
            pady=5
        )
        add_button.pack(side=tk.RIGHT, padx=20)
        
        # 设置按钮
        settings_button = tk.Button(
            toolbar,
            text="⚙",
            command=self.open_settings,
            bg=self.config.theme_color,
            fg="#FFFFFF",
            font=("Arial", 14),
            relief=tk.FLAT
        )
        settings_button.pack(side=tk.RIGHT, padx=5)
    
    def setup_sidebar(self):
        """设置侧边栏"""
        sidebar = tk.Frame(self.root, bg="#F8F9FA", width=200)
        sidebar.pack(fill=tk.Y, side=tk.LEFT)
        
        # 类型筛选
        type_frame = tk.LabelFrame(sidebar, text="📁 客户类型", bg="#F8F9FA", padx=10, pady=10)
        type_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.type_listbox = tk.Listbox(
            type_frame,
            bg="#FFFFFF",
            relief=tk.FLAT,
            selectmode=tk.MULTIPLE,
            height=15
        )
        self.type_listbox.pack(fill=tk.BOTH, expand=True)
        
        # 类型管理按钮
        type_button_frame = tk.Frame(type_frame, bg="#F8F9FA")
        type_button_frame.pack(fill=tk.X, pady=(5, 0))
        
        tk.Button(
            type_button_frame,
            text="管理类型",
            command=self.manage_types,
            bg=self.config.theme_color,
            fg="#FFFFFF",
            relief=tk.FLAT,
            font=("Microsoft YaHei", 9)
        ).pack(side=tk.LEFT, padx=2)
        
        tk.Button(
            type_button_frame,
            text="统计",
            command=self.show_stats,
            bg=self.config.theme_color,
            fg="#FFFFFF",
            relief=tk.FLAT,
            font=("Microsoft YaHei", 9)
        ).pack(side=tk.LEFT, padx=2)
    
    def setup_main_content(self):
        """设置主内容区域"""
        # 主框架
        main_frame = tk.Frame(self.root, bg=self.config.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # 客户网格容器
        self.canvas = tk.Canvas(main_frame, bg=self.config.bg_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.config.bg_color)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定鼠标滚轮
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # 网格框架
        self.grid_frame = tk.Frame(self.scrollable_frame, bg=self.config.bg_color)
        self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    def setup_statusbar(self):
        """设置状态栏"""
        statusbar = tk.Frame(self.root, bg="#F0F0F0", height=30)
        statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = tk.Label(
            statusbar,
            text="就绪",
            bg="#F0F0F0",
            fg="#666666",
            font=("Microsoft YaHei", 9)
        )
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # 客户计数
        self.count_label = tk.Label(
            statusbar,
            text="客户: 0",
            bg="#F0F0F0",
            fg="#666666",
            font=("Microsoft YaHei", 9)
        )
        self.count_label.pack(side=tk.RIGHT, padx=10)
    
    def _on_mousewheel(self, event):
        """鼠标滚轮事件"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def load_data(self):
        """加载数据"""
        # 加载类型
        self.refresh_type_list()
        
        # 加载客户
        self.refresh_client_grid()
    
    def refresh_type_list(self):
        """刷新类型列表"""
        self.type_listbox.delete(0, tk.END)
        types = self.client_manager.get_types()
        
        for type_data in types:
            type_id, name, color, created_at, count = type_data
            self.type_listbox.insert(tk.END, f"{name} ({count})")
    
    def refresh_client_grid(self, clients=None):
        """刷新客户网格"""
        # 清除现有卡片
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        
        # 获取客户数据
        if clients is None:
            clients = self.client_manager.get_all_clients()
        
        # 显示客户卡片
        for i, client_data in enumerate(clients):
            # 将数据库行转换为字典
            client_dict = {
                'id': client_data[0],
                'name': client_data[1],
                'folder_path': client_data[2],
                'type_id': client_data[3],
                'date': client_data[4],
                'phone': client_data[5],
                'email': client_data[6],
                'notes': client_data[7],
                'avatar_path': client_data[8],
                'type_name': client_data[10],
                'type_color': client_data[11]
            }
            
            # 创建卡片
            card = Card(
                self.grid_frame,
                client_dict,
                lambda e, cid=client_dict['id']: self.open_client_folder(cid),
                lambda e, cid=client_dict['id']: self.show_context_menu(e, cid)
            )
            
            # 网格布局（每行4个）
            row = i // 4
            col = i % 4
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        # 配置网格权重
        for i in range(4):
            self.grid_frame.columnconfigure(i, weight=1)
        
        # 更新状态栏
        self.count_label.config(text=f"客户: {len(clients)}")
        self.status_label.config(text=f"显示 {len(clients)} 位客户")
    
    def on_search(self, *args):
        """搜索事件"""
        keyword = self.search_var.get().strip()
        if keyword:
            clients = self.client_manager.search_clients(keyword)
            self.refresh_client_grid(clients)
        else:
            self.refresh_client_grid()
    
    def add_client_dialog(self):
        """添加客户对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加新客户")
        dialog.geometry("500x600")
        dialog.configure(bg=self.config.bg_color)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # 步骤1：选择文件夹
        step1_frame = tk.LabelFrame(dialog, text="1. 选择客户文件夹", bg=self.config.bg_color, padx=20, pady=20)
        step1_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(step1_frame, text="NAS路径:", bg=self.config.bg_color).pack(anchor=tk.W)
        
        path_frame = tk.Frame(step1_frame, bg=self.config.bg_color)
        path_frame.pack(fill=tk.X, pady=5)
        
        self.folder_path_var = tk.StringVar()
        path_entry = tk.Entry(path_frame, textvariable=self.folder_path_var, width=40)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Button(
            path_frame,
            text="浏览...",
            command=lambda: self.browse_folder(path_entry),
            bg=self.config.theme_color,
            fg="#FFFFFF"
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 步骤2：填写信息
        step2_frame = tk.LabelFrame(dialog, text="2. 填写客户信息", bg=self.config.bg_color, padx=20, pady=20)
        step2_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # 姓名
        tk.Label(step2_frame, text="客户姓名:", bg=self.config.bg_color).pack(anchor=tk.W)
        name_entry = tk.Entry(step2_frame, width=40)
        name_entry.pack(fill=tk.X, pady=(0, 10))
        
        # 类型
        tk.Label(step2_frame, text="拍摄类型:", bg=self.config.bg_color).pack(anchor=tk.W)
        type_entry = tk.Entry(step2_frame, width=40)
        type_entry.pack(fill=tk.X, pady=(0, 10))
        
        # 日期
        tk.Label(step2_frame, text="拍摄日期:", bg=self.config.bg_color).pack(anchor=tk.W)
        date_entry = tk.Entry(step2_frame, width=40)
        date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        date_entry.pack(fill=tk.X, pady=(0, 10))
        
        # 步骤3：确认
        def confirm_add():
            name = name_entry.get().strip()
            folder_path = self.folder_path_var.get().strip()
            type_name = type_entry.get().strip()
            date = date_entry.get().strip()
            
            if not name:
                messagebox.showerror("错误", "请输入客户姓名")
                return
            
            if not folder_path or not os.path.exists(folder_path):
                messagebox.showerror("错误", "请选择有效的文件夹路径")
                return
            
            if not type_name:
                messagebox.showerror("错误", "请输入拍摄类型")
                return
            
            try:
                # 检查是否新类型
                types = self.client_manager.get_types()
                existing_types = [t[1] for t in types]
                
                if type_name not in existing_types:
                    # 新类型确认
                    if not messagebox.askyesno("创建新类型", f"将创建新的客户类型：{type_name}\n\n确认创建并添加客户吗？"):
                        return
                
                # 添加客户
                self.client_manager.add_client(name, folder_path, type_name, date)
                
                # 刷新显示
                self.refresh_type_list()
                self.refresh_client_grid()
                
                messagebox.showinfo("成功", f"客户 {name} 添加成功！")
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("错误", f"添加失败: {str(e)}")
        
        button_frame = tk.Frame(dialog, bg=self.config.bg_color)
        button_frame.pack(pady=20)
        
        tk.Button(
            button_frame,
            text="取消",
            command=dialog.destroy,
            bg="#CCCCCC",
            fg="#333333",
            width=10
        ).pack(side=tk.LEFT, padx=10)
        
        tk.Button(
            button_frame,
            text="添加客户",
            command=confirm_add,
            bg=self.config.theme_color,
            fg="#FFFFFF",
            width=10
        ).pack(side=tk.LEFT, padx=10)
    
    def browse_folder(self, entry_widget):
        """浏览文件夹"""
        folder_path = filedialog.askdirectory(title="选择客户文件夹")
        if folder_path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, folder_path)
            self.folder_path_var.set(folder_path)
    
    def open_client_folder(self, client_id):
        """打开客户文件夹"""
        client = self.client_manager.get_client_by_id(client_id)
        if client and client[2]:  # folder_path
            folder_path = client[2]
            try:
                if os.path.exists(folder_path):
                    os.startfile(folder_path)
                    self.status_label.config(text=f"已打开文件夹: {client[1]}")
                else:
                    messagebox.showwarning("警告", f"文件夹不存在:\n{folder_path}")
            except Exception as e:
                messagebox.showerror("错误", f"无法打开文件夹: {str(e)}")
    
    def show_context_menu(self, event, client_id):
        """显示右键菜单"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="打开文件夹", command=lambda: self.open_client_folder(client_id))
        menu.add_separator()
        menu.add_command(label="编辑信息", command=lambda: self.edit_client(client_id))
        menu.add_command(label="删除客户", command=lambda: self.delete_client(client_id))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def edit_client(self, client_id):
        """编辑客户信息"""
        # 实现编辑对话框
        messagebox.showinfo("提示", "编辑功能将在后续版本中提供")
    
    def delete_client(self, client_id):
        """删除客户"""
        client = self.client_manager.get_client_by_id(client_id)
        if not client:
            return
        
        if messagebox.askyesno("确认删除", f"确定要删除客户 {client[1]} 吗？\n\n注意：这不会删除NAS上的照片文件。"):
            try:
                self.client_manager.delete_client(client_id)
                self.refresh_type_list()
                self.refresh_client_grid()
                messagebox.showinfo("成功", "客户已删除")
            except Exception as e:
                messagebox.showerror("错误", f"删除失败: {str(e)}")
    
    def manage_types(self):
        """管理类型对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("管理客户类型")
        dialog.geometry("600x500")
        dialog.configure(bg=self.config.bg_color)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # 类型列表
        list_frame = tk.Frame(dialog, bg=self.config.bg_color)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 表格
        columns = ("ID", "类型名称", "颜色", "客户数", "创建时间")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 加载数据
        types = self.client_manager.get_types()
        for type_data in types:
            tree.insert("", tk.END, values=type_data)
        
        # 按钮区域
        button_frame = tk.Frame(dialog, bg=self.config.bg_color)
        button_frame.pack(pady=10)
        
        tk.Button(
            button_frame,
            text="刷新",
            command=lambda: self.refresh_type_dialog(tree, dialog),
            bg=self.config.theme_color,
            fg="#FFFFFF"
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="关闭",
            command=dialog.destroy,
            bg="#CCCCCC",
            fg="#333333"
        ).pack(side=tk.LEFT, padx=5)
    
    def refresh_type_dialog(self, tree, dialog):
        """刷新类型对话框"""
        # 清空现有数据
        for item in tree.get_children():
            tree.delete(item)
        
        # 重新加载
        types = self.client_manager.get_types()
        for type_data in types:
            tree.insert("", tk.END, values=type_data)
        
        # 也刷新主界面的类型列表
        self.refresh_type_list()
    
    def show_stats(self):
        """显示统计信息"""
        stats = self.client_manager.get_stats()
        
        dialog = tk.Toplevel(self.root)
        dialog.title("统计信息")
        dialog.geometry("400x300")
        dialog.configure(bg=self.config.bg_color)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # 统计内容
        content_frame = tk.Frame(dialog, bg=self.config.bg_color, padx=20, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(
            content_frame,
            text=f"📊 客户统计",
            font=("Microsoft YaHei", 14, "bold"),
            bg=self.config.bg_color
        ).pack(anchor=tk.W, pady=(0, 20))
        
        tk.Label(
            content_frame,
            text=f"• 总客户数: {stats['total_clients']}",
            font=("Microsoft YaHei", 11),
            bg=self.config.bg_color
        ).pack(anchor=tk.W, pady=5)
        
        tk.Label(
            content_frame,
            text="• 类型分布:",
            font=("Microsoft YaHei", 11),
            bg=self.config.bg_color
        ).pack(anchor=tk.W, pady=(10, 5))
        
        # 类型分布
        for type_name, count in stats['type_distribution']:
            tk.Label(
                content_frame,
                text=f"  {type_name}: {count}",
                font=("Microsoft YaHei", 10),
                bg=self.config.bg_color,
                fg="#666666"
            ).pack(anchor=tk.W, padx=20)
        
        tk.Button(
            dialog,
            text="关闭",
            command=dialog.destroy,
            bg=self.config.theme_color,
            fg="#FFFFFF",
            width=10
        ).pack(pady=10)
    
    def open_settings(self):
        """打开设置"""
        dialog = tk.Toplevel(self.root)
        dialog.title("设置")
        dialog.geometry("400x500")
        dialog.configure(bg=self.config.bg_color)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # 设置内容
        content_frame = tk.Frame(dialog, bg=self.config.bg_color, padx=20, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(
            content_frame,
            text="⚙ 设置",
            font=("Microsoft YaHei", 14, "bold"),
            bg=self.config.bg_color
        ).pack(anchor=tk.W, pady=(0, 20))
        
        # NAS路径设置
        tk.Label(content_frame, text="NAS根路径:", bg=self.config.bg_color).pack(anchor=tk.W)
        
        nas_frame = tk.Frame(content_frame, bg=self.config.bg_color)
        nas_frame.pack(fill=tk.X, pady=5)
        
        nas_path = self.config.get("nas_path", "")
        nas_var = tk.StringVar(value=nas_path)
        nas_entry = tk.Entry(nas_frame, textvariable=nas_var, width=30)
        nas_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Button(
            nas_frame,
            text="浏览...",
            command=lambda: self.browse_nas_folder(nas_entry),
            bg=self.config.theme_color,
            fg="#FFFFFF"
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 卡片大小
        tk.Label(content_frame, text="卡片大小:", bg=self.config.bg_color).pack(anchor=tk.W, pady=(10, 5))
        size_var = tk.StringVar(value=self.config.get("card_size", "medium"))
        tk.Radiobutton(
            content_frame,
            text="小",
            variable=size_var,
            value="small",
            bg=self.config.bg_color
        ).pack(anchor=tk.W)
        tk.Radiobutton(
            content_frame,
            text="中",
            variable=size_var,
            value="medium",
            bg=self.config.bg_color
        ).pack(anchor=tk.W)
        tk.Radiobutton(
            content_frame,
            text="大",
            variable=size_var,
            value="large",
            bg=self.config.bg_color
        ).pack(anchor=tk.W)
        
        # 自动备份
        backup_var = tk.BooleanVar(value=self.config.get("auto_backup", True))
        tk.Checkbutton(
            content_frame,
            text="启用自动备份",
            variable=backup_var,
            bg=self.config.bg_color
        ).pack(anchor=tk.W, pady=10)
        
        def save_settings():
            self.config.set("nas_path", nas_var.get())
            self.config.set("card_size", size_var.get())
            self.config.set("auto_backup", backup_var.get())
            messagebox.showinfo("成功", "设置已保存")
            dialog.destroy()
        
        tk.Button(
            dialog,
            text="保存设置",
            command=save_settings,
            bg=self.config.theme_color,
            fg="#FFFFFF",
            width=15
        ).pack(pady=20)
    
    def browse_nas_folder(self, entry_widget):
        """浏览NAS文件夹"""
        folder_path = filedialog.askdirectory(title="选择NAS根目录")
        if folder_path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, folder_path)
    
    def run(self):
        """运行应用"""
        self.root.mainloop()

# ==================== 主程序入口 ====================
def main():
    """主函数"""
    # 检查必要依赖
    try:
        import PIL
    except ImportError:
        print("错误: 需要安装Pillow库")
        print("请在命令行运行: pip install pillow")
        return
    
    # 创建并运行应用
    app = PhotographerClientManager()
    app.run()

if __name__ == "__main__":
    main()