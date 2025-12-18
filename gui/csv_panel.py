"""
CSV management panel for RP2040 Programmer GUI.

Displays and manages the factory provisioning CSV file.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional

from core.csv_manager import CSVManager, CSVRow
from utils.persistence import PersistenceManager


class CSVPanel(ttk.LabelFrame):
    """
    Panel for CSV file management and row selection.
    
    Allows loading CSV files, viewing rows, and selecting units to program.
    """
    
    def __init__(
        self,
        parent: tk.Widget,
        csv_manager: CSVManager,
        persistence: PersistenceManager,
        on_row_selected: Optional[Callable[[CSVRow], None]] = None
    ):
        """
        Initialize CSV panel.
        
        Args:
            parent: Parent widget
            csv_manager: CSVManager instance
            persistence: PersistenceManager for storing paths
            on_row_selected: Callback when row is selected
        """
        super().__init__(parent, text="Serial Number Database", padding=10)
        
        self._csv_manager = csv_manager
        self._persistence = persistence
        self._on_row_selected = on_row_selected
        self._suppress_selection_event = False
        
        self._create_widgets()
        self._load_last_csv()
    
    def _create_widgets(self) -> None:
        """Create panel widgets."""
        # File selection row
        file_frame = ttk.Frame(self)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(file_frame, text="CSV File:").pack(side=tk.LEFT)
        
        self._file_var = tk.StringVar()
        self._file_entry = ttk.Entry(
            file_frame,
            textvariable=self._file_var,
            state="readonly",
            width=40
        )
        self._file_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self._browse_btn = ttk.Button(
            file_frame,
            text="Browse...",
            command=self._browse_csv
        )
        self._browse_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self._reload_btn = ttk.Button(
            file_frame,
            text="Reload",
            command=self._reload_csv,
            state=tk.DISABLED
        )
        self._reload_btn.pack(side=tk.LEFT)
        
        # Statistics row
        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill=tk.X, pady=(0, 5))
        
        self._stats_label = ttk.Label(
            stats_frame,
            text="No file loaded",
            foreground="gray"
        )
        self._stats_label.pack(side=tk.LEFT)
        
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            stats_frame,
            variable=self._progress_var,
            maximum=100,
            length=150
        )
        self._progress_bar.pack(side=tk.RIGHT)
        
        # Row selection
        selection_frame = ttk.Frame(self)
        selection_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(selection_frame, text="Selected:").pack(side=tk.LEFT)
        
        self._selected_var = tk.StringVar(value="None")
        self._selected_label = ttk.Label(
            selection_frame,
            textvariable=self._selected_var,
            font=("TkDefaultFont", 10, "bold")
        )
        self._selected_label.pack(side=tk.LEFT, padx=5)
        
        self._next_btn = ttk.Button(
            selection_frame,
            text="Next Unprogrammed",
            command=self._select_next_unprogrammed,
            state=tk.DISABLED
        )
        self._next_btn.pack(side=tk.RIGHT)
        
        # Row list
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("serial", "status", "date", "fw", "region")
        self._tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            height=6,
            selectmode="browse"
        )
        
        self._tree.heading("serial", text="Serial Number")
        self._tree.heading("status", text="Status")
        self._tree.heading("date", text="Date Programmed")
        self._tree.heading("fw", text="FW Version")
        self._tree.heading("region", text="Region")
        
        self._tree.column("serial", width=140)
        self._tree.column("status", width=80, anchor="center")
        self._tree.column("date", width=140)
        self._tree.column("fw", width=80)
        self._tree.column("region", width=50, anchor="center")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(
            list_frame,
            orient=tk.VERTICAL,
            command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scrollbar.set)
        
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        
        # Tags for row styling
        self._tree.tag_configure("programmed", background="#d4edda")
        self._tree.tag_configure("unprogrammed", background="#fff3cd")
        self._tree.tag_configure("selected", background="#cce5ff")
    
    def _load_last_csv(self) -> None:
        """Load last used CSV file."""
        last_path = self._persistence.get("last_csv_path", "")
        if last_path:
            # Use public wrapper to ensure callbacks (on_csv_loaded) are invoked
            self.load_csv(last_path)
    
    def _browse_csv(self) -> None:
        """Open file browser for CSV selection."""
        initial_dir = self._persistence.get("last_csv_path", "")
        if initial_dir:
            from pathlib import Path
            initial_dir = str(Path(initial_dir).parent)
        
        filepath = filedialog.askopenfilename(
            title="Select Serial Number CSV",
            initialdir=initial_dir or ".",
            filetypes=[
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]
        )
        
        if filepath:
            # Use public wrapper to ensure callbacks (on_csv_loaded) are invoked
            self.load_csv(filepath)

    # -----------------------------------------------------------------
    # Public wrappers for MainWindow compatibility
    # -----------------------------------------------------------------
    def load_csv(self, filepath: str) -> None:
        self._load_csv(filepath)
        # Notify if MainWindow attached a callback
        if hasattr(self, 'on_csv_loaded') and callable(getattr(self, 'on_csv_loaded')):
            try:
                self.on_csv_loaded(self._csv_manager)  # type: ignore[attr-defined]
            except Exception:
                pass
    
    def browse_csv(self) -> None:
        self._browse_csv()
    
    def set_editing_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self._browse_btn.config(state=state)
        self._reload_btn.config(state=state)
    
    def _load_csv(self, filepath: str) -> None:
        """Load CSV file."""
        if self._csv_manager.load(filepath):
            self._file_var.set(filepath)
            self._persistence.set("last_csv_path", filepath)
            self._persistence.add_recent_csv(filepath)
            self._reload_btn.config(state=tk.NORMAL)
            self._next_btn.config(state=tk.NORMAL)
            self._update_display()
        else:
            messagebox.showerror(
                "Error",
                f"Failed to load CSV file:\n{filepath}"
            )
    
    def _reload_csv(self) -> None:
        """Reload current CSV file."""
        path = self._csv_manager.path
        if path:
            # Use public wrapper so status and callbacks refresh
            self.load_csv(str(path))
    
    def _update_display(self) -> None:
        """Update all display elements."""
        # Clear tree
        for item in self._tree.get_children():
            self._tree.delete(item)

        # Populate rows incrementally to keep UI responsive on large CSVs
        self._rows_cache = list(self._csv_manager.rows)
        self._populate_chunk_index = 0
        self._populate_chunk_size = 500
        self._populate_tree_chunk()
        
        # Update statistics
        stats = self._csv_manager.get_statistics()
        self._stats_label.config(
            text=f"Total: {stats['total']} | "
                 f"Programmed: {stats['programmed']} | "
                 f"Remaining: {stats['remaining']}"
        )
        self._progress_var.set(stats['progress_percent'])
        
        # Update selection display
        self._update_selection_display()

    def _populate_tree_chunk(self) -> None:
        """Insert a chunk of rows into the tree to avoid UI stalls."""
        if not hasattr(self, "_rows_cache"):
            return
        end = min(self._populate_chunk_index + self._populate_chunk_size, len(self._rows_cache))
        for idx in range(self._populate_chunk_index, end):
            row = self._rows_cache[idx]
            status = "Done" if row.is_programmed else "Pending"
            tag = "programmed" if row.is_programmed else "unprogrammed"
            self._tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(
                    row.serial_number,
                    status,
                    row.date_programmed or "-",
                    row.firmware_version or "-",
                    row.region_code or "-"
                ),
                tags=(tag,)
            )
        self._populate_chunk_index = end
        if end < len(self._rows_cache):
            # Schedule next chunk
            self.after(1, self._populate_tree_chunk)
        else:
            # Cleanup cache when done
            del self._rows_cache
    
    def _update_selection_display(self) -> None:
        """Update selection label and tree highlight."""
        row = self._csv_manager.selected_row
        idx = self._csv_manager.selected_index
        
        if row:
            self._selected_var.set(row.serial_number)
            
            # Highlight in tree
            if idx is not None:
                # Only update tree selection if changed
                current = self._tree.selection()
                target = str(idx)
                if not current or current[0] != target:
                    # Suppress selection event and release after idle to avoid re-entrancy
                    self._suppress_selection_event = True
                    self._tree.selection_set(target)
                    self._tree.see(target)
                    # Delay unsetting suppression until after Tk processes events
                    self.after_idle(lambda: setattr(self, "_suppress_selection_event", False))
        else:
            self._selected_var.set("None")
    
    def _on_tree_select(self, event) -> None:
        """Handle row selection in treeview."""
        if self._suppress_selection_event:
            return
        selection = self._tree.selection()
        if selection:
            idx = int(selection[0])
            self._csv_manager.select_row(idx)
            # Update only the selected label to avoid triggering selection loops
            row = self._csv_manager.selected_row
            if row:
                self._selected_var.set(row.serial_number)
            
            if row and self._on_row_selected:
                self._on_row_selected(row)
    
    def _select_next_unprogrammed(self) -> None:
        """Select next unprogrammed row."""
        if self._csv_manager.select_next_unprogrammed():
            self._update_selection_display()
            
            row = self._csv_manager.selected_row
            if row and self._on_row_selected:
                self._on_row_selected(row)
        else:
            messagebox.showinfo(
                "Complete",
                "All units have been programmed!"
            )

    # Public alias expected by MainWindow
    def select_next_unprogrammed(self) -> None:
        self._select_next_unprogrammed()
    
    def get_selected_row(self) -> Optional[CSVRow]:
        """Get currently selected CSV row."""
        return self._csv_manager.selected_row
    
    def mark_row_complete(
        self,
        firmware_version: str,
        hardware_version: str,
        region_code: str,
        batch_id: str,
        notes: str
    ) -> bool:
        """
        Mark current row as programmed.
        
        Returns:
            True if update successful
        """
        if self._csv_manager.update_selected_row(
            firmware_version=firmware_version,
            hardware_version=hardware_version,
            region_code=region_code,
            batch_id=batch_id,
            notes=notes
        ):
            # Save immediately
            if self._csv_manager.save():
                self._update_display()
                return True
        return False
    
    def refresh(self) -> None:
        """Refresh display."""
        self._update_display()