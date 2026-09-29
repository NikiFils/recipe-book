import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from pathlib import Path
from datetime import datetime
from collections import OrderedDict, Counter
from PIL import Image, ImageTk
import shutil
import re
import sys
import traceback
import copy
import random
import csv

# Попробуем импортировать дополнительные библиотеки
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Класс для всплывающих подсказок
class ToolTip:
    """Создает всплывающую подсказку для виджета"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind('<Enter>', self.enter)
        self.widget.bind('<Leave>', self.leave)
    
    def enter(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("Arial", 10, "normal"))
        label.pack()
    
    def leave(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

# Функция для добавления подсказки
def add_tooltip(widget, text):
    ToolTip(widget, text)

# Используем путь к файлу
RECIPES_FILE = Path.home() / "Documents" / "my_recipes.json"
BACKUP_FOLDER = Path.home() / "Documents" / "RecipeBackups"
IMAGES_FOLDER = Path.home() / "Documents" / "RecipeImages"
MEAL_PLAN_FILE = Path.home() / "Documents" / "meal_plan.json"
NOTES_FOLDER = Path.home() / "Documents" / "CookingNotes"

class RecipeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Кулинарная книга - Мои рецепты с группами")
        self.root.geometry("1300x800")
        self.root.resizable(True, True)
        
        # Загружаем данные
        self.data = self.load_data()
        self.meal_plan = self.load_meal_plan()
        self.current_group = None
        self.current_recipe = None
        self.current_image_path = None
        self.image_preview = None
        self.shopping_list = []
        self.temp_image_path = None
        
        # История для отмены/повтора
        self.history = []
        self.history_index = -1
        self.save_to_history()
        
        # Создаем папки
        BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
        IMAGES_FOLDER.mkdir(parents=True, exist_ok=True)
        NOTES_FOLDER.mkdir(parents=True, exist_ok=True)
        
        # Создаем меню
        self.create_menu()
        
        # Создаем интерфейс
        self.create_widgets()
        
        # Обновляем списки
        self.refresh_group_list()
        self.update_tags_list()
        
        # Создаем статусную строку
        self.create_status_bar()
        
        # Обработка закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Привязываем Delete только когда фокус не на полях ввода
        self.root.bind('<Delete>', self.on_delete_key)
        
        # Горячие клавиши
        self.root.bind('<Control-z>', self.undo)
        self.root.bind('<Control-y>', self.redo)
        self.root.bind('<Control-f>', lambda e: self.search_var.set(""))
        self.root.bind('<Control-s>', lambda e: self.save_current_recipe())
        self.root.bind('<Control-n>', lambda e: self.add_recipe_dialog())
        self.root.bind('<Control-g>', lambda e: self.add_group_dialog())
    
    def create_menu(self):
        """Создает верхнее меню"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Меню "Файл"
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Новая группа (Ctrl+G)", command=self.add_group_dialog)
        file_menu.add_command(label="Новый рецепт (Ctrl+N)", command=self.add_recipe_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Сохранить рецепт (Ctrl+S)", command=self.save_current_recipe)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.on_closing)
        
        # Меню "Импорт/Экспорт"
        import_export_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Импорт/Экспорт", menu=import_export_menu)
        import_export_menu.add_command(label="📥 Импорт JSON", command=self.import_json)
        import_export_menu.add_command(label="📤 Экспорт JSON", command=self.export_json)
        import_export_menu.add_separator()
        import_export_menu.add_command(label="📄 Экспорт TXT", command=self.export_txt)
        import_export_menu.add_command(label="📑 Экспорт PDF", command=self.export_pdf)
        import_export_menu.add_command(label="📊 Экспорт CSV", command=self.export_csv)
        import_export_menu.add_command(label="🌐 Экспорт HTML", command=self.export_html)
        import_export_menu.add_command(label="📝 Экспорт Markdown", command=self.export_markdown)
        import_export_menu.add_separator()
        import_export_menu.add_command(label="💾 Создать бэкап", command=self.create_backup)
        
        # Меню "Вид"
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Вид", menu=view_menu)
        view_menu.add_command(label="📖 Рецепты", command=lambda: self.notebook.select(0))
        view_menu.add_command(label="📅 Планировщик меню", command=lambda: self.notebook.select(1))
        view_menu.add_command(label="📊 Статистика", command=lambda: self.notebook.select(2))
        view_menu.add_command(label="🔍 Поиск по ингредиентам", command=lambda: self.notebook.select(3))
        
        # Меню "Помощь"
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Помощь", menu=help_menu)
        help_menu.add_command(label="📖 О программе", command=self.show_about)
        help_menu.add_command(label="⌨️ Горячие клавиши", command=self.show_hotkeys)
    
    def show_about(self):
        """Показывает информацию о программе"""
        messagebox.showinfo("О программе", 
            "Кулинарная книга v4.0\n\n"
            "Возможности:\n"
            "• Управление группами и рецептами\n"
            "• Планировщик меню на неделю\n"
            "• Поиск по ингредиентам\n"
            "• Масштабирование порций\n"
            "• Режим приготовления с таймером\n"
            "• Экспорт в PDF, TXT, HTML, CSV, Markdown\n"
            "• Статистика и аналитика\n"
            "• История действий (Ctrl+Z/Ctrl+Y)\n\n"
            "© 2024")
    
    def show_hotkeys(self):
        """Показывает горячие клавиши"""
        messagebox.showinfo("Горячие клавиши",
            "⌨️ Горячие клавиши:\n\n"
            "Ctrl+N - Новый рецепт\n"
            "Ctrl+G - Новая группа\n"
            "Ctrl+S - Сохранить рецепт\n"
            "Ctrl+F - Поиск\n"
            "Ctrl+Z - Отмена действия\n"
            "Ctrl+Y - Повтор действия\n"
            "Delete - Удалить рецепт (когда не в поле ввода)\n\n"
            "В режиме приготовления:\n"
            "F11 - Полный экран\n"
            "Esc - Выход из полноэкранного режима")
    
    def save_to_history(self):
        """Сохраняет текущее состояние в историю"""
        if len(self.history) > 50:
            self.history = self.history[-50:]
        
        if self.history_index < len(self.history) - 1:
            self.history = self.history[:self.history_index + 1]
        
        self.history.append(copy.deepcopy(self.data))
        self.history_index = len(self.history) - 1
    
    def undo(self, event=None):
        """Отмена последнего действия"""
        if self.history_index > 0:
            self.history_index -= 1
            self.data = copy.deepcopy(self.history[self.history_index])
            self.refresh_group_list()
            self.refresh_recipe_list()
            self.update_tags_list()
            if self.current_recipe:
                self.on_recipe_select(None)
            self.update_status("Действие отменено")
    
    def redo(self, event=None):
        """Повтор отмененного действия"""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.data = copy.deepcopy(self.history[self.history_index])
            self.refresh_group_list()
            self.refresh_recipe_list()
            self.update_tags_list()
            if self.current_recipe:
                self.on_recipe_select(None)
            self.update_status("Действие повторено")
    
    def update_status(self, message, duration=3000):
        """Обновляет статусную строку"""
        self.status_bar.config(text=message)
        if duration > 0:
            self.root.after(duration, lambda: self.status_bar.config(text="Готово"))
    
    def create_status_bar(self):
        """Создает статусную строку"""
        self.status_bar = ttk.Label(self.root, text="Готово", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def highlight_search_term(self, text_widget, search_term):
        """Подсвечивает найденные термины в тексте"""
        text_widget.tag_remove('highlight', '1.0', tk.END)
        
        if not search_term:
            return
        
        start = '1.0'
        while True:
            pos = text_widget.search(search_term, start, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(search_term)}c"
            text_widget.tag_add('highlight', pos, end)
            start = end
        
        text_widget.tag_config('highlight', background='yellow', foreground='black')
    
    def random_recipe(self):
        """Выбирает случайный рецепт"""
        all_recipes = []
        for group, recipes in self.data.items():
            for recipe_name in recipes.keys():
                all_recipes.append((group, recipe_name))
        
        if all_recipes:
            group, recipe_name = random.choice(all_recipes)
            self.current_group = group
            self.current_recipe = recipe_name
            self.refresh_group_list()
            self.refresh_recipe_list()
            self.on_recipe_select(None)
            self.update_status(f"Случайный выбор: {recipe_name}")
            messagebox.showinfo("Случайный рецепт", f"🍳 Сегодня готовим: {recipe_name}!")
        else:
            messagebox.showwarning("Нет рецептов", "Добавьте хотя бы один рецепт")
    
    def update_tags_list(self):
        """Обновляет список доступных тегов для фильтра"""
        all_tags = set()
        for group, recipes in self.data.items():
            for recipe in recipes.values():
                all_tags.update(recipe.get('tags', []))
        
        tags_list = ["Все теги"] + sorted(all_tags)
        if hasattr(self, 'tags_filter_combo'):
            self.tags_filter_combo['values'] = tags_list
    
    def on_delete_key(self, event):
        """Обработка клавиши Delete - удаляет только если фокус не на виджете ввода"""
        focus_widget = self.root.focus_get()
        input_widgets = (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox, ttk.Spinbox)
        
        if focus_widget and isinstance(focus_widget, input_widgets):
            return
        
        self.delete_recipe()
    
    def load_data(self):
        """Загружает данные из файла"""
        try:
            if RECIPES_FILE.exists():
                with open(RECIPES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ordered_data = OrderedDict()
                    for key, value in data.items():
                        ordered_data[key] = value
                    return ordered_data
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
        return OrderedDict()
    
    def load_meal_plan(self):
        """Загружает план питания"""
        try:
            if MEAL_PLAN_FILE.exists():
                with open(MEAL_PLAN_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def save_meal_plan(self):
        """Сохраняет план питания"""
        try:
            with open(MEAL_PLAN_FILE, "w", encoding="utf-8") as f:
                json.dump(self.meal_plan, f, ensure_ascii=False, indent=4)
        except:
            pass
    
    def save_data(self):
        """Сохраняет данные в файл с улучшенной обработкой ошибок"""
        try:
            RECIPES_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # Создаем временный файл для безопасного сохранения
            temp_file = RECIPES_FILE.with_suffix('.tmp')
            data_to_save = dict(self.data)
            
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            
            # Заменяем оригинальный файл временным
            temp_file.replace(RECIPES_FILE)
            self.save_to_history()
            return True
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить файл:\n{str(e)}")
            return False
    
    def create_widgets(self):
        # Создаем Notebook для вкладок
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Вкладка "Рецепты"
        self.recipes_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.recipes_tab, text="📖 Рецепты")
        self.create_recipes_tab()
        
        # Другие вкладки
        self.create_meal_planner()
        self.create_statistics_tab()
        self.search_by_ingredients()
    
    def create_recipes_tab(self):
        # Панель управления - две одинаковые панели рядом
        control_panel = ttk.Frame(self.recipes_tab)
        control_panel.pack(pady=10, padx=10, fill=tk.X)
        
        # Панель управления группами
        group_frame = ttk.LabelFrame(control_panel, text="Управление группами", padding=5)
        group_frame.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        group_buttons = ttk.Frame(group_frame)
        group_buttons.pack()
        
        btn1 = ttk.Button(group_buttons, text="➕ Новая группа", command=self.add_group_dialog, width=14)
        btn1.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn1, "Создать новую группу рецептов (Ctrl+G)")
        
        btn2 = ttk.Button(group_buttons, text="✏️ Переименовать", command=self.rename_group, width=14)
        btn2.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn2, "Переименовать выбранную группу")
        
        btn3 = ttk.Button(group_buttons, text="❌ Удалить группу", command=self.delete_group, width=14)
        btn3.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn3, "Удалить выбранную группу и все рецепты в ней")
        
        btn4 = ttk.Button(group_buttons, text="⬆️ Вверх", command=self.move_group_up, width=8)
        btn4.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn4, "Переместить группу вверх в списке")
        
        btn5 = ttk.Button(group_buttons, text="⬇️ Вниз", command=self.move_group_down, width=8)
        btn5.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn5, "Переместить группу вниз в списке")
        
        # Панель управления рецептами (такая же ширина)
        recipe_frame = ttk.LabelFrame(control_panel, text="Управление рецептами", padding=5)
        recipe_frame.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        recipe_buttons = ttk.Frame(recipe_frame)
        recipe_buttons.pack()
        
        btn_r1 = ttk.Button(recipe_buttons, text="📝 Добавить рецепт", command=self.add_recipe_dialog, width=14)
        btn_r1.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn_r1, "Добавить новый рецепт в выбранную группу (Ctrl+N)")
        
        btn_r2 = ttk.Button(recipe_buttons, text="✏️ Редактировать", command=self.edit_recipe_dialog, width=14)
        btn_r2.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn_r2, "Редактировать выбранный рецепт")
        
        btn_r3 = ttk.Button(recipe_buttons, text="❌ Удалить рецепт", command=self.delete_recipe, width=14)
        btn_r3.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn_r3, "Удалить выбранный рецепт (Delete)")
        
        btn_r4 = ttk.Button(recipe_buttons, text="📋 Копировать", command=self.copy_recipe_to_group, width=12)
        btn_r4.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn_r4, "Копировать рецепт в другую группу")
        
        btn_r5 = ttk.Button(recipe_buttons, text="⬆️ Вверх", command=self.move_recipe_up, width=8)
        btn_r5.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn_r5, "Переместить рецепт вверх в списке")
        
        btn_r6 = ttk.Button(recipe_buttons, text="⬇️ Вниз", command=self.move_recipe_down, width=8)
        btn_r6.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn_r6, "Переместить рецепт вниз в списке")
        
        btn_r7 = ttk.Button(recipe_buttons, text="🍳 Режим готовки", command=self.cooking_mode, width=12)
        btn_r7.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn_r7, "Запустить пошаговый режим приготовления с таймером")
        
        btn_r8 = ttk.Button(recipe_buttons, text="🎲 Случайный", command=self.random_recipe, width=10)
        btn_r8.pack(side=tk.LEFT, padx=2)
        add_tooltip(btn_r8, "Выбрать случайный рецепт")
        
        # Поиск и фильтры
        search_frame = ttk.Frame(self.recipes_tab)
        search_frame.pack(pady=5, fill=tk.X, padx=20)
        
        ttk.Label(search_frame, text="🔍 Поиск:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *args: self.refresh_recipe_list())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=5)
        add_tooltip(search_entry, "Поиск рецептов по названию (Ctrl+F)")
        
        self.favorite_filter_var = tk.BooleanVar()
        fav_check = ttk.Checkbutton(search_frame, text="⭐ Только избранные", variable=self.favorite_filter_var, 
                       command=self.refresh_recipe_list)
        fav_check.pack(side=tk.LEFT, padx=10)
        add_tooltip(fav_check, "Показывать только рецепты, добавленные в избранное")
        
        ttk.Label(search_frame, text="⏱️ Время:").pack(side=tk.LEFT, padx=5)
        self.time_filter_var = tk.StringVar()
        self.time_filter_var.set("Все")
        time_combo = ttk.Combobox(search_frame, textvariable=self.time_filter_var, 
                                  values=["Все", "≤ 15 мин", "15-30 мин", "30-60 мин", "≥ 60 мин"], 
                                  width=10, state="readonly")
        time_combo.pack(side=tk.LEFT, padx=5)
        time_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_recipe_list())
        add_tooltip(time_combo, "Фильтр по времени приготовления")
        
        ttk.Label(search_frame, text="Сложность:").pack(side=tk.LEFT, padx=5)
        self.difficulty_filter_var = tk.StringVar()
        self.difficulty_filter_var.set("Все")
        difficulty_combo = ttk.Combobox(search_frame, textvariable=self.difficulty_filter_var,
                                        values=["Все", "Легко", "Средне", "Сложно"],
                                        width=8, state="readonly")
        difficulty_combo.pack(side=tk.LEFT, padx=5)
        difficulty_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_recipe_list())
        add_tooltip(difficulty_combo, "Фильтр по сложности приготовления")
        
        # Фильтр по тегам
        ttk.Label(search_frame, text="🏷️ Теги:").pack(side=tk.LEFT, padx=5)
        self.tags_filter_var = tk.StringVar()
        self.tags_filter_var.set("Все теги")
        self.tags_filter_combo = ttk.Combobox(search_frame, textvariable=self.tags_filter_var, 
                                              values=["Все теги"], width=15, state="readonly")
        self.tags_filter_combo.pack(side=tk.LEFT, padx=5)
        self.tags_filter_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_recipe_list())
        add_tooltip(self.tags_filter_combo, "Фильтр по тегам рецептов")
        
        reset_btn = ttk.Button(search_frame, text="🗑️ Сбросить", command=self.reset_filters)
        reset_btn.pack(side=tk.LEFT, padx=10)
        add_tooltip(reset_btn, "Сбросить все фильтры")
        
        # Основная область
        main_frame = ttk.Frame(self.recipes_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Левая панель - группы
        left_frame = ttk.LabelFrame(main_frame, text="Группы рецептов", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        self.group_listbox = tk.Listbox(left_frame, width=28, height=25, font=("Arial", 10))
        self.group_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        add_tooltip(self.group_listbox, "Список групп. Кликните для выбора группы")
        
        group_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.group_listbox.yview)
        group_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.group_listbox.config(yscrollcommand=group_scroll.set)
        
        self.group_listbox.bind('<<ListboxSelect>>', self.on_group_select)
        self.group_listbox.bind("<Button-3>", self.show_group_context_menu)
        
        # Средняя панель - рецепты
        middle_frame = ttk.LabelFrame(main_frame, text="Рецепты в группе", padding=5)
        middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.recipe_listbox = tk.Listbox(middle_frame, width=32, height=25, font=("Arial", 10))
        self.recipe_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        add_tooltip(self.recipe_listbox, "Список рецептов в выбранной группе. Кликните для просмотра")
        
        recipe_scroll = ttk.Scrollbar(middle_frame, orient=tk.VERTICAL, command=self.recipe_listbox.yview)
        recipe_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.recipe_listbox.config(yscrollcommand=recipe_scroll.set)
        
        self.recipe_listbox.bind('<<ListboxSelect>>', self.on_recipe_select)
        self.recipe_listbox.bind("<Button-3>", self.show_recipe_context_menu)
        
        # Правая панель - детали рецепта
        right_frame = ttk.LabelFrame(main_frame, text="Детали рецепта", padding=5)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Создаем панель инструментов для редактирования
        edit_toolbar = ttk.Frame(right_frame)
        edit_toolbar.pack(fill=tk.X, pady=(0, 10))
        
        edit_btn = ttk.Button(edit_toolbar, text="✏️ Редактировать рецепт", command=self.edit_recipe_dialog)
        edit_btn.pack(side=tk.LEFT, padx=2)
        add_tooltip(edit_btn, "Открыть окно редактирования рецепта")
        
        save_btn = ttk.Button(edit_toolbar, text="💾 Сохранить изменения", command=self.save_current_recipe)
        save_btn.pack(side=tk.LEFT, padx=2)
        add_tooltip(save_btn, "Сохранить изменения в текущем рецепте (Ctrl+S)")
        
        # Верхняя часть правой панели - фото и информация
        top_right_frame = ttk.Frame(right_frame)
        top_right_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Фото
        photo_frame = ttk.LabelFrame(top_right_frame, text="Фото блюда", padding=5)
        photo_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.photo_label = ttk.Label(photo_frame, text="Нет фото", relief=tk.SUNKEN)
        self.photo_label.pack(pady=5)
        add_tooltip(self.photo_label, "Здесь будет отображаться фото выбранного блюда")
        
        photo_buttons_frame = ttk.Frame(photo_frame)
        photo_buttons_frame.pack(pady=5)
        
        add_photo_btn = ttk.Button(photo_buttons_frame, text="📸 Добавить фото", command=self.add_photo)
        add_photo_btn.pack(side=tk.LEFT, padx=2)
        add_tooltip(add_photo_btn, "Добавить фото к рецепту")
        
        remove_photo_btn = ttk.Button(photo_buttons_frame, text="🗑️ Удалить фото", command=self.remove_photo)
        remove_photo_btn.pack(side=tk.LEFT, padx=2)
        add_tooltip(remove_photo_btn, "Удалить фото рецепта")
        
        # Информация о рецепте (редактируемая)
        info_frame = ttk.LabelFrame(top_right_frame, text="Информация", padding=5)
        info_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # Название и избранное
        name_frame = ttk.Frame(info_frame)
        name_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(name_frame, text="Название:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.name_label = ttk.Label(name_frame, text="", font=("Arial", 11, "bold"), wraplength=180)
        self.name_label.pack(side=tk.LEFT, padx=(5, 10))
        add_tooltip(self.name_label, "Название текущего рецепта")
        
        self.favorite_btn = ttk.Button(name_frame, text="☆", width=3, command=self.toggle_favorite)
        self.favorite_btn.pack(side=tk.RIGHT)
        add_tooltip(self.favorite_btn, "Добавить/удалить рецепт из избранного")
        
        # Группа
        group_info_frame = ttk.Frame(info_frame)
        group_info_frame.pack(fill=tk.X, pady=5)
        ttk.Label(group_info_frame, text="Группа:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.group_label = ttk.Label(group_info_frame, text="", font=("Arial", 10), wraplength=180)
        self.group_label.pack(side=tk.LEFT, padx=(5, 0))
        add_tooltip(self.group_label, "Группа, к которой относится рецепт")
        
        # Время
        time_frame = ttk.Frame(info_frame)
        time_frame.pack(fill=tk.X, pady=5)
        ttk.Label(time_frame, text="⏱️ Время (мин):", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.time_entry = ttk.Entry(time_frame, width=8)
        self.time_entry.pack(side=tk.LEFT, padx=(5, 15))
        add_tooltip(self.time_entry, "Время приготовления в минутах")
        
        # Сложность
        difficulty_frame = ttk.Frame(info_frame)
        difficulty_frame.pack(fill=tk.X, pady=5)
        ttk.Label(difficulty_frame, text="📊 Сложность:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.difficulty_combo = ttk.Combobox(difficulty_frame, values=["Легко", "Средне", "Сложно"], width=8, state="readonly")
        self.difficulty_combo.pack(side=tk.LEFT, padx=(5, 0))
        add_tooltip(self.difficulty_combo, "Уровень сложности приготовления")
        
        # Порции
        servings_frame = ttk.Frame(info_frame)
        servings_frame.pack(fill=tk.X, pady=5)
        ttk.Label(servings_frame, text="👥 Порции:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.servings_spin = ttk.Spinbox(servings_frame, from_=1, to=20, width=6)
        self.servings_spin.pack(side=tk.LEFT, padx=(5, 10))
        add_tooltip(self.servings_spin, "Количество порций")
        
        scale_btn = ttk.Button(servings_frame, text="🔄", width=3, command=self.scale_recipe)
        scale_btn.pack(side=tk.LEFT)
        add_tooltip(scale_btn, "Пересчитать ингредиенты на указанное количество порций")
        
        # Теги
        tags_frame_inner = ttk.Frame(info_frame)
        tags_frame_inner.pack(fill=tk.X, pady=5)
        ttk.Label(tags_frame_inner, text="🏷️ Теги:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.tags_entry = ttk.Entry(tags_frame_inner, width=20)
        self.tags_entry.pack(side=tk.LEFT, padx=(5, 0))
        add_tooltip(self.tags_entry, "Теги рецепта через запятую (например: завтрак, быстро, вегетарианское)")
        
        # Ингредиенты
        ttk.Label(right_frame, text="Ингредиенты:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        ingredients_frame = ttk.Frame(right_frame)
        ingredients_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.ingredients_text = tk.Text(ingredients_frame, height=7, wrap=tk.WORD, font=("Arial", 10))
        ingredients_scroll = ttk.Scrollbar(ingredients_frame, orient=tk.VERTICAL, command=self.ingredients_text.yview)
        self.ingredients_text.configure(yscrollcommand=ingredients_scroll.set)
        self.ingredients_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ingredients_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        add_tooltip(self.ingredients_text, "Список ингредиентов (каждый с новой строки)")
        
        # Приготовление
        ttk.Label(right_frame, text="Приготовление:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        steps_frame = ttk.Frame(right_frame)
        steps_frame.pack(fill=tk.BOTH, expand=True)
        
        self.steps_text = tk.Text(steps_frame, height=9, wrap=tk.WORD, font=("Arial", 10))
        steps_scroll = ttk.Scrollbar(steps_frame, orient=tk.VERTICAL, command=self.steps_text.yview)
        self.steps_text.configure(yscrollcommand=steps_scroll.set)
        self.steps_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        steps_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        add_tooltip(self.steps_text, "Пошаговый рецепт приготовления (каждый шаг с новой строки)")
    
    def export_csv(self):
        """Экспорт всех рецептов в CSV файл"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Группа', 'Название', 'Время', 'Сложность', 'Порции', 'Теги', 'Ингредиенты', 'Приготовление', 'Избранное'])
                    
                    for group, recipes in self.data.items():
                        for name, recipe in recipes.items():
                            writer.writerow([
                                group,
                                name,
                                recipe.get('time', 0),
                                recipe.get('difficulty', ''),
                                recipe.get('servings', 2),
                                ', '.join(recipe.get('tags', [])),
                                recipe.get('ingredients', ''),
                                recipe.get('steps', ''),
                                'Да' if recipe.get('favorite', False) else 'Нет'
                            ])
                
                self.update_status(f"CSV файл создан: {filename}")
                messagebox.showinfo("Успех", f"CSV файл создан: {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось создать CSV: {str(e)}")
    
    def export_html(self):
        """Экспорт рецепта в HTML файл"""
        if not self.current_recipe:
            messagebox.showwarning("Предупреждение", "Выберите рецепт")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                recipe = self.data[self.current_group][self.current_recipe]
                
                html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{self.current_recipe}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
        .recipe-card {{ background: white; border-radius: 20px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }}
        h1 {{ color: #667eea; border-bottom: 3px solid #667eea; padding-bottom: 10px; }}
        .info {{ background: #f8f9fa; padding: 15px; border-radius: 10px; margin: 20px 0; }}
        .info-item {{ margin: 5px 0; }}
        .tag {{ display: inline-block; background: #e0e0e0; padding: 3px 10px; border-radius: 15px; margin: 2px; font-size: 12px; }}
        h2 {{ color: #333; margin-top: 20px; }}
        .ingredients, .steps {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 15px 0; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="recipe-card">
        <h1>🍳 {self.current_recipe} {'⭐' if recipe.get('favorite', False) else ''}</h1>
        
        <div class="info">
            <div class="info-item"><strong>📁 Группа:</strong> {self.current_group}</div>
            <div class="info-item"><strong>⏱️ Время:</strong> {recipe.get('time', 0)} мин</div>
            <div class="info-item"><strong>📊 Сложность:</strong> {recipe.get('difficulty', 'Не указана')}</div>
            <div class="info-item"><strong>👥 Порции:</strong> {recipe.get('servings', 2)}</div>
            <div class="info-item"><strong>🏷️ Теги:</strong> {', '.join([f'<span class="tag">{tag}</span>' for tag in recipe.get('tags', [])])}</div>
        </div>
        
        <h2>📝 Ингредиенты</h2>
        <div class="ingredients">
            {recipe.get('ingredients', '').replace(chr(10), '<br>')}
        </div>
        
        <h2>🍳 Приготовление</h2>
        <div class="steps">
            {recipe.get('steps', '').replace(chr(10), '<br>')}
        </div>
        
        <div class="footer">
            Создано в Кулинарной книге | {datetime.now().strftime('%d.%m.%Y %H:%M')}
        </div>
    </div>
</body>
</html>'''
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                self.update_status(f"HTML файл создан: {filename}")
                messagebox.showinfo("Успех", f"HTML файл создан: {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось создать HTML: {str(e)}")
    
    def edit_recipe_dialog(self):
        """Диалог для редактирования рецепта"""
        if not self.current_recipe:
            messagebox.showwarning("Предупреждение", "Выберите рецепт для редактирования")
            return
        
        recipe = self.data[self.current_group][self.current_recipe]
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Редактирование: {self.current_recipe}")
        dialog.geometry("500x450")
        dialog.resizable(False, False)
        
        # Группа
        ttk.Label(dialog, text="Группа:", font=("Arial", 10, "bold")).pack(pady=(10, 0), anchor=tk.W, padx=20)
        group_var = tk.StringVar(value=self.current_group)
        group_combo = ttk.Combobox(dialog, textvariable=group_var, values=sorted(self.data.keys()), width=40, state="readonly")
        group_combo.pack(pady=5, padx=20, fill=tk.X)
        add_tooltip(group_combo, "Выберите группу для рецепта")
        
        # Название
        ttk.Label(dialog, text="Название блюда:", font=("Arial", 10, "bold")).pack(pady=(10, 0), anchor=tk.W, padx=20)
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.insert(0, self.current_recipe)
        name_entry.pack(pady=5, padx=20, fill=tk.X)
        add_tooltip(name_entry, "Введите название блюда")
        
        # Время
        time_frame = ttk.Frame(dialog)
        time_frame.pack(pady=5, padx=20, fill=tk.X)
        ttk.Label(time_frame, text="⏱️ Время (мин):", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        time_spin = ttk.Spinbox(time_frame, from_=1, to=300, width=10)
        time_spin.set(recipe.get("time", 0))
        time_spin.pack(side=tk.LEFT)
        add_tooltip(time_spin, "Время приготовления в минутах")
        
        # Сложность
        difficulty_frame = ttk.Frame(dialog)
        difficulty_frame.pack(pady=5, padx=20, fill=tk.X)
        ttk.Label(difficulty_frame, text="📊 Сложность:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        difficulty_combo = ttk.Combobox(difficulty_frame, values=["Легко", "Средне", "Сложно"], width=10, state="readonly")
        difficulty_combo.set(recipe.get("difficulty", "Легко"))
        difficulty_combo.pack(side=tk.LEFT)
        add_tooltip(difficulty_combo, "Уровень сложности приготовления")
        
        # Порции
        servings_frame = ttk.Frame(dialog)
        servings_frame.pack(pady=5, padx=20, fill=tk.X)
        ttk.Label(servings_frame, text="👥 Порции:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        servings_spin = ttk.Spinbox(servings_frame, from_=1, to=20, width=10)
        servings_spin.set(recipe.get("servings", 2))
        servings_spin.pack(side=tk.LEFT)
        add_tooltip(servings_spin, "Количество порций")
        
        # Избранное
        favorite_var = tk.BooleanVar(value=recipe.get("favorite", False))
        fav_check = ttk.Checkbutton(dialog, text="⭐ В избранном", variable=favorite_var)
        fav_check.pack(anchor=tk.W, padx=20, pady=5)
        add_tooltip(fav_check, "Добавить рецепт в избранное")
        
        # Теги
        ttk.Label(dialog, text="🏷️ Теги (через запятую):", font=("Arial", 10, "bold")).pack(pady=(10, 0), anchor=tk.W, padx=20)
        tags_entry = ttk.Entry(dialog, width=40)
        tags_entry.insert(0, ", ".join(recipe.get("tags", [])))
        tags_entry.pack(pady=5, padx=20, fill=tk.X)
        add_tooltip(tags_entry, "Теги рецепта через запятую")
        
        def save_changes():
            new_group = group_var.get()
            new_name = name_entry.get().strip()
            
            if not new_name:
                messagebox.showerror("Ошибка", "Введите название блюда")
                return
            
            tags_text = tags_entry.get().strip()
            tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]
            
            updated_recipe = {
                "ingredients": recipe.get("ingredients", ""),
                "steps": recipe.get("steps", ""),
                "time": int(time_spin.get()) if time_spin.get().isdigit() else 0,
                "difficulty": difficulty_combo.get(),
                "tags": tags,
                "favorite": favorite_var.get(),
                "servings": int(servings_spin.get()) if servings_spin.get().isdigit() else 2
            }
            
            if "image_path" in recipe:
                updated_recipe["image_path"] = recipe["image_path"]
            
            if new_group != self.current_group:
                del self.data[self.current_group][self.current_recipe]
                if new_group not in self.data:
                    self.data[new_group] = OrderedDict()
                self.data[new_group][new_name] = updated_recipe
                self.current_group = new_group
            else:
                if new_name != self.current_recipe:
                    del self.data[self.current_group][self.current_recipe]
                    self.data[self.current_group][new_name] = updated_recipe
                    self.current_recipe = new_name
                else:
                    self.data[self.current_group][self.current_recipe] = updated_recipe
            
            self.save_data()
            self.refresh_group_list()
            self.refresh_recipe_list()
            self.update_tags_list()
            self.on_recipe_select(None)
            
            self.update_status(f"Рецепт '{new_name}' обновлен")
            messagebox.showinfo("Успех", "Рецепт обновлен!")
            dialog.destroy()
        
        save_btn = ttk.Button(dialog, text="Сохранить изменения", command=save_changes)
        save_btn.pack(pady=20)
        add_tooltip(save_btn, "Сохранить изменения в рецепте")
    
    def save_current_recipe(self):
        """Сохраняет текущий рецепт из полей ввода"""
        if self.current_group and self.current_recipe:
            tags_text = self.tags_entry.get().strip()
            tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]
            
            current_recipe = self.data[self.current_group][self.current_recipe]
            image_path = current_recipe.get("image_path")
            favorite = current_recipe.get("favorite", False)
            
            time_value = self.time_entry.get()
            try:
                time_int = int(time_value) if time_value else 0
            except:
                time_int = 0
            
            servings_value = self.servings_spin.get()
            try:
                servings_int = int(servings_value) if servings_value else 2
            except:
                servings_int = 2
            
            self.data[self.current_group][self.current_recipe] = {
                "ingredients": self.ingredients_text.get(1.0, tk.END).strip(),
                "steps": self.steps_text.get(1.0, tk.END).strip(),
                "time": time_int,
                "difficulty": self.difficulty_combo.get(),
                "tags": tags,
                "favorite": favorite,
                "servings": servings_int
            }
            
            if image_path:
                self.data[self.current_group][self.current_recipe]["image_path"] = image_path
            
            if self.save_data():
                self.update_tags_list()
                self.update_status(f"Рецепт '{self.current_recipe}' сохранен")
                messagebox.showinfo("Успех", f"Рецепт '{self.current_recipe}' сохранен!")
                self.refresh_recipe_list()
                self.refresh_group_list()
    
    def create_meal_planner(self):
        """Создает вкладку планировщика меню"""
        self.meal_planner_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.meal_planner_tab, text="📅 Планировщик меню")
        
        # Верхняя панель
        top_frame = ttk.Frame(self.meal_planner_tab)
        top_frame.pack(pady=10, padx=10, fill=tk.X)
        
        btn1 = ttk.Button(top_frame, text="➕ Добавить в план", command=self.add_to_meal_plan)
        btn1.pack(side=tk.LEFT, padx=5)
        add_tooltip(btn1, "Добавить текущий рецепт в план питания")
        
        btn2 = ttk.Button(top_frame, text="🛒 Создать список покупок", command=self.create_shopping_list)
        btn2.pack(side=tk.LEFT, padx=5)
        add_tooltip(btn2, "Создать список покупок на основе плана питания")
        
        btn3 = ttk.Button(top_frame, text="📋 Показать список", command=self.show_shopping_list)
        btn3.pack(side=tk.LEFT, padx=5)
        add_tooltip(btn3, "Показать сохраненный список покупок")
        
        btn4 = ttk.Button(top_frame, text="🔄 Повторить меню", command=self.repeat_meal_plan)
        btn4.pack(side=tk.LEFT, padx=5)
        add_tooltip(btn4, "Повторить меню на следующую неделю")
        
        btn5 = ttk.Button(top_frame, text="🗑️ Очистить план", command=self.clear_meal_plan)
        btn5.pack(side=tk.LEFT, padx=5)
        add_tooltip(btn5, "Очистить весь план питания")
        
        # Создаем canvas с прокруткой
        canvas_frame = ttk.Frame(self.meal_planner_tab)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        self.meal_plan_frame = ttk.Frame(canvas)
        
        self.meal_plan_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.meal_plan_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.update_meal_plan_display()
    
    def update_meal_plan_display(self):
        """Обновляет отображение плана питания"""
        for widget in self.meal_plan_frame.winfo_children():
            widget.destroy()
        
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        meals = ["Завтрак", "Обед", "Ужин"]
        
        # Заголовки
        header_frame = ttk.Frame(self.meal_plan_frame)
        header_frame.pack(fill=tk.X, pady=5)
        ttk.Label(header_frame, text="", width=15).pack(side=tk.LEFT)
        for meal in meals:
            ttk.Label(header_frame, text=meal, width=30, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        # Дни недели
        for day in days:
            day_frame = ttk.Frame(self.meal_plan_frame)
            day_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(day_frame, text=day, width=15, font=("Arial", 10, "bold")).pack(side=tk.LEFT)
            
            for meal in meals:
                key = f"{day}_{meal}"
                recipe_name = self.meal_plan.get(key, "")
                
                meal_frame = ttk.Frame(day_frame)
                meal_frame.pack(side=tk.LEFT, padx=5)
                
                if recipe_name:
                    ttk.Label(meal_frame, text=recipe_name, width=30, wraplength=200).pack(side=tk.LEFT)
                    del_btn = ttk.Button(meal_frame, text="❌", width=2, 
                              command=lambda k=key: self.remove_from_meal_plan(k))
                    del_btn.pack(side=tk.LEFT)
                    add_tooltip(del_btn, f"Удалить {recipe_name} из плана")
                else:
                    ttk.Label(meal_frame, text="—", width=30).pack(side=tk.LEFT)
    
    def add_to_meal_plan(self):
        if not self.current_recipe:
            messagebox.showwarning("Предупреждение", "Сначала выберите рецепт")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить в план питания")
        dialog.geometry("300x200")
        
        ttk.Label(dialog, text="Выберите день и прием пищи:").pack(pady=10)
        
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_var = tk.StringVar(value=days[0])
        day_combo = ttk.Combobox(dialog, textvariable=day_var, values=days, width=20, state="readonly")
        day_combo.pack(pady=5)
        add_tooltip(day_combo, "Выберите день недели")
        
        meals = ["Завтрак", "Обед", "Ужин"]
        meal_var = tk.StringVar(value=meals[0])
        meal_combo = ttk.Combobox(dialog, textvariable=meal_var, values=meals, width=20, state="readonly")
        meal_combo.pack(pady=5)
        add_tooltip(meal_combo, "Выберите прием пищи")
        
        def save():
            key = f"{day_var.get()}_{meal_var.get()}"
            self.meal_plan[key] = self.current_recipe
            self.save_meal_plan()
            self.update_meal_plan_display()
            dialog.destroy()
            self.update_status(f"Рецепт добавлен в план на {day_var.get()} ({meal_var.get()})")
            messagebox.showinfo("Успех", f"Рецепт добавлен в план на {day_var.get()} ({meal_var.get()})")
        
        save_btn = ttk.Button(dialog, text="Добавить", command=save)
        save_btn.pack(pady=10)
        add_tooltip(save_btn, "Добавить рецепт в план питания")
    
    def remove_from_meal_plan(self, key):
        if key in self.meal_plan:
            del self.meal_plan[key]
            self.save_meal_plan()
            self.update_meal_plan_display()
            self.update_status("Блюдо удалено из плана")
    
    def create_shopping_list(self):
        ingredients = []
        for recipe_name in self.meal_plan.values():
            for group, recipes in self.data.items():
                if recipe_name in recipes:
                    recipe_ingredients = recipes[recipe_name].get("ingredients", "")
                    for line in recipe_ingredients.split("\n"):
                        if line.strip():
                            ingredients.append(line.strip())
                    break
        
        ingredient_counts = Counter(ingredients)
        self.shopping_list = [f"{count}x {item}" if count > 1 else item for item, count in ingredient_counts.items()]
        self.show_shopping_list()
    
    def show_shopping_list(self):
        if not self.shopping_list:
            messagebox.showinfo("Информация", "Список покупок пуст.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("🛒 Список покупок")
        dialog.geometry("400x500")
        
        text_widget = tk.Text(dialog, wrap=tk.WORD, font=("Arial", 12))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text_widget.insert(tk.END, "🛒 СПИСОК ПОКУПОК\n")
        text_widget.insert(tk.END, "="*30 + "\n\n")
        
        for item in sorted(self.shopping_list):
            text_widget.insert(tk.END, f"☐ {item}\n")
        
        text_widget.config(state=tk.DISABLED)
        add_tooltip(text_widget, "Список продуктов для покупки")
    
    def repeat_meal_plan(self):
        new_plan = {}
        for key, value in self.meal_plan.items():
            new_plan[key] = value
        self.meal_plan = new_plan
        self.save_meal_plan()
        self.update_meal_plan_display()
        self.update_status("Меню повторено на следующую неделю")
        messagebox.showinfo("Успех", "Меню повторено!")
    
    def clear_meal_plan(self):
        if messagebox.askyesno("Подтверждение", "Очистить весь план питания?"):
            self.meal_plan = {}
            self.save_meal_plan()
            self.update_meal_plan_display()
            self.update_status("План питания очищен")
    
    def create_statistics_tab(self):
        self.statistics_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.statistics_tab, text="📊 Статистика")
        
        canvas_frame = ttk.Frame(self.statistics_tab)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        stats_frame = ttk.Frame(canvas)
        
        stats_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=stats_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.update_statistics(stats_frame)
    
    def update_statistics(self, parent_frame):
        total_recipes = sum(len(recipes) for recipes in self.data.values())
        total_groups = len(self.data)
        
        all_tags = []
        all_ingredients = []
        times = []
        difficulties = []
        
        for group, recipes in self.data.items():
            for recipe_name, recipe_data in recipes.items():
                tags = recipe_data.get("tags", [])
                all_tags.extend(tags)
                
                ingredients = recipe_data.get("ingredients", "")
                for line in ingredients.split("\n"):
                    if line.strip():
                        all_ingredients.append(line.strip())
                
                time_val = recipe_data.get("time", 0)
                if time_val:
                    times.append(time_val)
                
                difficulty = recipe_data.get("difficulty", "")
                if difficulty:
                    difficulties.append(difficulty)
        
        # Общая информация
        info_frame = ttk.LabelFrame(parent_frame, text="Общая информация", padding=10)
        info_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(info_frame, text=f"📚 Всего рецептов: {total_recipes}", font=("Arial", 12)).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"📁 Всего групп: {total_groups}", font=("Arial", 12)).pack(anchor=tk.W)
        
        if times:
            avg_time = sum(times) / len(times)
            ttk.Label(info_frame, text=f"⏱️ Среднее время: {avg_time:.0f} мин", font=("Arial", 12)).pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"⚡ Самый быстрый: {min(times)} мин", font=("Arial", 12)).pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"🐢 Самый долгий: {max(times)} мин", font=("Arial", 12)).pack(anchor=tk.W)
        
        # Популярные теги
        if all_tags:
            tag_counts = Counter(all_tags)
            popular_tags = tag_counts.most_common(10)
            
            tags_frame = ttk.LabelFrame(parent_frame, text="🏷️ Популярные теги", padding=10)
            tags_frame.pack(fill=tk.X, pady=10)
            
            for tag, count in popular_tags:
                ttk.Label(tags_frame, text=f"{tag}: {count} рецепт(ов)", font=("Arial", 11)).pack(anchor=tk.W)
        
        # Частые ингредиенты
        if all_ingredients:
            ingredient_counts = Counter(all_ingredients)
            common_ingredients = ingredient_counts.most_common(15)
            
            ingredients_frame = ttk.LabelFrame(parent_frame, text="🥕 Частые ингредиенты", padding=10)
            ingredients_frame.pack(fill=tk.X, pady=10)
            
            for ingredient, count in common_ingredients:
                ttk.Label(ingredients_frame, text=f"{ingredient[:50]}: {count} раз", font=("Arial", 11)).pack(anchor=tk.W)
        
        # Распределение по сложности
        if difficulties:
            difficulty_counts = Counter(difficulties)
            diff_frame = ttk.LabelFrame(parent_frame, text="📊 Распределение по сложности", padding=10)
            diff_frame.pack(fill=tk.X, pady=10)
            
            for diff, count in difficulty_counts.items():
                percent = (count / len(difficulties)) * 100
                ttk.Label(diff_frame, text=f"{diff}: {count} рецепт(ов) ({percent:.1f}%)", font=("Arial", 11)).pack(anchor=tk.W)
    
    def search_by_ingredients(self):
        search_tab = ttk.Frame(self.notebook)
        self.notebook.add(search_tab, text="🔍 Поиск по ингредиентам")
        
        top_frame = ttk.Frame(search_tab)
        top_frame.pack(pady=10, padx=10, fill=tk.X)
        
        ttk.Label(top_frame, text="Ингредиенты (через запятую):").pack(side=tk.LEFT, padx=5)
        self.ingredients_search_entry = ttk.Entry(top_frame, width=30)
        self.ingredients_search_entry.pack(side=tk.LEFT, padx=5)
        add_tooltip(self.ingredients_search_entry, "Введите ингредиенты через запятую (например: курица, рис, помидоры)")
        
        ttk.Label(top_frame, text="Исключить:").pack(side=tk.LEFT, padx=5)
        self.exclude_search_entry = ttk.Entry(top_frame, width=20)
        self.exclude_search_entry.pack(side=tk.LEFT, padx=5)
        add_tooltip(self.exclude_search_entry, "Ингредиенты, которые нужно исключить (аллергены)")
        
        search_btn = ttk.Button(top_frame, text="🔍 Найти", command=self.find_recipes_by_ingredients)
        search_btn.pack(side=tk.LEFT, padx=5)
        add_tooltip(search_btn, "Найти рецепты по указанным ингредиентам")
        
        self.search_results_listbox = tk.Listbox(search_tab, height=20, font=("Arial", 11))
        self.search_results_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.search_results_listbox.bind('<Double-Button-1>', self.open_recipe_from_search)
        add_tooltip(self.search_results_listbox, "Дважды кликните по рецепту, чтобы открыть его")
    
    def find_recipes_by_ingredients(self):
        ingredients_str = self.ingredients_search_entry.get()
        exclude_str = self.exclude_search_entry.get()
        
        ingredients = [i.strip().lower() for i in ingredients_str.split(",") if i.strip()]
        exclude = [e.strip().lower() for e in exclude_str.split(",") if e.strip()]
        
        if not ingredients:
            messagebox.showwarning("Предупреждение", "Введите ингредиенты")
            return
        
        self.search_results_listbox.delete(0, tk.END)
        results = []
        
        for group, recipes in self.data.items():
            for recipe_name, recipe_data in recipes.items():
                recipe_text = recipe_data.get("ingredients", "").lower()
                
                has_all = all(ing in recipe_text for ing in ingredients)
                has_exclude = any(ex in recipe_text for ex in exclude)
                
                if has_all and not has_exclude:
                    found = sum(1 for ing in ingredients if ing in recipe_text)
                    match_percent = (found / len(ingredients)) * 100
                    results.append((recipe_name, group, match_percent))
        
        results.sort(key=lambda x: x[2], reverse=True)
        
        for recipe_name, group, percent in results:
            self.search_results_listbox.insert(tk.END, f"[{percent:.0f}%] {recipe_name} ({group})")
        
        if not results:
            self.search_results_listbox.insert(tk.END, "Рецепты не найдены")
        else:
            self.update_status(f"Найдено {len(results)} рецептов")
    
    def open_recipe_from_search(self, event):
        selection = self.search_results_listbox.curselection()
        if selection:
            text = self.search_results_listbox.get(selection[0])
            if "(" in text:
                recipe_part = text.split(" (")[0]
                recipe_name = recipe_part.split("] ")[1] if "] " in recipe_part else recipe_part
                group = text.split("(")[1].replace(")", "")
                
                self.current_group = group
                self.current_recipe = recipe_name
                self.refresh_group_list()
                self.refresh_recipe_list()
                self.on_recipe_select(None)
                self.notebook.select(0)
                self.update_status(f"Открыт рецепт: {recipe_name}")
    
    def scale_recipe(self):
        if not self.current_recipe:
            return
        
        target_servings = int(self.servings_spin.get()) if self.servings_spin.get().isdigit() else 2
        recipe = self.data[self.current_group][self.current_recipe]
        original_servings = recipe.get("servings", 2)
        
        if original_servings == target_servings:
            return
        
        scale_factor = target_servings / original_servings
        
        ingredients = recipe.get("ingredients", "")
        scaled_ingredients = []
        
        for line in ingredients.split("\n"):
            if line.strip():
                numbers = re.findall(r'(\d+(?:\.\d+)?)', line)
                scaled_line = line
                for num in numbers:
                    try:
                        scaled_num = float(num) * scale_factor
                        if scaled_num.is_integer():
                            scaled_num = int(scaled_num)
                        else:
                            scaled_num = round(scaled_num, 1)
                        scaled_line = scaled_line.replace(num, str(scaled_num), 1)
                    except:
                        pass
                scaled_ingredients.append(scaled_line)
            else:
                scaled_ingredients.append(line)
        
        self.ingredients_text.delete(1.0, tk.END)
        self.ingredients_text.insert(1.0, "\n".join(scaled_ingredients))
        self.update_status(f"Ингредиенты пересчитаны на {target_servings} порций")
        messagebox.showinfo("Успех", f"Ингредиенты пересчитаны на {target_servings} порций!")
    
    def cooking_mode(self):
        if not self.current_recipe:
            messagebox.showwarning("Предупреждение", "Выберите рецепт")
            return
        
        recipe = self.data[self.current_group][self.current_recipe]
        steps = [s.strip() for s in recipe.get("steps", "").split("\n") if s.strip()]
        
        if not steps:
            messagebox.showwarning("Предупреждение", "Нет шагов приготовления")
            return
        
        cooking_window = tk.Toplevel(self.root)
        cooking_window.title(f"🍳 Приготовление: {self.current_recipe}")
        cooking_window.geometry("800x700")
        
        fullscreen = False
        def toggle_fullscreen():
            nonlocal fullscreen
            fullscreen = not fullscreen
            cooking_window.attributes('-fullscreen', fullscreen)
        
        top_bar = ttk.Frame(cooking_window)
        top_bar.pack(fill=tk.X, pady=5)
        
        fs_btn = ttk.Button(top_bar, text="⛶ Полный экран", command=toggle_fullscreen)
        fs_btn.pack(side=tk.LEFT, padx=5)
        add_tooltip(fs_btn, "Переключить полноэкранный режим (F11)")
        
        close_btn = ttk.Button(top_bar, text="✖ Закрыть", command=cooking_window.destroy)
        close_btn.pack(side=tk.RIGHT, padx=5)
        add_tooltip(close_btn, "Закрыть режим приготовления")
        
        content_frame = ttk.Frame(cooking_window)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        step_label = ttk.Label(content_frame, text="", font=("Arial", 16), wraplength=700, justify=tk.CENTER)
        step_label.pack(pady=20)
        add_tooltip(step_label, "Текущий шаг приготовления")
        
        timer_label = ttk.Label(content_frame, text="", font=("Arial", 48, "bold"))
        timer_label.pack(pady=20)
        add_tooltip(timer_label, "Таймер обратного отсчета")
        
        progress_var = tk.IntVar()
        progress_bar = ttk.Progressbar(content_frame, variable=progress_var, maximum=len(steps))
        progress_bar.pack(fill=tk.X, pady=10)
        add_tooltip(progress_bar, "Прогресс приготовления")
        
        # Поле для заметок
        notes_frame = ttk.LabelFrame(content_frame, text="📝 Мои заметки", padding=10)
        notes_frame.pack(fill=tk.X, pady=10)
        
        notes_text = tk.Text(notes_frame, height=4, wrap=tk.WORD, font=("Arial", 10))
        notes_text.pack(fill=tk.X)
        add_tooltip(notes_text, "Заметки к текущему приготовлению")
        
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(pady=20)
        
        step_index = 0
        timer_running = False
        timer_id = None
        
        def save_note():
            note = notes_text.get(1.0, tk.END).strip()
            if note:
                notes_file = NOTES_FOLDER / f"cooking_note_{self.current_recipe}_{datetime.now().strftime('%Y%m%d')}.txt"
                with open(notes_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {note}\n")
                notes_text.delete(1.0, tk.END)
                self.update_status("Заметка сохранена")
                messagebox.showinfo("Заметка", "Заметка сохранена!")
        
        save_note_btn = ttk.Button(notes_frame, text="💾 Сохранить заметку", command=save_note)
        save_note_btn.pack(pady=5)
        add_tooltip(save_note_btn, "Сохранить текущую заметку")
        
        def update_step():
            nonlocal timer_running, timer_id
            if timer_running and timer_id:
                cooking_window.after_cancel(timer_id)
                timer_running = False
            
            step_label.config(text=f"Шаг {step_index + 1}/{len(steps)}\n\n{steps[step_index]}")
            progress_var.set(step_index + 1)
            
            time_match = re.search(r'(\d+)\s*(?:минут|мин|минуты|min)', steps[step_index], re.IGNORECASE)
            if time_match:
                minutes = int(time_match.group(1))
                start_timer(minutes)
        
        def start_timer(minutes):
            nonlocal timer_running, timer_id
            if timer_running:
                return
            
            seconds_left = minutes * 60
            
            def update_timer():
                nonlocal seconds_left, timer_running, timer_id
                if seconds_left > 0:
                    mins = seconds_left // 60
                    secs = seconds_left % 60
                    timer_label.config(text=f"{mins:02d}:{secs:02d}")
                    seconds_left -= 1
                    timer_id = cooking_window.after(1000, update_timer)
                else:
                    timer_label.config(text="Время вышло!")
                    timer_running = False
                    cooking_window.bell()
                    self.update_status("Время приготовления шага истекло!")
            
            timer_running = True
            timer_label.config(text=f"{minutes:02d}:00")
            update_timer()
        
        def next_step():
            nonlocal step_index, timer_running, timer_id
            if timer_running:
                if messagebox.askyesno("Таймер", "Остановить таймер и продолжить?"):
                    if timer_id:
                        cooking_window.after_cancel(timer_id)
                    timer_running = False
                    timer_label.config(text="")
                else:
                    return
            
            if step_index < len(steps) - 1:
                step_index += 1
                update_step()
            else:
                self.update_status(f"Приготовление '{self.current_recipe}' завершено!")
                messagebox.showinfo("Готово!", "🎉 Приятного аппетита! 🎉")
                cooking_window.destroy()
        
        def prev_step():
            nonlocal step_index, timer_running, timer_id
            if timer_running:
                if timer_id:
                    cooking_window.after_cancel(timer_id)
                timer_running = False
                timer_label.config(text="")
            
            if step_index > 0:
                step_index -= 1
                update_step()
        
        prev_btn = ttk.Button(button_frame, text="◀ Предыдущий", command=prev_step, width=15)
        prev_btn.pack(side=tk.LEFT, padx=10)
        add_tooltip(prev_btn, "Перейти к предыдущему шагу")
        
        next_btn = ttk.Button(button_frame, text="Следующий ▶", command=next_step, width=15)
        next_btn.pack(side=tk.LEFT, padx=10)
        add_tooltip(next_btn, "Перейти к следующему шагу")
        
        update_step()
    
    def export_pdf(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Ошибка", "Установите reportlab: pip install reportlab")
            return
        
        if not self.current_recipe:
            messagebox.showwarning("Предупреждение", "Выберите рецепт")
            return
        
        filename = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if filename:
            try:
                recipe = self.data[self.current_group][self.current_recipe]
                doc = SimpleDocTemplate(filename, pagesize=letter)
                styles = getSampleStyleSheet()
                story = []
                
                title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, spaceAfter=30)
                story.append(Paragraph(self.current_recipe, title_style))
                
                info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=12, spaceAfter=10)
                story.append(Paragraph(f"<b>Группа:</b> {self.current_group}", info_style))
                story.append(Paragraph(f"<b>Время:</b> {recipe.get('time', 0)} мин", info_style))
                story.append(Paragraph(f"<b>Сложность:</b> {recipe.get('difficulty', 'Не указана')}", info_style))
                
                if recipe.get('tags'):
                    story.append(Paragraph(f"<b>Теги:</b> {', '.join(recipe.get('tags', []))}", info_style))
                
                story.append(Spacer(1, 0.2*inch))
                story.append(Paragraph("<b>Ингредиенты:</b>", styles['Heading2']))
                for line in recipe.get("ingredients", "").split("\n"):
                    if line.strip():
                        story.append(Paragraph(f"• {line}", styles['Normal']))
                
                story.append(Spacer(1, 0.2*inch))
                story.append(Paragraph("<b>Приготовление:</b>", styles['Heading2']))
                for i, line in enumerate(recipe.get("steps", "").split("\n"), 1):
                    if line.strip():
                        story.append(Paragraph(f"{i}. {line}", styles['Normal']))
                
                doc.build(story)
                self.update_status(f"PDF создан: {filename}")
                messagebox.showinfo("Успех", f"PDF создан: {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
    
    def send_by_email(self):
        messagebox.showinfo("Информация", "Для отправки email настройте SMTP сервер в коде")
    
    def export_markdown(self):
        if not self.current_recipe:
            messagebox.showwarning("Предупреждение", "Выберите рецепт")
            return
        
        filename = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown", "*.md")])
        if filename:
            recipe = self.data[self.current_group][self.current_recipe]
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# {self.current_recipe}\n\n")
                f.write(f"**Группа:** {self.current_group}  \n")
                f.write(f"**Время:** {recipe.get('time', 0)} мин  \n")
                f.write(f"**Сложность:** {recipe.get('difficulty', 'Не указана')}  \n\n")
                f.write(f"## Ингредиенты\n\n")
                for line in recipe.get("ingredients", "").split("\n"):
                    if line.strip():
                        f.write(f"- {line}\n")
                f.write(f"\n## Приготовление\n\n")
                for i, line in enumerate(recipe.get("steps", "").split("\n"), 1):
                    if line.strip():
                        f.write(f"{i}. {line}\n")
            self.update_status(f"Markdown файл создан: {filename}")
            messagebox.showinfo("Успех", f"Markdown создан: {filename}")
    
    def refresh_group_list(self):
        self.group_listbox.delete(0, tk.END)
        for group in self.data.keys():
            count = len(self.data[group])
            self.group_listbox.insert(tk.END, f"{group} ({count})")
    
    def refresh_recipe_list(self):
        self.recipe_listbox.delete(0, tk.END)
        if not self.current_group:
            return
        
        recipes = self.data.get(self.current_group, {})
        search_term = self.search_var.get().lower().strip()
        time_filter = self.time_filter_var.get()
        difficulty_filter = self.difficulty_filter_var.get()
        show_only_favorites = self.favorite_filter_var.get()
        tag_filter = self.tags_filter_var.get()
        
        for recipe_name, recipe_data in recipes.items():
            if search_term and search_term not in recipe_name.lower():
                continue
            if show_only_favorites and not recipe_data.get("favorite", False):
                continue
            
            # Фильтр по тегам
            if tag_filter != "Все теги" and tag_filter not in recipe_data.get("tags", []):
                continue
            
            time_min = recipe_data.get("time", 0)
            if time_filter == "≤ 15 мин" and time_min > 15:
                continue
            elif time_filter == "15-30 мин" and (time_min < 15 or time_min > 30):
                continue
            elif time_filter == "30-60 мин" and (time_min < 30 or time_min > 60):
                continue
            elif time_filter == "≥ 60 мин" and time_min < 60:
                continue
            
            difficulty = recipe_data.get("difficulty", "")
            if difficulty_filter != "Все" and difficulty != difficulty_filter:
                continue
            
            display_name = recipe_name
            if recipe_data.get("favorite", False):
                display_name = "⭐ " + display_name
            
            tags = recipe_data.get("tags", [])
            if tags:
                display_name += f" [{', '.join(tags[:2])}]"
                if len(tags) > 2:
                    display_name += "..."
            
            self.recipe_listbox.insert(tk.END, display_name)
    
    def reset_filters(self):
        self.search_var.set("")
        self.time_filter_var.set("Все")
        self.difficulty_filter_var.set("Все")
        self.favorite_filter_var.set(False)
        self.tags_filter_var.set("Все теги")
        self.refresh_recipe_list()
        self.update_status("Фильтры сброшены")
    
    def on_group_select(self, event):
        selection = self.group_listbox.curselection()
        if selection:
            group_text = self.group_listbox.get(selection[0])
            self.current_group = group_text.split(" (")[0]
            self.current_recipe = None
            self.reset_filters()
            
            self.name_label.config(text="")
            self.group_label.config(text="")
            self.time_entry.delete(0, tk.END)
            self.difficulty_combo.set("")
            self.servings_spin.delete(0, tk.END)
            self.servings_spin.insert(0, "2")
            self.tags_entry.delete(0, tk.END)
            self.ingredients_text.delete(1.0, tk.END)
            self.steps_text.delete(1.0, tk.END)
            self.display_image(None)
            self.favorite_btn.config(text="☆")
            self.update_status(f"Выбрана группа: {self.current_group}")
    
    def on_recipe_select(self, event):
        selection = self.recipe_listbox.curselection()
        if selection and self.current_group:
            display_name = self.recipe_listbox.get(selection[0])
            recipe_name = display_name
            if recipe_name.startswith("⭐ "):
                recipe_name = recipe_name[2:]
            if " [" in recipe_name:
                recipe_name = recipe_name.split(" [")[0]
            
            self.current_recipe = recipe_name
            recipe = self.data[self.current_group].get(recipe_name, {})
            
            self.name_label.config(text=recipe_name)
            self.group_label.config(text=self.current_group)
            
            self.time_entry.delete(0, tk.END)
            self.time_entry.insert(0, str(recipe.get("time", 0)))
            
            self.difficulty_combo.set(recipe.get("difficulty", ""))
            
            self.servings_spin.delete(0, tk.END)
            self.servings_spin.insert(0, str(recipe.get("servings", 2)))
            
            self.tags_entry.delete(0, tk.END)
            self.tags_entry.insert(0, ", ".join(recipe.get("tags", [])))
            
            self.ingredients_text.delete(1.0, tk.END)
            self.ingredients_text.insert(1.0, recipe.get("ingredients", ""))
            
            self.steps_text.delete(1.0, tk.END)
            self.steps_text.insert(1.0, recipe.get("steps", ""))
            
            self.update_favorite_button()
            
            # Подсветка поиска
            search_term = self.search_var.get()
            if search_term:
                self.highlight_search_term(self.ingredients_text, search_term)
                self.highlight_search_term(self.steps_text, search_term)
            
            image_path = recipe.get("image_path")
            self.display_image(image_path)
            self.update_status(f"Выбран рецепт: {recipe_name}")
    
    def toggle_favorite(self):
        if self.current_group and self.current_recipe:
            favorite = self.data[self.current_group][self.current_recipe].get("favorite", False)
            self.data[self.current_group][self.current_recipe]["favorite"] = not favorite
            self.save_data()
            self.refresh_recipe_list()
            self.update_favorite_button()
            self.update_status("Избранное обновлено")
    
    def update_favorite_button(self):
        if self.current_group and self.current_recipe:
            favorite = self.data[self.current_group][self.current_recipe].get("favorite", False)
            self.favorite_btn.config(text="★" if favorite else "☆")
    
    def add_photo(self):
        if not self.current_group or not self.current_recipe:
            messagebox.showwarning("Предупреждение", "Выберите рецепт")
            return
        
        file_path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif")])
        if file_path:
            try:
                ext = Path(file_path).suffix
                new_filename = f"{self.current_group}_{self.current_recipe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                new_filename = "".join(c for c in new_filename if c.isalnum() or c in '._-')
                dest_path = IMAGES_FOLDER / new_filename
                shutil.copy2(file_path, dest_path)
                
                self.data[self.current_group][self.current_recipe]["image_path"] = str(dest_path)
                self.save_data()
                self.display_image(dest_path)
                self.update_status("Фото добавлено")
                messagebox.showinfo("Успех", "Фото добавлено!")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
    
    def remove_photo(self):
        if self.current_group and self.current_recipe:
            if "image_path" in self.data[self.current_group][self.current_recipe]:
                old_path = self.data[self.current_group][self.current_recipe]["image_path"]
                if Path(old_path).exists():
                    Path(old_path).unlink()
                del self.data[self.current_group][self.current_recipe]["image_path"]
                self.save_data()
                self.display_image(None)
                self.update_status("Фото удалено")
                messagebox.showinfo("Успех", "Фото удалено!")
    
    def display_image(self, image_path):
        if image_path and Path(image_path).exists():
            try:
                img = Image.open(image_path)
                img.thumbnail((180, 180))
                self.image_preview = ImageTk.PhotoImage(img)
                self.photo_label.config(image=self.image_preview, text="")
            except:
                self.photo_label.config(image="", text="Ошибка")
        else:
            self.photo_label.config(image="", text="Нет фото")
            self.image_preview = None
    
    def add_recipe_dialog(self):
        if not self.current_group and self.data:
            self.current_group = list(self.data.keys())[0]
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить рецепт")
        dialog.geometry("600x750")
        
        ttk.Label(dialog, text="Группа:").pack(pady=(10,0), anchor=tk.W, padx=20)
        group_var = tk.StringVar(value=self.current_group if self.current_group else "")
        group_combo = ttk.Combobox(dialog, textvariable=group_var, values=sorted(self.data.keys()), width=50, state="readonly")
        group_combo.pack(pady=5, padx=20, fill=tk.X)
        add_tooltip(group_combo, "Выберите группу для рецепта")
        
        ttk.Label(dialog, text="Название:").pack(pady=(10,0), anchor=tk.W, padx=20)
        name_entry = ttk.Entry(dialog, width=50)
        name_entry.pack(pady=5, padx=20, fill=tk.X)
        add_tooltip(name_entry, "Введите название блюда")
        
        info_frame = ttk.Frame(dialog)
        info_frame.pack(pady=5, padx=20, fill=tk.X)
        ttk.Label(info_frame, text="Время (мин):").pack(side=tk.LEFT, padx=(0,5))
        time_spin = ttk.Spinbox(info_frame, from_=1, to=300, width=10)
        time_spin.pack(side=tk.LEFT, padx=(0,20))
        add_tooltip(time_spin, "Время приготовления в минутах")
        
        ttk.Label(info_frame, text="Сложность:").pack(side=tk.LEFT, padx=(0,5))
        difficulty_combo = ttk.Combobox(info_frame, values=["Легко", "Средне", "Сложно"], width=10, state="readonly")
        difficulty_combo.set("Легко")
        difficulty_combo.pack(side=tk.LEFT)
        add_tooltip(difficulty_combo, "Уровень сложности приготовления")
        
        servings_frame = ttk.Frame(dialog)
        servings_frame.pack(pady=5, padx=20, fill=tk.X)
        ttk.Label(servings_frame, text="Порции:").pack(side=tk.LEFT, padx=(0,5))
        servings_spin = ttk.Spinbox(servings_frame, from_=1, to=20, width=10)
        servings_spin.set(2)
        servings_spin.pack(side=tk.LEFT)
        add_tooltip(servings_spin, "Количество порций")
        
        favorite_var = tk.BooleanVar()
        fav_check = ttk.Checkbutton(dialog, text="⭐ В избранное", variable=favorite_var)
        fav_check.pack(anchor=tk.W, padx=20, pady=5)
        add_tooltip(fav_check, "Добавить рецепт в избранное")
        
        ttk.Label(dialog, text="Теги (через запятую):").pack(pady=(10,0), anchor=tk.W, padx=20)
        tags_entry = ttk.Entry(dialog, width=50)
        tags_entry.pack(pady=5, padx=20, fill=tk.X)
        add_tooltip(tags_entry, "Теги рецепта через запятую (например: завтрак, быстро, полезно)")
        
        # Предпросмотр фото
        preview_label = ttk.Label(dialog, text="Предпросмотр фото:", font=("Arial", 10, "bold"))
        preview_label.pack(anchor=tk.W, padx=20, pady=(10,0))
        
        self.preview_image_label = ttk.Label(dialog, text="Нет фото", relief=tk.SUNKEN)
        self.preview_image_label.pack(pady=5, padx=20)
        add_tooltip(self.preview_image_label, "Предпросмотр выбранного фото")
        
        def add_photo_preview():
            file_path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif")])
            if file_path:
                try:
                    img = Image.open(file_path)
                    img.thumbnail((150, 150))
                    photo = ImageTk.PhotoImage(img)
                    self.preview_image_label.config(image=photo, text="")
                    self.preview_image_label.image = photo
                    self.temp_image_path = file_path
                except:
                    pass
        
        preview_btn = ttk.Button(dialog, text="📸 Выбрать фото", command=add_photo_preview)
        preview_btn.pack(pady=5)
        add_tooltip(preview_btn, "Выбрать фото для рецепта")
        
        ttk.Label(dialog, text="Ингредиенты:").pack(pady=(10,0), anchor=tk.W, padx=20)
        ingredients_text = tk.Text(dialog, height=8, wrap=tk.WORD)
        ingredients_text.pack(pady=5, padx=20, fill=tk.BOTH, expand=True)
        add_tooltip(ingredients_text, "Список ингредиентов (каждый с новой строки)")
        
        ttk.Label(dialog, text="Приготовление:").pack(pady=(10,0), anchor=tk.W, padx=20)
        steps_text = tk.Text(dialog, height=8, wrap=tk.WORD)
        steps_text.pack(pady=5, padx=20, fill=tk.BOTH, expand=True)
        add_tooltip(steps_text, "Пошаговый рецепт приготовления (каждый шаг с новой строки)")
        
        def save():
            group = group_var.get()
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Ошибка", "Введите название")
                return
            if group not in self.data:
                messagebox.showerror("Ошибка", "Группа не существует")
                return
            
            tags = [t.strip() for t in tags_entry.get().split(",") if t.strip()]
            
            recipe_data = {
                "ingredients": ingredients_text.get(1.0, tk.END).strip(),
                "steps": steps_text.get(1.0, tk.END).strip(),
                "time": int(time_spin.get()) if time_spin.get().isdigit() else 0,
                "difficulty": difficulty_combo.get(),
                "tags": tags,
                "favorite": favorite_var.get(),
                "servings": int(servings_spin.get()) if servings_spin.get().isdigit() else 2
            }
            
            # Сохраняем фото если есть
            if hasattr(self, 'temp_image_path') and self.temp_image_path:
                try:
                    ext = Path(self.temp_image_path).suffix
                    new_filename = f"{group}_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                    new_filename = "".join(c for c in new_filename if c.isalnum() or c in '._-')
                    dest_path = IMAGES_FOLDER / new_filename
                    shutil.copy2(self.temp_image_path, dest_path)
                    recipe_data["image_path"] = str(dest_path)
                except:
                    pass
            
            self.data[group][name] = recipe_data
            self.save_data()
            self.refresh_group_list()
            self.update_tags_list()
            if group == self.current_group:
                self.refresh_recipe_list()
            dialog.destroy()
            self.update_status(f"Рецепт '{name}' добавлен")
            messagebox.showinfo("Успех", f"Рецепт '{name}' добавлен!")
        
        save_btn = ttk.Button(dialog, text="Сохранить", command=save)
        save_btn.pack(pady=10)
        add_tooltip(save_btn, "Сохранить новый рецепт")
        name_entry.focus()
    
    # Методы перемещения
    def move_group_up(self):
        if not self.current_group:
            return
        groups = list(self.data.keys())
        idx = groups.index(self.current_group)
        if idx > 0:
            groups[idx], groups[idx-1] = groups[idx-1], groups[idx]
            new_data = OrderedDict()
            for g in groups:
                new_data[g] = self.data[g]
            self.data = new_data
            self.save_data()
            self.refresh_group_list()
            self.group_listbox.selection_set(idx-1)
            self.current_group = groups[idx-1]
            self.update_status(f"Группа перемещена вверх")
    
    def move_group_down(self):
        if not self.current_group:
            return
        groups = list(self.data.keys())
        idx = groups.index(self.current_group)
        if idx < len(groups)-1:
            groups[idx], groups[idx+1] = groups[idx+1], groups[idx]
            new_data = OrderedDict()
            for g in groups:
                new_data[g] = self.data[g]
            self.data = new_data
            self.save_data()
            self.refresh_group_list()
            self.group_listbox.selection_set(idx+1)
            self.current_group = groups[idx+1]
            self.update_status(f"Группа перемещена вниз")
    
    def move_recipe_up(self):
        if not self.current_recipe or not self.current_group:
            return
        recipes = list(self.data[self.current_group].keys())
        idx = recipes.index(self.current_recipe)
        if idx > 0:
            recipes[idx], recipes[idx-1] = recipes[idx-1], recipes[idx]
            new_recipes = OrderedDict()
            for r in recipes:
                new_recipes[r] = self.data[self.current_group][r]
            self.data[self.current_group] = new_recipes
            self.save_data()
            self.refresh_recipe_list()
            self.recipe_listbox.selection_set(idx-1)
            self.current_recipe = recipes[idx-1]
            self.update_status(f"Рецепт перемещен вверх")
    
    def move_recipe_down(self):
        if not self.current_recipe or not self.current_group:
            return
        recipes = list(self.data[self.current_group].keys())
        idx = recipes.index(self.current_recipe)
        if idx < len(recipes)-1:
            recipes[idx], recipes[idx+1] = recipes[idx+1], recipes[idx]
            new_recipes = OrderedDict()
            for r in recipes:
                new_recipes[r] = self.data[self.current_group][r]
            self.data[self.current_group] = new_recipes
            self.save_data()
            self.refresh_recipe_list()
            self.recipe_listbox.selection_set(idx+1)
            self.current_recipe = recipes[idx+1]
            self.update_status(f"Рецепт перемещен вниз")
    
    def add_group_dialog(self):
        name = simpledialog.askstring("Новая группа", "Название группы:")
        if name and name.strip():
            name = name.strip()
            if name in self.data:
                messagebox.showerror("Ошибка", "Группа уже существует")
                return
            self.data[name] = OrderedDict()
            self.save_data()
            self.refresh_group_list()
            self.update_status(f"Группа '{name}' создана")
    
    def rename_group(self):
        if not self.current_group:
            messagebox.showwarning("Предупреждение", "Сначала выберите группу")
            return
        new_name = simpledialog.askstring("Переименование", "Новое название:", initialvalue=self.current_group)
        if new_name and new_name.strip() and new_name != self.current_group:
            new_name = new_name.strip()
            if new_name in self.data:
                messagebox.showerror("Ошибка", "Группа уже существует")
                return
            new_data = OrderedDict()
            for g in self.data:
                if g == self.current_group:
                    new_data[new_name] = self.data[g]
                else:
                    new_data[g] = self.data[g]
            self.data = new_data
            self.current_group = new_name
            self.save_data()
            self.refresh_group_list()
            self.update_status(f"Группа переименована в '{new_name}'")
    
    def delete_group(self):
        if not self.current_group:
            messagebox.showwarning("Предупреждение", "Сначала выберите группу")
            return
        if messagebox.askyesno("Удаление", f"Удалить группу '{self.current_group}' и все рецепты в ней?"):
            del self.data[self.current_group]
            self.current_group = None
            self.current_recipe = None
            self.save_data()
            self.refresh_group_list()
            self.recipe_listbox.delete(0, tk.END)
            self.update_status("Группа удалена")
    
    def delete_recipe(self):
        if not self.current_recipe:
            messagebox.showwarning("Предупреждение", "Сначала выберите рецепт")
            return
        if messagebox.askyesno("Удаление", f"Удалить рецепт '{self.current_recipe}'?"):
            if "image_path" in self.data[self.current_group][self.current_recipe]:
                path = self.data[self.current_group][self.current_recipe]["image_path"]
                if Path(path).exists():
                    Path(path).unlink()
            del self.data[self.current_group][self.current_recipe]
            self.current_recipe = None
            self.save_data()
            self.refresh_recipe_list()
            self.refresh_group_list()
            self.update_tags_list()
            self.ingredients_text.delete(1.0, tk.END)
            self.steps_text.delete(1.0, tk.END)
            self.name_label.config(text="")
            self.display_image(None)
            self.update_status("Рецепт удален")
    
    def copy_recipe_to_group(self):
        if not self.current_recipe:
            messagebox.showwarning("Предупреждение", "Сначала выберите рецепт")
            return
        groups = [g for g in self.data if g != self.current_group]
        if not groups:
            messagebox.showwarning("Нет групп", "Нет других групп")
            return
        target = simpledialog.askstring("Копирование", f"В какую группу?\n{', '.join(groups)}")
        if target and target in self.data:
            self.data[target][self.current_recipe] = self.data[self.current_group][self.current_recipe].copy()
            self.save_data()
            self.refresh_group_list()
            self.update_status(f"Рецепт скопирован в группу '{target}'")
            messagebox.showinfo("Успех", "Рецепт скопирован!")
    
    def import_json(self):
        file = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if file:
            with open(file, 'r', encoding='utf-8') as f:
                imported = json.load(f)
            if messagebox.askyesno("Импорт", "Объединить с текущими?"):
                for group, recipes in imported.items():
                    if group not in self.data:
                        self.data[group] = OrderedDict()
                    self.data[group].update(recipes)
            else:
                self.data = OrderedDict(imported)
            self.save_data()
            self.refresh_group_list()
            self.update_tags_list()
            self.update_status("Импорт завершен")
    
    def export_json(self):
        file = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if file:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(dict(self.data), f, ensure_ascii=False, indent=4)
            self.update_status(f"Экспорт в JSON: {file}")
            messagebox.showinfo("Успех", "Экспортировано!")
    
    def export_txt(self):
        if not self.current_recipe:
            messagebox.showwarning("Предупреждение", "Выберите рецепт")
            return
        file = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if file:
            recipe = self.data[self.current_group][self.current_recipe]
            with open(file, 'w', encoding='utf-8') as f:
                f.write(f"{self.current_recipe}\n{'='*40}\n")
                f.write(f"Группа: {self.current_group}\n")
                f.write(f"Время: {recipe.get('time', 0)} мин\n")
                f.write(f"Сложность: {recipe.get('difficulty', '')}\n")
                f.write(f"Теги: {', '.join(recipe.get('tags', []))}\n\n")
                f.write("ИНГРЕДИЕНТЫ:\n")
                f.write(recipe.get('ingredients', '') + "\n\n")
                f.write("ПРИГОТОВЛЕНИЕ:\n")
                f.write(recipe.get('steps', '') + "\n")
            self.update_status(f"Экспорт в TXT: {file}")
            messagebox.showinfo("Успех", "Экспортировано!")
    
    def create_backup(self):
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_path = BACKUP_FOLDER / backup_name
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(dict(self.data), f, ensure_ascii=False, indent=4)
        self.update_status(f"Бэкап создан: {backup_path}")
        messagebox.showinfo("Успех", f"Бэкап: {backup_path}")
    
    def show_group_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="➕ Добавить группу", command=self.add_group_dialog)
        menu.add_command(label="✏️ Переименовать", command=self.rename_group)
        menu.add_command(label="⬆️ Вверх", command=self.move_group_up)
        menu.add_command(label="⬇️ Вниз", command=self.move_group_down)
        menu.add_command(label="❌ Удалить", command=self.delete_group)
        menu.post(event.x_root, event.y_root)
    
    def show_recipe_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="📝 Добавить рецепт", command=self.add_recipe_dialog)
        menu.add_command(label="✏️ Редактировать", command=self.edit_recipe_dialog)
        menu.add_command(label="⬆️ Вверх", command=self.move_recipe_up)
        menu.add_command(label="⬇️ Вниз", command=self.move_recipe_down)
        menu.add_command(label="📋 Копировать", command=self.copy_recipe_to_group)
        menu.add_command(label="🍳 Режим готовки", command=self.cooking_mode)
        menu.add_command(label="❌ Удалить", command=self.delete_recipe)
        menu.post(event.x_root, event.y_root)
    
    def on_closing(self):
        if messagebox.askokcancel("Выход", "Сохранить изменения?"):
            self.save_data()
            self.save_meal_plan()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = RecipeApp(root)
    root.mainloop()