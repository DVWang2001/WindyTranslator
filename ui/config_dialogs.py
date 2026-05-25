# ui/config_dialogs.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import logging

# 导入 API 客户端模块用于连接测试
from core.api_clients import gemini, deepseek
# 导入默认配置以获取默认 Prompt 值
from core.config import DEFAULT_WORLD_DICT_CONFIG

log = logging.getLogger(__name__)

PROVIDER_GEMINI = 'gemini'
PROVIDER_OPENAI = 'openai'
PROVIDER_NVIDIA_NIM = 'nvidia_nim'

NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_NIM_MODELS = [
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-405b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "google/gemma-2-27b-it",
    "mistralai/mistral-large-2-instruct",
    "deepseek-ai/deepseek-r1",
]

# --- 世界观字典配置窗口 ---

class WorldDictConfigWindow(tk.Toplevel):
    """世界观字典配置对话框。"""

    def __init__(self, parent, app_controller, world_dict_config):
        """初始化配置窗口并绑定 UI 控件。"""
        super().__init__(parent)
        self.app = app_controller
        self.config = world_dict_config  # 直接引用配置字典

        self.initializing = True
        self.connection_tested_ok = False

        self.provider_display_map = {
            PROVIDER_GEMINI: "Google Gemini 原生",
            PROVIDER_OPENAI: "OpenAI 兼容端点",
            PROVIDER_NVIDIA_NIM: "NVIDIA NIM",
        }
        self.provider_value_map = {label: value for value, label in self.provider_display_map.items()}

        provider_value = (self.config.get("provider") or PROVIDER_GEMINI).lower()
        if provider_value not in self.provider_display_map:
            provider_value = PROVIDER_GEMINI

        self.provider_var = tk.StringVar(value=provider_value)
        self.provider_display_var = tk.StringVar(value=self.provider_display_map[provider_value])
        self.api_key_var = tk.StringVar(value=self.config.get("api_key", ""))
        self.api_url_var = tk.StringVar(value=self.config.get("api_url", ""))
        self.model_var = tk.StringVar(value=self.config.get("model", DEFAULT_WORLD_DICT_CONFIG["model"]))
        self.openai_temp_var = tk.StringVar(value=str(self.config.get("openai_temperature", DEFAULT_WORLD_DICT_CONFIG["openai_temperature"])))
        max_tokens_cfg = self.config.get("openai_max_tokens", DEFAULT_WORLD_DICT_CONFIG["openai_max_tokens"])
        self.openai_max_tokens_var = tk.StringVar(value="" if max_tokens_cfg in (None, "") else str(max_tokens_cfg))
        self.enable_base_dict_var = tk.BooleanVar(value=self.config.get("enable_base_dictionary", True))
        self.show_key_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="请输入配置并测试连接")

        self.title("世界观字典配置")
        self.geometry("820x560")
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)

        row_idx = 0

        ttk.Label(frame, text="模型供应商:").grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        self.provider_combo = ttk.Combobox(
            frame,
            textvariable=self.provider_display_var,
            values=list(self.provider_display_map.values()),
            state='readonly',
            width=40,
        )
        self.provider_combo.grid(row=row_idx, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_combo_selected)
        row_idx += 1

        self.api_key_label = ttk.Label(frame, text="API Key:")
        self.api_key_label.grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        key_frame = ttk.Frame(frame)
        key_frame.grid(row=row_idx, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        key_frame.columnconfigure(0, weight=1)
        self.api_key_entry = ttk.Entry(key_frame, textvariable=self.api_key_var, width=50, show="*")
        self.api_key_entry.grid(row=0, column=0, sticky="ew")
        self.key_toggle_button = ttk.Checkbutton(key_frame, text="显示", variable=self.show_key_var, command=self._toggle_key_visibility)
        self.key_toggle_button.grid(row=0, column=1, padx=(5, 0))
        row_idx += 1

        self.api_url_row = row_idx
        self.api_url_label = ttk.Label(frame, text="API 基础地址:")
        self.api_url_label.grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        self.api_url_entry = ttk.Entry(frame, textvariable=self.api_url_var, width=50)
        self.api_url_entry.grid(row=row_idx, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        row_idx += 1

        ttk.Label(frame, text="模型名称:").grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        model_values = [
            "gemini-2.5-pro-preview-05-06",
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash-latest",
            "gemini-pro",
        ]
        self.model_combobox = ttk.Combobox(frame, textvariable=self.model_var, values=model_values, width=48)
        self.model_combobox.grid(row=row_idx, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        row_idx += 1

        self.openai_params_row = row_idx
        self.openai_params_frame = ttk.Frame(frame)
        self.openai_params_frame.grid(row=row_idx, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        self.openai_params_frame.columnconfigure(1, weight=1)
        self.openai_params_frame.columnconfigure(3, weight=1)
        ttk.Label(self.openai_params_frame, text="温度 (0-2):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.openai_temp_entry = ttk.Entry(self.openai_params_frame, textvariable=self.openai_temp_var, width=10)
        self.openai_temp_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(self.openai_params_frame, text="最大 tokens:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.openai_max_tokens_entry = ttk.Entry(self.openai_params_frame, textvariable=self.openai_max_tokens_var, width=12)
        self.openai_max_tokens_entry.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(self.openai_params_frame, text="(留空使用服务端默认)").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        row_idx += 1

        prompt_area_frame = ttk.Frame(frame)
        prompt_area_frame.grid(row=row_idx, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        prompt_area_frame.columnconfigure(0, weight=1)
        prompt_area_frame.columnconfigure(1, weight=1)
        prompt_area_frame.rowconfigure(0, weight=1)
        frame.rowconfigure(row_idx, weight=1)
        row_idx += 1

        char_prompt_frame = ttk.LabelFrame(prompt_area_frame, text="人物提取 Prompt", padding="5")
        char_prompt_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
        char_prompt_frame.rowconfigure(0, weight=1)
        char_prompt_frame.columnconfigure(0, weight=1)
        self.char_prompt_text = scrolledtext.ScrolledText(char_prompt_frame, wrap=tk.WORD, height=15)
        self.char_prompt_text.grid(row=0, column=0, sticky="nsew")
        self.char_prompt_text.insert(tk.END, self.config.get("character_prompt_template", DEFAULT_WORLD_DICT_CONFIG["character_prompt_template"]))
        self.char_prompt_text.edit_modified(False)

        entity_prompt_frame = ttk.LabelFrame(prompt_area_frame, text="事物提取 Prompt", padding="5")
        entity_prompt_frame.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")
        entity_prompt_frame.rowconfigure(0, weight=1)
        entity_prompt_frame.columnconfigure(0, weight=1)
        self.entity_prompt_text = scrolledtext.ScrolledText(entity_prompt_frame, wrap=tk.WORD, height=15)
        self.entity_prompt_text.grid(row=0, column=0, sticky="nsew")
        self.entity_prompt_text.insert(tk.END, self.config.get("entity_prompt_template", DEFAULT_WORLD_DICT_CONFIG["entity_prompt_template"]))
        self.entity_prompt_text.edit_modified(False)

        self.status_label = ttk.Label(frame, textvariable=self.status_var, foreground="orange")
        self.status_label.grid(row=row_idx, column=0, columnspan=3, padx=5, pady=(10, 0), sticky="ew")
        row_idx += 1

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=row_idx, column=0, columnspan=3, pady=10, sticky="e")

        self.enable_base_dict_checkbutton = ttk.Checkbutton(
            button_frame,
            text="启用基础字典",
            variable=self.enable_base_dict_var,
            command=self._on_config_change,
        )
        self.enable_base_dict_checkbutton.pack(side=tk.LEFT, padx=5)

        self.edit_base_dict_button = ttk.Button(button_frame, text="编辑基础字典", command=self._open_base_dict_editor_modal)
        self.edit_base_dict_button.pack(side=tk.LEFT, padx=5)

        self.test_button = ttk.Button(button_frame, text="测试连接", command=self._test_connection)
        self.test_button.pack(side=tk.LEFT, padx=5)

        self.save_button = ttk.Button(button_frame, text="保存", command=self._save_config)
        self.save_button.pack(side=tk.LEFT, padx=5)

        cancel_button = ttk.Button(button_frame, text="取消", command=self.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        self.provider_var.trace_add("write", self._on_provider_var_changed)
        self.api_key_var.trace_add("write", self._on_config_change)
        self.api_url_var.trace_add("write", self._on_config_change)
        self.model_var.trace_add("write", self._on_config_change)
        self.openai_temp_var.trace_add("write", self._on_config_change)
        self.openai_max_tokens_var.trace_add("write", self._on_config_change)
        self.char_prompt_text.bind("<<Modified>>", self._on_prompt_modified)
        self.entity_prompt_text.bind("<<Modified>>", self._on_prompt_modified)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.controls_to_manage = []  # 占位，稍后填充

        self._sync_provider_display()
        self._update_provider_ui(initial=True)

        minimal_ready = bool(self.api_key_var.get().strip())
        if self.provider_var.get() == PROVIDER_OPENAI:
            minimal_ready = minimal_ready and bool(self.api_url_var.get().strip())
        self.connection_tested_ok = minimal_ready
        if self.connection_tested_ok:
            self._set_status("配置已加载", "green")
        else:
            self._set_status("请输入必要信息并测试连接", "red")

        self.controls_to_manage = [
            self.provider_combo,
            self.api_key_entry,
            self.key_toggle_button,
            self.api_url_entry,
            self.model_combobox,
            self.openai_temp_entry,
            self.openai_max_tokens_entry,
            self.char_prompt_text,
            self.entity_prompt_text,
            self.enable_base_dict_checkbutton,
            self.edit_base_dict_button,
            self.test_button,
            self.save_button,
        ]

        self.initializing = False
        self._update_connection_signature()
        if self.connection_tested_ok:
            self.save_button.config(state=tk.NORMAL)
        else:
            self.save_button.config(state=tk.DISABLED)

    def _sync_provider_display(self):
        provider = self.provider_var.get()
        display_value = self.provider_display_map.get(provider, self.provider_display_map[PROVIDER_GEMINI])
        if self.provider_display_var.get() != display_value:
            self.provider_display_var.set(display_value)

    def _on_provider_combo_selected(self, event=None):
        display = self.provider_display_var.get()
        provider = self.provider_value_map.get(display, PROVIDER_GEMINI)
        if provider != self.provider_var.get():
            self.provider_var.set(provider)

    def _on_provider_var_changed(self, *args):
        self._sync_provider_display()
        self._update_provider_ui()
        self._on_config_change()

    def _update_provider_ui(self, initial=False):
        provider = self.provider_var.get()
        if provider == PROVIDER_GEMINI:
            self.title("世界观字典配置 (Gemini)")
            self.api_key_label.config(text="Gemini API Key:")
            self.api_url_label.grid_remove()
            self.api_url_entry.grid_remove()
            self.openai_params_frame.grid_remove()
            self.model_combobox.config(values=[
                "gemini-2.5-pro-preview-05-06",
                "gemini-1.5-pro-latest",
                "gemini-1.5-flash-latest",
                "gemini-pro",
            ])
        elif provider == PROVIDER_NVIDIA_NIM:
            self.title("世界观字典配置 (NVIDIA NIM)")
            self.api_key_label.config(text="NVIDIA API Key:")
            self.api_url_label.grid(row=self.api_url_row, column=0, padx=5, pady=5, sticky="w")
            self.api_url_entry.grid(row=self.api_url_row, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
            self.openai_params_frame.grid(row=self.openai_params_row, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
            self.model_combobox.config(values=NVIDIA_NIM_MODELS)
            if not initial and not self.api_url_var.get().strip():
                self.api_url_var.set(NVIDIA_NIM_BASE_URL)
        else:
            self.title("世界观字典配置 (OpenAI 兼容)")
            self.api_key_label.config(text="OpenAI API Key:")
            self.api_url_label.grid(row=self.api_url_row, column=0, padx=5, pady=5, sticky="w")
            self.api_url_entry.grid(row=self.api_url_row, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
            self.openai_params_frame.grid(row=self.openai_params_row, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
            self.model_combobox.config(values=[
                "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo",
                "deepseek-chat", "moonshot-v1-32k",
            ])
        if not initial:
            self._set_status("供应商已切换，请重新测试连接", "orange")

    def _open_base_dict_editor_modal(self):
        self._set_controls_enabled(False)
        editor_window = self.app.open_base_dict_editor(parent_for_editor=self)
        if editor_window:
            self.wait_window(editor_window)
        self._set_controls_enabled(True)
        self.focus_set()
        self.grab_set()

    def _set_controls_enabled(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        for control in self.controls_to_manage:
            if not control or not control.winfo_exists():
                continue
            try:
                if isinstance(control, ttk.Combobox):
                    control.config(state='readonly' if enabled else tk.DISABLED)
                elif isinstance(control, (tk.Entry, ttk.Entry, scrolledtext.ScrolledText, tk.Text, ttk.Spinbox)):
                    control.config(state=state)
                elif isinstance(control, (ttk.Button, ttk.Checkbutton)):
                    control.config(state=state)
            except tk.TclError:
                pass

    def _toggle_key_visibility(self):
        if self.show_key_var.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="*")

    def _on_prompt_modified(self, event=None):
        if not self.initializing and event:
            widget = event.widget
            if widget.edit_modified():
                widget.edit_modified(False)
                self._on_config_change()

    def _current_connection_signature(self):
        provider = self.provider_var.get()
        api_key = self.api_key_var.get().strip()
        model = self.model_var.get().strip()
        api_url = self.api_url_var.get().strip() if provider == PROVIDER_OPENAI else ""
        return (provider, api_key, api_url, model)

    def _update_connection_signature(self):
        self._last_connection_signature = self._current_connection_signature()

    def _on_config_change(self, *args):
        if self.initializing:
            return
        current_signature = self._current_connection_signature()
        if getattr(self, '_last_connection_signature', None) != current_signature:
            self.connection_tested_ok = False
            if self.save_button.winfo_exists():
                self.save_button.config(state=tk.DISABLED)
            self._set_status("关键配置已修改，请重新测试连接", "orange")
            self._last_connection_signature = current_signature

    def _set_status(self, message, color):
        if self.winfo_exists():
            self.status_var.set(message)
            self.status_label.config(foreground=color)

    def _test_connection(self):
        provider = self.provider_var.get()
        api_key = self.api_key_var.get().strip()
        model = self.model_var.get().strip()
        api_url = self.api_url_var.get().strip()
        provider_display = self.provider_display_map.get(provider, provider)

        if not api_key:
            messagebox.showerror("错误", f"请输入 {provider_display} Key", parent=self)
            return
        if provider == PROVIDER_OPENAI and not api_url:
            messagebox.showerror("错误", "请输入 OpenAI 兼容 API 的基础地址", parent=self)
            return
        if not model:
            messagebox.showerror("错误", "请选择或输入模型名称", parent=self)
            return

        self._set_status("正在测试连接...", "blue")
        self.test_button.config(state=tk.DISABLED)
        self.save_button.config(state=tk.DISABLED)

        thread = threading.Thread(
            target=self._test_connection_thread,
            args=(provider, api_url, api_key, model),
            daemon=True,
        )
        thread.start()

    def _test_connection_thread(self, provider, api_url, api_key, model):
        provider_display = self.provider_display_map.get(provider, provider)
        try:
            if provider == PROVIDER_GEMINI:
                client = gemini.GeminiClient(api_key)
            else:
                client = deepseek.DeepSeekClient(base_url=api_url, api_key=api_key)
            success, message = client.test_connection(model)
            self.after(0, lambda: self._test_connection_result(success, message))
        except ConnectionError as exc:
            self.after(0, lambda: self._test_connection_result(False, f"客户端初始化失败: {exc}"))
        except Exception as exc:
            log.exception("世界观字典连接测试线程发生意外错误。")
            self.after(0, lambda: self._test_connection_result(False, f"测试时发生意外错误: {exc}"))

    def _test_connection_result(self, success, message):
        if not self.winfo_exists():
            return
        self.test_button.config(state=tk.NORMAL)
        if success:
            self.connection_tested_ok = True
            self._update_connection_signature()
            self._set_status("连接成功!", "green")
            self.save_button.config(state=tk.NORMAL)
            messagebox.showinfo("成功", message, parent=self)
        else:
            self.connection_tested_ok = False
            self._set_status("连接失败", "red")
            self.save_button.config(state=tk.DISABLED)
            messagebox.showerror("连接失败", message, parent=self)

    def _save_config(self):
        if not self.connection_tested_ok:
            messagebox.showwarning("无法保存", "请先成功测试连接后再保存。", parent=self)
            return

        provider = self.provider_var.get()
        api_key = self.api_key_var.get().strip()
        api_url = self.api_url_var.get().strip()
        model = self.model_var.get().strip()

        temp_text = self.openai_temp_var.get().strip()
        if temp_text:
            try:
                openai_temperature = float(temp_text)
            except ValueError:
                messagebox.showerror("错误", "OpenAI 温度必须是数字。", parent=self)
                return
        else:
            openai_temperature = DEFAULT_WORLD_DICT_CONFIG["openai_temperature"]

        max_tokens_text = self.openai_max_tokens_var.get().strip()
        if max_tokens_text:
            try:
                openai_max_tokens = int(max_tokens_text)
            except ValueError:
                messagebox.showerror("错误", "OpenAI 最大 tokens 必须是整数。", parent=self)
                return
        else:
            openai_max_tokens = None

        self.config["provider"] = provider
        self.config["api_key"] = api_key
        self.config["api_url"] = api_url
        self.config["model"] = model
        self.config["openai_temperature"] = openai_temperature
        self.config["openai_max_tokens"] = openai_max_tokens

        self.config["character_prompt_template"] = self.char_prompt_text.get("1.0", tk.END).strip()
        self.config["entity_prompt_template"] = self.entity_prompt_text.get("1.0", tk.END).strip()
        self.config["enable_base_dictionary"] = self.enable_base_dict_var.get()
        self.config["character_dict_filename"] = self.config.get(
            "character_dict_filename",
            DEFAULT_WORLD_DICT_CONFIG["character_dict_filename"],
        )
        self.config["entity_dict_filename"] = self.config.get(
            "entity_dict_filename",
            DEFAULT_WORLD_DICT_CONFIG["entity_dict_filename"],
        )

        self.app.save_config()
        log.info("世界观字典配置已更新。")
        self.destroy()


# --- DeepSeek (翻译) 配置窗口 ---
class TranslateConfigWindow(tk.Toplevel):
    """翻译 JSON (DeepSeek/OpenAI 兼容) 配置对话框。"""

    def __init__(self, parent, app_controller, translate_config):
        """
        初始化 DeepSeek 配置窗口。

        Args:
            parent (tk.Widget): 父窗口。
            app_controller (RPGTranslatorApp): 应用控制器实例。
            translate_config (dict): 当前的翻译配置字典 (来自 app.config)。
                                     窗口将直接修改这个字典。
        """
        super().__init__(parent)
        self.app = app_controller
        self.config = translate_config # 直接引用配置字典

        # --- 状态标志 ---
        self.initializing = True
        self.connection_tested_ok = False

        # --- 窗口设置 ---
        self.title("翻译JSON文件配置 (OpenAI兼容 API)")
        self.geometry("600x580") # 保持原大小
        self.transient(parent)
        self.grab_set()

        # --- 框架 ---
        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1) # 让输入框等可扩展

        # --- 控件变量 ---
        # 注意：获取默认值时，应从导入的 DEFAULT_TRANSLATE_CONFIG 获取
        from core.config import DEFAULT_TRANSLATE_CONFIG # 导入默认翻译配置
        self.api_url_var = tk.StringVar(value=self.config.get("api_url", DEFAULT_TRANSLATE_CONFIG["api_url"]))
        self.api_key_var = tk.StringVar(value=self.config.get("api_key", ""))
        self.model_var = tk.StringVar(value=self.config.get("model", DEFAULT_TRANSLATE_CONFIG["model"]))
        self.batch_var = tk.IntVar(value=self.config.get("batch_size", DEFAULT_TRANSLATE_CONFIG["batch_size"]))
        self.context_var = tk.IntVar(value=self.config.get("context_lines", DEFAULT_TRANSLATE_CONFIG["context_lines"]))
        self.concur_var = tk.IntVar(value=self.config.get("concurrency", DEFAULT_TRANSLATE_CONFIG["concurrency"]))
        self.source_lang_var = tk.StringVar(value=self.config.get("source_language", DEFAULT_TRANSLATE_CONFIG["source_language"]))
        self.target_lang_var = tk.StringVar(value=self.config.get("target_language", DEFAULT_TRANSLATE_CONFIG["target_language"]))
        self.show_key_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="请先测试连接")

        # --- 创建控件 ---
        row_idx = 0

        # 供应商预设
        self._translate_presets = {
            "（手动填写）": {"url": "", "models": []},
            "NVIDIA NIM": {"url": NVIDIA_NIM_BASE_URL, "models": NVIDIA_NIM_MODELS},
            "DeepSeek": {"url": "https://api.deepseek.com/v1", "models": ["deepseek-chat", "deepseek-coder"]},
            "Moonshot": {"url": "https://api.moonshot.cn/v1", "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]},
            "OpenAI": {"url": "https://api.openai.com/v1", "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]},
        }
        self._preset_var = tk.StringVar(value="（手动填写）")
        ttk.Label(frame, text="供应商预设:").grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        preset_combo = ttk.Combobox(frame, textvariable=self._preset_var,
                                    values=list(self._translate_presets.keys()),
                                    state="readonly", width=30)
        preset_combo.grid(row=row_idx, column=1, padx=5, pady=5, sticky="w")
        preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)
        row_idx += 1

        # API URL
        ttk.Label(frame, text="API URL:").grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        self.api_url_entry = ttk.Entry(frame, textvariable=self.api_url_var, width=60)
        self.api_url_entry.grid(row=row_idx, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        row_idx += 1

        # API Key
        ttk.Label(frame, text="API Key:").grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        key_frame = ttk.Frame(frame)
        key_frame.grid(row=row_idx, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        key_frame.columnconfigure(0, weight=1)
        self.api_key_entry = ttk.Entry(key_frame, textvariable=self.api_key_var, width=50, show="*")
        self.api_key_entry.grid(row=0, column=0, sticky="ew")
        key_toggle_button = ttk.Checkbutton(key_frame, text="显示", variable=self.show_key_var, command=self._toggle_key_visibility)
        key_toggle_button.grid(row=0, column=1, padx=(5, 0))
        row_idx += 1

        # Model Name
        ttk.Label(frame, text="模型名称:").grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        self._translate_model_combo = ttk.Combobox(frame, textvariable=self.model_var, values=[
            "deepseek-chat", "deepseek-coder",
            "gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview", "gpt-4o", "gpt-4o-mini",
            "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k",
        ] + NVIDIA_NIM_MODELS, width=48)
        self._translate_model_combo.grid(row=row_idx, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        row_idx += 1

        # Spinboxes in a subframe for better layout
        spinbox_frame = ttk.Frame(frame)
        spinbox_frame.grid(row=row_idx, column=0, columnspan=4, padx=0, pady=5, sticky="w")

        # Batch Size
        ttk.Label(spinbox_frame, text="批次大小:").pack(side=tk.LEFT, padx=(5, 2))
        self.batch_spinbox = ttk.Spinbox(spinbox_frame, from_=1, to=100, textvariable=self.batch_var, width=5)
        self.batch_spinbox.pack(side=tk.LEFT, padx=(0, 10))

        # Context Lines
        ttk.Label(spinbox_frame, text="上文行数:").pack(side=tk.LEFT, padx=(5, 2))
        self.context_spinbox = ttk.Spinbox(spinbox_frame, from_=0, to=50, textvariable=self.context_var, width=5)
        self.context_spinbox.pack(side=tk.LEFT, padx=(0, 10))

        # Concurrency
        ttk.Label(spinbox_frame, text="并发数:").pack(side=tk.LEFT, padx=(5, 2))
        self.concur_spinbox = ttk.Spinbox(spinbox_frame, from_=1, to=256, textvariable=self.concur_var, width=5) # 增加并发上限示例
        self.concur_spinbox.pack(side=tk.LEFT, padx=(0, 5))
        row_idx += 1

        # Language Selection
        lang_frame = ttk.Frame(frame)
        lang_frame.grid(row=row_idx, column=0, columnspan=4, padx=0, pady=5, sticky="ew")
        lang_frame.columnconfigure(1, weight=1)
        lang_frame.columnconfigure(3, weight=1)

        # Source Language
        ttk.Label(lang_frame, text="源语言:").grid(row=0, column=0, padx=5, sticky="w")
        source_lang_combo = ttk.Combobox(lang_frame, textvariable=self.source_lang_var, values=[
            "日语", "英语", "简体中文", "繁体中文", "韩语", "俄语", "法语", "德语", "西班牙语", "自动检测"
        ], width=15, state="readonly")
        source_lang_combo.grid(row=0, column=1, padx=5, sticky="ew")

        # Target Language
        ttk.Label(lang_frame, text="目标语言:").grid(row=0, column=2, padx=(10, 5), sticky="w")
        target_lang_combo = ttk.Combobox(lang_frame, textvariable=self.target_lang_var, values=[
            "简体中文", "繁体中文", "英语", "日语", "韩语", "俄语", "法语", "德语", "西班牙语"
        ], width=15, state="readonly")
        target_lang_combo.grid(row=0, column=3, padx=5, sticky="ew")
        row_idx += 1

        # Prompt Template
        prompt_frame = ttk.LabelFrame(frame, text="Prompt 模板", padding="5")
        prompt_frame.grid(row=row_idx, column=0, columnspan=4, padx=5, pady=5, sticky="nsew")
        frame.rowconfigure(row_idx, weight=1)
        prompt_frame.columnconfigure(0, weight=1)
        prompt_frame.rowconfigure(0, weight=1)

        self.prompt_text = scrolledtext.ScrolledText(prompt_frame, wrap=tk.WORD, height=8) # 减少默认高度
        self.prompt_text.grid(row=0, column=0, sticky="nsew")
        # 加载时使用配置值，若无则用默认值
        self.prompt_text.insert(tk.END, self.config.get("prompt_template", DEFAULT_TRANSLATE_CONFIG["prompt_template"]))
        self.prompt_text.edit_modified(False)
        row_idx += 1

        # Status Label
        self.status_label = ttk.Label(frame, textvariable=self.status_var, foreground="orange")
        self.status_label.grid(row=row_idx, column=0, columnspan=4, padx=5, pady=(10, 0), sticky="ew")
        row_idx += 1

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=row_idx, column=0, columnspan=4, pady=10, sticky="e")

        self.test_button = ttk.Button(button_frame, text="测试连接", command=self._test_connection)
        self.test_button.pack(side=tk.LEFT, padx=5)
        self.save_button = ttk.Button(button_frame, text="保存", command=self._save_config, state=tk.DISABLED)
        self.save_button.pack(side=tk.LEFT, padx=5)
        cancel_button = ttk.Button(button_frame, text="取消", command=self.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        # --- Bind Events ---
        self.api_url_var.trace_add("write", self._on_config_change)
        self.api_key_var.trace_add("write", self._on_config_change)
        self.model_var.trace_add("write", self._on_config_change)
        # Spinbox 变化也触发检查
        self.batch_spinbox.bind("<FocusOut>", self._on_config_change)
        self.batch_spinbox.bind("<KeyRelease>", self._on_config_change) # 用 KeyRelease 更即时
        self.context_spinbox.bind("<FocusOut>", self._on_config_change)
        self.context_spinbox.bind("<KeyRelease>", self._on_config_change)
        self.concur_spinbox.bind("<FocusOut>", self._on_config_change)
        self.concur_spinbox.bind("<KeyRelease>", self._on_config_change)
        # Combobox 选择变化
        source_lang_combo.bind("<<ComboboxSelected>>", self._on_config_change)
        target_lang_combo.bind("<<ComboboxSelected>>", self._on_config_change)
        # Prompt 文本变化
        self.prompt_text.bind("<<Modified>>", self._on_prompt_modified)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # --- Initialization Complete ---
        self.initializing = False
        if self.api_key_var.get() and self.api_url_var.get():
            self._set_status("配置已加载，请测试连接", "orange")
        else:
            self._set_status("请输入 API URL 和 Key 并测试连接", "red")

    def _toggle_key_visibility(self):
        """Toggle API Key visibility."""
        if self.show_key_var.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="*")

    def _on_preset_selected(self, event=None):
        preset_name = self._preset_var.get()
        preset = self._translate_presets.get(preset_name, {})
        url = preset.get("url", "")
        models = preset.get("models", [])
        if url:
            self.api_url_var.set(url)
        if models:
            self._translate_model_combo.config(values=models)
            if self.model_var.get() not in models:
                self.model_var.set(models[0])

    def _on_prompt_modified(self, event=None):
        """Handle Prompt text modification."""
        # TranslateConfigWindow 只有一个 prompt_text，逻辑不变
        if not self.initializing and self.prompt_text.edit_modified():
            self.prompt_text.edit_modified(False)
            self._on_config_change()

    def _set_status(self, message, color):
        """Update status label."""
        if self.winfo_exists():
             self.status_var.set(message)
             self.status_label.config(foreground=color)

    def _test_connection(self):
        """Start connection test thread."""
        api_url = self.api_url_var.get().strip()
        api_key = self.api_key_var.get().strip()
        model = self.model_var.get().strip()
        if not api_key or not api_url:
            messagebox.showerror("错误", "请输入 API URL 和 API Key", parent=self)
            return
        if not model:
             messagebox.showerror("错误", "请输入模型名称", parent=self)
             return

        self._set_status("正在测试连接...", "blue")
        self.test_button.config(state=tk.DISABLED)
        self.save_button.config(state=tk.DISABLED)

        thread = threading.Thread(target=self._test_connection_thread, args=(api_url, api_key, model), daemon=True)
        thread.start()

    def _test_connection_thread(self, api_url, api_key, model):
        """Run connection test in a thread."""
        try:
            client = deepseek.DeepSeekClient(base_url=api_url, api_key=api_key)
            success, message = client.test_connection(model)
            self.after(0, lambda: self._test_connection_result(success, message))
        except ConnectionError as e:
             self.after(0, lambda: self._test_connection_result(False, f"客户端初始化失败: {e}"))
        except Exception as e:
            log.exception("翻译API连接测试线程发生意外错误。")
            self.after(0, lambda: self._test_connection_result(False, f"测试时发生意外错误: {e}"))

    def _test_connection_result(self, success, message):
        """Handle connection test result."""
        if not self.winfo_exists(): return
        self.test_button.config(state=tk.NORMAL)
        if success:
            self.connection_tested_ok = True
            self._set_status("连接成功!", "green")
            self.save_button.config(state=tk.NORMAL)
            messagebox.showinfo("成功", message, parent=self)
        else:
            self.connection_tested_ok = False
            self._set_status("连接失败", "red")
            self.save_button.config(state=tk.DISABLED)
            messagebox.showerror("连接失败", message, parent=self)

    def _save_config(self):
        """Save configuration and close window."""
        if not self.connection_tested_ok:
            messagebox.showwarning("无法保存", "请先成功测试连接后再保存。", parent=self)
            return

        # 获取 Spinbox 的值，并进行基本的类型检查和范围限制 (可选但推荐)
        try:
            batch_size = int(self.batch_var.get())
            if not (1 <= batch_size <= 100): batch_size = 10 # 恢复默认
        except ValueError: batch_size = 10
        try:
            context_lines = int(self.context_var.get())
            if not (0 <= context_lines <= 50): context_lines = 10
        except ValueError: context_lines = 10
        try:
            concurrency = int(self.concur_var.get())
            if not (1 <= concurrency <= 256): concurrency = 16
        except ValueError: concurrency = 16


        # Update the config dictionary directly
        self.config["api_url"] = self.api_url_var.get().strip()
        self.config["api_key"] = self.api_key_var.get().strip()
        self.config["model"] = self.model_var.get().strip()
        self.config["batch_size"] = batch_size
        self.config["context_lines"] = context_lines
        self.config["concurrency"] = concurrency
        self.config["source_language"] = self.source_lang_var.get()
        self.config["target_language"] = self.target_lang_var.get()
        self.config["prompt_template"] = self.prompt_text.get("1.0", tk.END).strip()
        # 确保 max_retries 也被保存 (如果之前没有，从默认值添加)
        from core.config import DEFAULT_TRANSLATE_CONFIG
        self.config["max_retries"] = self.config.get("max_retries", DEFAULT_TRANSLATE_CONFIG["max_retries"])

        # Notify app to save the entire config
        self.app.save_config()
        log.info("翻译配置已更新。")
        self.destroy()


# --- g4f 配置窗口 ---

class G4FConfigWindow(tk.Toplevel):
    """g4f (GPT4Free) 翻译配置对话框，无需 API Key。"""

    _G4F_PROVIDERS = [
        "（自动选择）",
        "Copilot", "DeepSeek", "Gemini", "GeminiPro",
        "Blackbox", "DDG", "You", "PerplexityLabs",
        "Pizzagpt", "FreeChatgpt",
    ]

    def __init__(self, parent, app_controller, g4f_config):
        super().__init__(parent)
        self.app = app_controller
        self.config = g4f_config

        self.initializing = True

        self.title("g4f (GPT4Free) 翻译配置")
        self.geometry("600x520")
        self.transient(parent)
        self.grab_set()

        from core.config import DEFAULT_G4F_CONFIG
        self._defaults = DEFAULT_G4F_CONFIG

        # --- 变量 ---
        raw_provider = self.config.get("g4f_provider", "") or ""
        self.provider_var = tk.StringVar(
            value=raw_provider if raw_provider else "（自动选择）"
        )
        self.model_var = tk.StringVar(value=self.config.get("model", self._defaults["model"]))
        self.batch_var = tk.IntVar(value=self.config.get("batch_size", self._defaults["batch_size"]))
        self.context_var = tk.IntVar(value=self.config.get("context_lines", self._defaults["context_lines"]))
        self.concur_var = tk.IntVar(value=self.config.get("concurrency", self._defaults["concurrency"]))
        self.source_lang_var = tk.StringVar(value=self.config.get("source_language", self._defaults["source_language"]))
        self.target_lang_var = tk.StringVar(value=self.config.get("target_language", self._defaults["target_language"]))
        self.status_var = tk.StringVar(value="g4f 无需 API Key，可直接保存或先测试连接")

        # --- 布局 ---
        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        row_idx = 0

        # Provider
        ttk.Label(frame, text="Provider:").grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        self.provider_combo = ttk.Combobox(
            frame, textvariable=self.provider_var,
            values=self._G4F_PROVIDERS, width=30,
        )
        self.provider_combo.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(frame, text="（留空 = 自动）", foreground="gray").grid(row=row_idx, column=2, padx=5, sticky="w")
        row_idx += 1

        # Model
        ttk.Label(frame, text="模型名称:").grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
        model_combo = ttk.Combobox(frame, textvariable=self.model_var, values=[
            "gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-3.5-turbo",
            "gemini-pro", "gemini-1.5-flash", "deepseek-chat",
        ], width=30)
        model_combo.grid(row=row_idx, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        row_idx += 1

        # Spinboxes
        spinbox_frame = ttk.Frame(frame)
        spinbox_frame.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=5, sticky="w")
        ttk.Label(spinbox_frame, text="批次大小:").pack(side=tk.LEFT, padx=(5, 2))
        ttk.Spinbox(spinbox_frame, from_=1, to=50, textvariable=self.batch_var, width=5).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(spinbox_frame, text="上文行数:").pack(side=tk.LEFT, padx=(5, 2))
        ttk.Spinbox(spinbox_frame, from_=0, to=50, textvariable=self.context_var, width=5).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(spinbox_frame, text="并发数:").pack(side=tk.LEFT, padx=(5, 2))
        ttk.Spinbox(spinbox_frame, from_=1, to=8, textvariable=self.concur_var, width=5).pack(side=tk.LEFT, padx=(0, 5))
        row_idx += 1

        # Language
        lang_frame = ttk.Frame(frame)
        lang_frame.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=5, sticky="ew")
        lang_frame.columnconfigure(1, weight=1)
        lang_frame.columnconfigure(3, weight=1)
        ttk.Label(lang_frame, text="源语言:").grid(row=0, column=0, padx=5, sticky="w")
        ttk.Combobox(lang_frame, textvariable=self.source_lang_var, values=[
            "日语", "英语", "简体中文", "繁体中文", "韩语",
        ], width=15, state="readonly").grid(row=0, column=1, padx=5, sticky="ew")
        ttk.Label(lang_frame, text="目标语言:").grid(row=0, column=2, padx=(10, 5), sticky="w")
        ttk.Combobox(lang_frame, textvariable=self.target_lang_var, values=[
            "简体中文", "繁体中文", "英语", "日语", "韩语",
        ], width=15, state="readonly").grid(row=0, column=3, padx=5, sticky="ew")
        row_idx += 1

        # Prompt
        prompt_frame = ttk.LabelFrame(frame, text="Prompt 模板", padding="5")
        prompt_frame.grid(row=row_idx, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        frame.rowconfigure(row_idx, weight=1)
        prompt_frame.columnconfigure(0, weight=1)
        prompt_frame.rowconfigure(0, weight=1)
        self.prompt_text = scrolledtext.ScrolledText(prompt_frame, wrap=tk.WORD, height=8)
        self.prompt_text.grid(row=0, column=0, sticky="nsew")
        self.prompt_text.insert(tk.END, self.config.get("prompt_template", self._defaults["prompt_template"]))
        self.prompt_text.edit_modified(False)
        row_idx += 1

        # Status
        self.status_label = ttk.Label(frame, textvariable=self.status_var, foreground="gray")
        self.status_label.grid(row=row_idx, column=0, columnspan=3, padx=5, pady=(5, 0), sticky="ew")
        row_idx += 1

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row_idx, column=0, columnspan=3, pady=10, sticky="e")
        self.test_button = ttk.Button(btn_frame, text="测试连接", command=self._test_connection)
        self.test_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="保存", command=self._save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.initializing = False

    def _set_status(self, message, color="gray"):
        if self.winfo_exists():
            self.status_var.set(message)
            self.status_label.config(foreground=color)

    def _test_connection(self):
        model = self.model_var.get().strip()
        if not model:
            messagebox.showerror("错误", "请输入模型名称", parent=self)
            return
        provider_raw = self.provider_var.get().strip()
        provider = None if provider_raw in ("", "（自动选择）") else provider_raw
        self._set_status("正在测试 g4f 连接（首次可能较慢）...", "blue")
        self.test_button.config(state=tk.DISABLED)
        threading.Thread(
            target=self._test_thread, args=(model, provider), daemon=True
        ).start()

    def _test_thread(self, model, provider):
        try:
            from core.api_clients.g4f_client import G4FClient
            client = G4FClient(provider)
            success, message = client.test_connection(model)
            self.after(0, lambda: self._test_result(success, message))
        except Exception as e:
            self.after(0, lambda: self._test_result(False, str(e)))

    def _test_result(self, success, message):
        if not self.winfo_exists():
            return
        self.test_button.config(state=tk.NORMAL)
        if success:
            self._set_status("连接成功！", "green")
            messagebox.showinfo("成功", message, parent=self)
        else:
            self._set_status(f"连接失败: {message}", "red")
            messagebox.showerror("连接失败", message, parent=self)

    def _save_config(self):
        provider_raw = self.provider_var.get().strip()
        self.config["provider"] = "g4f"
        self.config["g4f_provider"] = "" if provider_raw in ("", "（自动选择）") else provider_raw
        self.config["model"] = self.model_var.get().strip()
        try:
            self.config["batch_size"] = max(1, min(50, int(self.batch_var.get())))
        except ValueError:
            self.config["batch_size"] = self._defaults["batch_size"]
        try:
            self.config["context_lines"] = max(0, min(50, int(self.context_var.get())))
        except ValueError:
            self.config["context_lines"] = self._defaults["context_lines"]
        try:
            self.config["concurrency"] = max(1, min(8, int(self.concur_var.get())))
        except ValueError:
            self.config["concurrency"] = self._defaults["concurrency"]
        self.config["source_language"] = self.source_lang_var.get()
        self.config["target_language"] = self.target_lang_var.get()
        self.config["prompt_template"] = self.prompt_text.get("1.0", tk.END).strip()
        self.app.save_config()
        log.info("g4f 翻译配置已更新。")
        self.destroy()
