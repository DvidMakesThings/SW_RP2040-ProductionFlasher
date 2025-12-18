"""
Log panel for RP2040 Programmer GUI.

Displays real-time log messages and process status.
"""
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Optional

from config.settings import CONFIG
from utils.logger import LogEntry


class LogPanel(ttk.LabelFrame):
    """
    Panel displaying log messages and process progress.
    
    Shows real-time logging with color-coded levels.
    """
    
    def __init__(self, parent: tk.Widget):
        """
        Initialize log panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent, text="Process Log", padding=10)
        
        self._create_widgets()
    
    def _create_widgets(self) -> None:
        """Create panel widgets."""
        # Progress bar
        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill=tk.X, pady=(0, 5))
        
        self._progress_label = ttk.Label(
            progress_frame,
            text="Idle"
        )
        self._progress_label.pack(side=tk.LEFT)
        
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self._progress_var,
            maximum=100,
            length=200
        )
        self._progress_bar.pack(side=tk.RIGHT)
        
        # Log text area
        log_frame = ttk.Frame(self)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self._log_text = tk.Text(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9) if tk.TkVersion >= 8.6 else ("Courier", 9),
            state=tk.DISABLED,
            height=12
        )
        
        scrollbar = ttk.Scrollbar(
            log_frame,
            orient=tk.VERTICAL,
            command=self._log_text.yview
        )
        self._log_text.configure(yscrollcommand=scrollbar.set)
        
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configure text tags for colors
        self._log_text.tag_configure("DEBUG", foreground="gray")
        self._log_text.tag_configure("INFO", foreground="black")
        self._log_text.tag_configure("WARNING", foreground="orange")
        self._log_text.tag_configure("ERROR", foreground="red")
        self._log_text.tag_configure("SUCCESS", foreground="green")
        self._log_text.tag_configure("timestamp", foreground="gray")
        self._log_text.tag_configure("source", foreground="blue")
        
        # Button row
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        self._clear_btn = ttk.Button(
            btn_frame,
            text="Clear Log",
            command=self.clear
        )
        self._clear_btn.pack(side=tk.LEFT)
        
        self._save_btn = ttk.Button(
            btn_frame,
            text="Save Log...",
            command=self._save_log
        )
        self._save_btn.pack(side=tk.LEFT, padx=5)
        
        self._autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            btn_frame,
            text="Auto-scroll",
            variable=self._autoscroll_var
        ).pack(side=tk.RIGHT)
    
    def add_entry(self, entry: LogEntry) -> None:
        """
        Add a log entry to display.
        
        Args:
            entry: LogEntry to display
        """
        self._log_text.config(state=tk.NORMAL)
        
        # Format: [timestamp] [level] [source] message
        ts = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]
        
        self._log_text.insert(tk.END, f"[{ts}] ", "timestamp")
        self._log_text.insert(tk.END, f"[{entry.level}] ", entry.level)
        self._log_text.insert(tk.END, f"[{entry.source}] ", "source")
        self._log_text.insert(tk.END, f"{entry.message}\n", entry.level)
        
        # Limit lines
        line_count = int(self._log_text.index('end-1c').split('.')[0])
        if line_count > CONFIG.LOG_MAX_LINES:
            self._log_text.delete('1.0', f'{line_count - CONFIG.LOG_MAX_LINES}.0')
        
        self._log_text.config(state=tk.DISABLED)
        
        # Auto-scroll if enabled
        if self._autoscroll_var.get():
            self._log_text.see(tk.END)
    
    def log(self, level: str, source: str, message: str) -> None:
        """
        Add a log message directly.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, SUCCESS)
            source: Source module name
            message: Log message
        """
        from datetime import datetime
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            source=source,
            message=message
        )
        self.add_entry(entry)
    
    def info(self, source: str, message: str) -> None:
        """Log info message."""
        self.log("INFO", source, message)
    
    def error(self, source: str, message: str) -> None:
        """Log error message."""
        self.log("ERROR", source, message)
    
    def success(self, source: str, message: str) -> None:
        """Log success message."""
        self.log("SUCCESS", source, message)
    
    def warning(self, source: str, message: str) -> None:
        """Log warning message."""
        self.log("WARNING", source, message)
    
    def clear(self) -> None:
        """Clear all log entries."""
        self._log_text.config(state=tk.NORMAL)
        self._log_text.delete('1.0', tk.END)
        self._log_text.config(state=tk.DISABLED)
    
    def set_progress(self, value: float, label: str = None) -> None:
        """
        Set progress bar value and optional label.
        
        Args:
            value: Progress value (0-100)
            label: Optional progress label
        """
        self._progress_var.set(value)
        if label:
            self._progress_label.config(text=label)
    
    def reset_progress(self) -> None:
        """Reset progress bar to idle state."""
        self._progress_var.set(0)
        self._progress_label.config(text="Idle")

    # Compatibility wrapper expected by MainWindow
    def update_progress(self, value: float, text: str = "") -> None:
        """Update progress value and optional text (alias for set_progress)."""
        self.set_progress(value, text)
    
    def _save_log(self) -> None:
        """Save log contents to file."""
        filepath = filedialog.asksaveasfilename(
            title="Save Log",
            defaultextension=".log",
            filetypes=[
                ("Log files", "*.log"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if filepath:
            content = self._log_text.get('1.0', tk.END)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("Error", f"Failed to save log: {e}")
    
    def get_log_content(self) -> str:
        """Get all log content as string."""
        return self._log_text.get('1.0', tk.END)