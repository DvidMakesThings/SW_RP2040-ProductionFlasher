"""
Main Window - Integrates all GUI panels and orchestrates programming workflow.

This is the central controller that:
- Creates and arranges all GUI panels
- Handles the programming workflow state machine
- Coordinates between device detection, firmware upload, provisioning, and verification
- Manages threading for long-running operations
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import time
from datetime import datetime
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Dict, Any

from config.settings import Settings
from utils.logger import AppLogger, LogLevel
from utils.persistence import PersistenceManager
from core.device_detector import DeviceDetector, DeviceInfo, DeviceState
from core.firmware_uploader import FirmwareUploader, UploadResult
from core.serial_provisioner import SerialProvisioner, ProvisioningResult
from core.csv_manager import CSVManager
from core.verification import DeviceVerifier, VerificationResult, Verifier
from label.label_generator import LabelGenerator, LabelResult
from artefacts.report_generator import ReportGenerator, ProcessingReport, StepResult

from gui.device_panel import DevicePanel
from gui.csv_panel import CSVPanel
from gui.provisioning_panel import ProvisioningPanel
from gui.log_panel import LogPanel


class WorkflowState(Enum):
    """State machine for the programming workflow."""
    IDLE = auto()
    WAITING_FOR_DEVICE = auto()
    UPLOADING_FIRMWARE = auto()
    WAITING_FOR_SERIAL = auto()
    PROVISIONING = auto()
    VERIFYING = auto()
    GENERATING_LABEL = auto()
    GENERATING_REPORT = auto()
    UPDATING_CSV = auto()
    COMPLETED = auto()
    ERROR = auto()
    STOPPED = auto()


@dataclass
class WorkflowContext:
    """Context data passed through the workflow."""
    serial_number: str = ""
    firmware_version: str = ""
    hardware_version: str = ""
    region_code: str = ""
    batch_id: str = ""
    notes: str = ""
    firmware_path: str = ""
    device_path: str = ""
    serial_port: str = ""
    
    # Results from each step
    upload_result: Optional[UploadResult] = None
    provisioning_result: Optional[ProvisioningResult] = None
    verification_result: Optional[VerificationResult] = None
    label_result: Optional[LabelResult] = None
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class MainWindow:
    """
    Main application window integrating all panels and workflow control.
    """
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"RP2040 Programmer v{Settings.VERSION}")
        self.root.geometry("1200x800")
        self.root.minsize(1200, 800)
        
        # Initialize components
        self.logger = AppLogger()
        self.persistence = PersistenceManager()
        self.device_detector = DeviceDetector()
        self.csv_manager: Optional[CSVManager] = CSVManager()
        
        # Workflow state
        self.workflow_state = WorkflowState.IDLE
        self.workflow_context: Optional[WorkflowContext] = None
        self.workflow_thread: Optional[threading.Thread] = None
        self.stop_requested = False
        
        # Message queue for thread-safe GUI updates
        self.message_queue = queue.Queue()
        
        # Current device info
        self.current_device: Optional[DeviceInfo] = None
        
        # Build GUI
        self._create_menu()
        self._create_layout()
        self._setup_callbacks()
        self._restore_state()
        
        # Start device detection
        self.device_detector.start()
        
        # Start message queue processor
        self._process_message_queue()

        # Lightweight UI heartbeat to ensure Tk stays active (debug aid)
        self._hb_tick = 0
        self.root.after(1000, self._ui_heartbeat)
        
        # Log startup
        self.logger.info("RP2040 Programmer started")
        self.logger.info(f"Platform: {Settings.PLATFORM}")
        
    def _create_menu(self):
        """Create application menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open CSV...", command=self._on_open_csv)
        file_menu.add_command(label="Select Firmware...", command=self._on_select_firmware)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_exit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Refresh Devices", command=self._on_refresh_devices)
        tools_menu.add_command(label="Test Label Print", command=self._on_test_label)
        tools_menu.add_separator()
        tools_menu.add_command(label="Open Artefacts Folder", command=self._on_open_artefacts)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._on_about)
        
    def _create_layout(self):
        """Create main window layout with all panels."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top section: Device and CSV panels side by side
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Left: Device panel
        device_frame = ttk.LabelFrame(top_frame, text="Detected Devices", padding="5")
        device_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.device_panel = DevicePanel(
            device_frame,
            self.device_detector,
            on_enter_boot_mode=self._on_enter_boot_mode
        )
        # Show panel inside its container
        self.device_panel.pack(fill=tk.BOTH, expand=True)
        
        # Right: CSV panel
        csv_frame = ttk.LabelFrame(top_frame, text="Production CSV", padding="5")
        csv_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.csv_panel = CSVPanel(csv_frame, self.csv_manager, self.persistence, on_row_selected=self._on_row_selected)
        # Show panel inside its container
        self.csv_panel.pack(fill=tk.BOTH, expand=True)
        
        # Middle section: Provisioning panel
        prov_frame = ttk.LabelFrame(main_frame, text="Provisioning Settings", padding="5")
        prov_frame.pack(fill=tk.X, pady=(0, 5))
        self.provisioning_panel = ProvisioningPanel(prov_frame, self.persistence)
        # Show panel inside its container
        self.provisioning_panel.pack(fill=tk.X, expand=False)
        
        # Bottom section: Log panel
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_panel = LogPanel(log_frame)
        # Show panel inside its container
        self.log_panel.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self._create_status_bar()
        
    def _create_status_bar(self):
        """Create status bar at bottom of window."""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Workflow state indicator
        self.state_label = ttk.Label(status_frame, text="State: IDLE", width=30)
        self.state_label.pack(side=tk.LEFT, padx=5)
        
        # Separator
        ttk.Separator(status_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Device count
        self.device_count_label = ttk.Label(status_frame, text="Devices: 0")
        self.device_count_label.pack(side=tk.LEFT, padx=5)
        
        # Separator
        ttk.Separator(status_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # CSV status
        self.csv_status_label = ttk.Label(status_frame, text="CSV: Not loaded")
        self.csv_status_label.pack(side=tk.LEFT, padx=5)
        
        # Right side: version
        version_label = ttk.Label(status_frame, text=f"v{Settings.VERSION}")
        version_label.pack(side=tk.RIGHT, padx=5)
        
    def _setup_callbacks(self):
        """Set up callbacks between panels and components."""
        # Device detector callbacks
        self.device_detector.on_device_added = self._on_device_added
        self.device_detector.on_device_removed = self._on_device_removed
        self.device_detector.on_device_changed = self._on_device_changed
        
        # Logger callback for GUI
        self.logger.set_callback(self._on_log_message)
        
        # Provisioning panel callbacks
        self.provisioning_panel.on_start = self._on_start_programming
        self.provisioning_panel.on_stop = self._on_stop_programming
        
        # CSV panel callbacks
        self.csv_panel.on_csv_loaded = self._on_csv_loaded
        self.csv_panel.on_row_selected = self._on_row_selected
        
        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_exit)

        # If CSV was auto-loaded by CSVPanel before callbacks were attached,
        # emit the CSV loaded callback now so status/UI reflect it.
        try:
            if self.csv_manager and self.csv_manager.is_loaded:
                self._on_csv_loaded(self.csv_manager)
        except Exception:
            pass
        
    def _restore_state(self):
        """Restore application state from persistence."""
        # Restore window geometry
        geometry = self.persistence.get("window_geometry")
        if geometry:
            try:
                self.root.geometry(geometry)
            except:
                pass
                
        # Auto-load last CSV if it exists and not already loaded by CSVPanel
        last_csv = self.persistence.get("last_csv_path")
        try:
            already_loaded = bool(self.csv_manager and self.csv_manager.is_loaded)
        except Exception:
            already_loaded = False
        if last_csv and not already_loaded:
            # Public wrapper will load and trigger callbacks
            self.csv_panel.load_csv(last_csv)
            
    def _save_state(self):
        """Save application state to persistence."""
        self.persistence.set("window_geometry", self.root.geometry())
        
    # =========================================================================
    # Message Queue Processing (for thread-safe GUI updates)
    # =========================================================================
    
    def _process_message_queue(self):
        """Process messages from worker threads without blocking UI."""
        processed = 0
        max_per_tick = 100
        try:
            while processed < max_per_tick:
                msg = self.message_queue.get_nowait()
                msg_type = msg.get("type")
                
                if msg_type == "log":
                    self.log_panel.add_entry(msg["entry"])
                elif msg_type == "state":
                    self._update_workflow_state(msg["state"])
                elif msg_type == "progress":
                    self.log_panel.update_progress(msg["value"], msg.get("text", ""))
                elif msg_type == "complete":
                    self._on_workflow_complete(msg.get("success", False))
                elif msg_type == "error":
                    self._on_workflow_error(msg["message"])
                processed += 1
        except queue.Empty:
            pass
            
        # Schedule next check
        self.root.after(50, self._process_message_queue)
        
    def _queue_message(self, msg: Dict[str, Any]):
        """Queue a message for GUI thread processing."""
        self.message_queue.put(msg)

    def _ui_heartbeat(self):
        """Periodic update to keep UI lively and detect stalls."""
        try:
            self._hb_tick = (self._hb_tick + 1) % 10
            # Update state label subtly without interfering with real states
            current = self.state_label.cget("text")
            if "State:" in current:
                self.state_label.config(text=current.split(" [")[0] + f" [{self._hb_tick}]")
        except Exception:
            pass
        finally:
            self.root.after(1000, self._ui_heartbeat)
        
    # =========================================================================
    # Device Detection Callbacks
    # =========================================================================
    
    def _on_device_added(self, device: DeviceInfo):
        """Handle new device detection."""
        self.root.after(10, lambda: self._handle_device_added(device))
        
    def _handle_device_added(self, device: DeviceInfo):
        """Handle device added on GUI thread."""
        self.device_panel.refresh()
        self._update_device_count()
        
        if device.state == DeviceState.BOOTSEL:
            self.logger.success(f"RP2040 detected in BOOTSEL mode: {device.path}")
            self.current_device = device
            self.provisioning_panel.set_device_ready(True)
        elif device.state == DeviceState.SERIAL:
            self.logger.info(f"Serial port detected: {device.path}")
            
    def _on_device_removed(self, device: DeviceInfo):
        """Handle device removal."""
        self.root.after(10, lambda: self._handle_device_removed(device))
        
    def _handle_device_removed(self, device: DeviceInfo):
        """Handle device removed on GUI thread."""
        self.device_panel.refresh()
        self._update_device_count()
        
        if self.current_device and self.current_device.path == device.path:
            self.current_device = None
            self.provisioning_panel.set_device_ready(False)
            self.logger.warning(f"Device removed: {device.path}")
            
    def _on_device_changed(self, device: DeviceInfo):
        """Handle device state change."""
        self.root.after(50, lambda: self.device_panel.refresh())
        
    def _update_device_count(self):
        """Update device count in status bar."""
        devices = self.device_detector.get_devices()
        bootsel_count = sum(1 for d in devices if d.state == DeviceState.BOOTSEL)
        serial_count = sum(1 for d in devices if d.state == DeviceState.SERIAL)
        self.device_count_label.config(
            text=f"Devices: {bootsel_count} BOOTSEL, {serial_count} Serial"
        )
        
    # =========================================================================
    # CSV Callbacks
    # =========================================================================
    
    def _on_csv_loaded(self, csv_manager: CSVManager):
        """Handle CSV file loaded."""
        self.csv_manager = csv_manager
        stats = csv_manager.get_statistics()
        self.csv_status_label.config(
            text=f"CSV: {stats['remaining']} remaining of {stats['total']}"
        )
        self.provisioning_panel.set_csv_ready(True)
        
    def _on_row_selected(self, row_data):
        """Handle CSV row selection."""
        if row_data and hasattr(row_data, 'serial_number'):
            self.provisioning_panel.set_serial_number(row_data.serial_number)
            
    # =========================================================================
    # Log Callback
    # =========================================================================
    
    def _on_log_message(self, entry):
        """Handle log message (may be called from any thread)."""
        self._queue_message({"type": "log", "entry": entry})
        
    # =========================================================================
    # Workflow Control
    # =========================================================================
    
    def _on_start_programming(self):
        """Start the programming workflow."""
        # Validate prerequisites
        if not self._validate_prerequisites():
            return
            
        # Get parameters from panels
        params = self.provisioning_panel.get_parameters()
        row = self.csv_panel.get_selected_row()
        
        if not row:
            messagebox.showerror("Error", "No CSV row selected")
            return
            
        # Create workflow context
        self.workflow_context = WorkflowContext(
            serial_number=row.serial_number if row else "",
            firmware_version=params.get("firmware_version", ""),
            hardware_version=params.get("hardware_version", ""),
            region_code=params.get("region_code", "EU"),
            batch_id=params.get("batch_id", ""),
            notes=params.get("notes", ""),
            firmware_path=params.get("firmware_path", ""),
            device_path=self.current_device.path if self.current_device else "",
            start_time=datetime.now()
        )
        
        # Reset stop flag
        self.stop_requested = False
        
        # Update UI state
        self.provisioning_panel.set_programming_active(True)
        self.csv_panel.set_editing_enabled(False)
        
        # Start workflow thread
        self.workflow_thread = threading.Thread(target=self._run_workflow, daemon=True)
        self.workflow_thread.start()
        
        self.logger.info(f"Starting programming for {self.workflow_context.serial_number}")
        
    def _on_stop_programming(self):
        """Stop the programming workflow."""
        self.stop_requested = True
        self._queue_message({"type": "state", "state": WorkflowState.STOPPED})
        self.logger.warning("Stop requested - workflow will halt after current step")
        
    def _validate_prerequisites(self) -> bool:
        """Validate all prerequisites for programming."""
        errors = []
        
        # Check device; if not set, attempt to select first available BOOTSEL
        if not self.current_device or self.current_device.state != DeviceState.BOOTSEL:
            try:
                bootsel_devs = self.device_detector.get_bootsel_devices()
                if bootsel_devs:
                    self.current_device = bootsel_devs[0]
                    # Hint the provisioning panel
                    self.provisioning_panel.set_device_ready(True)
                else:
                    errors.append("No device in BOOTSEL mode detected")
            except Exception:
                errors.append("No device in BOOTSEL mode detected")
            
        # Check CSV
        if not self.csv_manager:
            errors.append("No CSV file loaded")
            
        # Check firmware
        params = self.provisioning_panel.get_parameters()
        if not params.get("firmware_path"):
            errors.append("No firmware file selected")
            
        # Validate provisioning panel inputs
        validation_errors = self.provisioning_panel.validate_inputs()
        errors.extend(validation_errors)
        
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return False
            
        return True
        
    def _update_workflow_state(self, state: WorkflowState):
        """Update workflow state and UI."""
        self.workflow_state = state
        self.state_label.config(text=f"State: {state.name}")
        
        # Update progress based on state
        progress_map = {
            WorkflowState.IDLE: (0, "Ready"),
            WorkflowState.WAITING_FOR_DEVICE: (5, "Waiting for device..."),
            WorkflowState.UPLOADING_FIRMWARE: (15, "Uploading firmware..."),
            WorkflowState.WAITING_FOR_SERIAL: (35, "Waiting for serial port..."),
            WorkflowState.PROVISIONING: (50, "Provisioning device..."),
            WorkflowState.VERIFYING: (70, "Verifying settings..."),
            WorkflowState.GENERATING_LABEL: (80, "Generating label..."),
            WorkflowState.GENERATING_REPORT: (90, "Generating report..."),
            WorkflowState.UPDATING_CSV: (95, "Updating CSV..."),
            WorkflowState.COMPLETED: (100, "Completed!"),
            WorkflowState.ERROR: (0, "Error occurred"),
            WorkflowState.STOPPED: (0, "Stopped by user"),
        }
        
        progress, text = progress_map.get(state, (0, ""))
        self.log_panel.update_progress(progress, text)

    def _wait_for_rp2040_serial(self, timeout: float) -> Optional[str]:
        """Poll for a new RP2040 serial port without emitting detector warnings.

        Returns the detected port path or None on timeout.
        """
        import time as _time
        import serial.tools.list_ports as _lp

        start = _time.time()
        initial = {p.device for p in _lp.comports()}
        while (_time.time() - start) < timeout:
            for port in _lp.comports():
                if port.device not in initial and port.vid == Settings.RP2040_USB_VID:
                    self.logger.info(f"Serial port detected: {port.device}")
                    return port.device
            _time.sleep(0.1)
        return None
        
    def _run_workflow(self):
        """Run the complete programming workflow (in worker thread)."""
        ctx = self.workflow_context
        report = ProcessingReport(
            serial_number=ctx.serial_number,
            firmware_version=ctx.firmware_version,
            hardware_version=ctx.hardware_version,
            region_code=ctx.region_code
        )
        
        try:
            # Step 1: Upload firmware
            if self.stop_requested:
                return
            self._queue_message({"type": "state", "state": WorkflowState.UPLOADING_FIRMWARE})
            
            uploader = FirmwareUploader(self.logger)
            _t0 = time.time()
            ctx.upload_result = uploader.upload(ctx.firmware_path, ctx.device_path)
            report.firmware_upload_time = time.time() - _t0
            
            report.add_step(StepResult(
                name="Firmware Upload",
                success=ctx.upload_result.success,
                message=ctx.upload_result.message,
                details={"exit_code": ctx.upload_result.exit_code}
            ))
            report.firmware_version = ctx.firmware_version
            report.hardware_version = ctx.hardware_version
            report.region_code = ctx.region_code
            report.firmware_upload_success = ctx.upload_result.success
            
            if not ctx.upload_result.success:
                raise Exception(f"Firmware upload failed: {ctx.upload_result.message}")
                
            self.logger.success("Firmware uploaded successfully")
            
            # Step 2: Wait for serial port
            if self.stop_requested:
                return
            self._queue_message({"type": "state", "state": WorkflowState.WAITING_FOR_SERIAL})
            
            serial_port = self.device_detector.wait_for_serial_port(
                timeout=Settings.SERIAL_RECONNECT_TIMEOUT
            )
            
            if not serial_port:
                raise Exception("Serial port did not appear after firmware upload")
                
            ctx.serial_port = serial_port
            self.logger.info(f"Serial port detected: {serial_port}")
            
            # Step 3: Provisioning
            if self.stop_requested:
                return
            self._queue_message({"type": "state", "state": WorkflowState.PROVISIONING})
            
            provisioner = SerialProvisioner(self.logger)
            _t1 = time.time()
            ctx.provisioning_result = provisioner.provision(
                port=ctx.serial_port,
                serial_number=ctx.serial_number,
                region_code=ctx.region_code
            )
            report.provisioning_time = time.time() - _t1
            
            report.add_step(StepResult(
                name="Provisioning",
                success=ctx.provisioning_result.success,
                message=ctx.provisioning_result.message,
                details=ctx.provisioning_result.responses
            ))
            report.provisioning_success = ctx.provisioning_result.success
            
            if not ctx.provisioning_result.success:
                raise Exception(f"Provisioning failed: {ctx.provisioning_result.message}")
            
            # Step 4: Verification (after reboot)
            if self.stop_requested:
                return
            self._queue_message({"type": "state", "state": WorkflowState.VERIFYING})
            
            # After provisioning, the provisioner performs reboot→reconnect→ready.
            # Use its connected port; fall back to a reconnect wait if needed.
            serial_port = provisioner.port or provisioner.reboot_and_reconnect_wait_ready()
            if not serial_port:
                raise Exception("Serial port did not reappear after reboot")
            # Provisioner has already ensured readiness; update context and proceed
            ctx.serial_port = serial_port
                
            # Verify using the already-connected provisioner to avoid double reconnect/logs
            verifier = Verifier(provisioner)
            ctx.verification_result = verifier.verify(
                serial_number=ctx.serial_number,
                region=ctx.region_code,
                firmware_version=ctx.firmware_version,
                hardware_version=ctx.hardware_version
            )
            
            report.add_step(StepResult(
                name="Verification",
                success=ctx.verification_result.success,
                message="All checks passed" if ctx.verification_result.success else "Verification failed",
                details=ctx.verification_result.checks
            ))
            report.verification_success = ctx.verification_result.success
            report.verification_result = ctx.verification_result
            
            if not ctx.verification_result.success:
                failed = [k for k, v in ctx.verification_result.checks.items() if not v]
                raise Exception(f"Verification failed: {', '.join(failed)}")
                
            self.logger.success("Verification passed")
            
            # Step 5: Generate label
            if self.stop_requested:
                return
            self._queue_message({"type": "state", "state": WorkflowState.GENERATING_LABEL})
            
            label_gen = LabelGenerator(self.logger)
            ctx.label_result = label_gen.generate(
                serial_number=ctx.serial_number,
                region=ctx.region_code
            )
            
            report.add_step(StepResult(
                name="Label Generation",
                success=ctx.label_result.success,
                message=ctx.label_result.message,
                details={"output_path": ctx.label_result.output_path}
            ))
            
            if not ctx.label_result.success:
                self.logger.warning(f"Label generation failed: {ctx.label_result.message}")
            else:
                self.logger.success(f"Label generated: {ctx.label_result.output_path}")
                report.label_generated = True
                report.label_path = ctx.label_result.output_path or ""
                
                # Print label if auto-print enabled
                params = self.provisioning_panel.get_parameters()
                if params.get("auto_print_label"):
                    print_result = label_gen.print_label(ctx.label_result.output_path)
                    if print_result.success:
                        self.logger.success("Label sent to printer")
                        report.label_printed = True
                    else:
                        self.logger.warning(f"Label printing failed: {print_result.message}")
                        
            # Step 6: Generate report and archive
            if self.stop_requested:
                return
            self._queue_message({"type": "state", "state": WorkflowState.GENERATING_REPORT})
            
            ctx.end_time = datetime.now()
            report.end_time = ctx.end_time
            report.total_time = (ctx.end_time - ctx.start_time).total_seconds() if ctx.start_time else 0.0
            report.success = True
            report.overall_success = True
            
            report_gen = ReportGenerator(self.logger)
            artefact_path = report_gen.generate(
                report=report,
                label_path=ctx.label_result.output_path if ctx.label_result and ctx.label_result.success else None,
                serial_log_path=self.logger.get_serial_log_path()
            )
            
            self.logger.info(f"Artefacts saved to: {artefact_path}")
            
            # Step 7: Update CSV
            if self.stop_requested:
                return
            self._queue_message({"type": "state", "state": WorkflowState.UPDATING_CSV})
            
            if self.csv_manager:
                # Ensure selected row corresponds to current serial
                self.csv_manager.select_by_serial(ctx.serial_number)
                success = self.csv_manager.update_selected_row(
                    firmware_version=ctx.firmware_version,
                    hardware_version=ctx.hardware_version,
                    region_code=ctx.region_code,
                    batch_id=ctx.batch_id,
                    notes=ctx.notes,
                    mark_programmed=True
                )
                if success:
                    # Persist to disk
                    saved = self.csv_manager.save()
                    if saved:
                        self.logger.success("CSV updated")
                    else:
                        self.logger.warning("Failed to save CSV to disk")
                else:
                    self.logger.warning("Failed to update CSV")
                    
            # Complete!
            self._queue_message({"type": "state", "state": WorkflowState.COMPLETED})
            self._queue_message({"type": "complete", "success": True})
            
        except Exception as e:
            self.logger.error(f"Workflow error: {str(e)}")
            report.overall_success = False
            report.error_message = str(e)
            self._queue_message({"type": "error", "message": str(e)})
            
    def _on_workflow_complete(self, success: bool):
        """Handle workflow completion."""
        self.provisioning_panel.set_programming_active(False)
        self.csv_panel.set_editing_enabled(True)
        
        if success:
            self.logger.success(f"Programming complete for {self.workflow_context.serial_number}")
            messagebox.showinfo("Success", 
                f"Device {self.workflow_context.serial_number} programmed successfully!")
            
            # Auto-select next if enabled
            params = self.provisioning_panel.get_parameters()
            if params.get("auto_select_next"):
                self.csv_panel.select_next_unprogrammed()
                
            # Refresh CSV display
            self.csv_panel.refresh()
            self._update_csv_status()
        else:
            self.logger.error("Programming failed")
            
        self.workflow_context = None
        self._update_workflow_state(WorkflowState.IDLE)
        
    def _on_workflow_error(self, message: str):
        """Handle workflow error."""
        self.provisioning_panel.set_programming_active(False)
        self.csv_panel.set_editing_enabled(True)
        self._update_workflow_state(WorkflowState.ERROR)
        
        messagebox.showerror("Programming Failed", message)
        
        self.workflow_context = None
        
    def _update_csv_status(self):
        """Update CSV status in status bar."""
        if self.csv_manager:
            stats = self.csv_manager.get_statistics()
            self.csv_status_label.config(
                text=f"CSV: {stats['remaining']} remaining of {stats['total']}"
            )
            
    # =========================================================================
    # Menu Actions
    # =========================================================================
    
    def _on_open_csv(self):
        """Handle Open CSV menu action."""
        self.csv_panel.browse_csv()
        
    def _on_select_firmware(self):
        """Handle Select Firmware menu action."""
        self.provisioning_panel.browse_firmware()
        
    def _on_refresh_devices(self):
        """Handle Refresh Devices menu action."""
        self.device_detector.scan_now()
        self.device_panel.refresh()
        self._update_device_count()

    def _on_enter_boot_mode(self, device: Optional[DeviceInfo] = None):
        """Send BOOTSEL command over serial to enter BOOT mode."""
        try:
            # Determine target serial port
            port = None
            if device and device.state == DeviceState.SERIAL:
                port = device.path
            else:
                serial_devs = self.device_detector.get_serial_devices()
                if serial_devs:
                    port = serial_devs[0].path
            if not port:
                messagebox.showwarning("Enter BOOT Mode", "No RP2040 serial device detected.")
                return

            self.logger.info(f"Sending BOOTSEL to {port}")
            provisioner = SerialProvisioner(self.logger)
            if not provisioner.connect(port):
                messagebox.showerror("Enter BOOT Mode", f"Failed to open port: {port}")
                return

            # Send BOOTSEL command; device should switch to BOOTSEL and drop serial
            provisioner.send_command("BOOTSEL", expect_response=False)
            # Small grace period before disconnect
            time.sleep(0.2)
            provisioner.disconnect()

            # Refresh devices after a short delay to observe disappearance and reappearance
            self.root.after(500, lambda: self._on_refresh_devices())
            self.logger.success("Device commanded to enter BOOT mode")
        except Exception as e:
            self.logger.error(f"Enter BOOT Mode failed: {e}")
            messagebox.showerror("Enter BOOT Mode", f"Operation failed: {e}")
        
    def _on_test_label(self):
        """Handle Test Label Print menu action."""
        label_gen = LabelGenerator(self.logger)
        params = self.provisioning_panel.get_parameters()
        region = params.get("region_code", "EU")
        result = label_gen.generate_and_print("TEST-000000", region)
        if result.success:
            self.logger.success("Label sent to printer")
            messagebox.showinfo("Test Label", "Test label sent to printer")
        else:
            self.logger.error(f"Label print failed: {result.message}")
            messagebox.showerror("Error", f"Label print failed: {result.message}")
            
    def _on_open_artefacts(self):
        """Open artefacts folder in file explorer."""
        import subprocess
        import os
        
        path = Settings.ARTEFACT_BASE_PATH
        os.makedirs(path, exist_ok=True)
        
        if Settings.PLATFORM == "Windows":
            subprocess.run(["explorer", path])
        else:
            subprocess.run(["xdg-open", path])
            
    def _on_about(self):
        """Show about dialog."""
        messagebox.showinfo("About", 
            f"RP2040 Programmer\n"
            f"Version {Settings.VERSION}\n\n"
            f"Factory programming tool for ENERGIS PDU devices.\n\n"
            f"Platform: {Settings.PLATFORM}"
        )
        
    def _on_exit(self):
        """Handle application exit."""
        if self.workflow_state not in (WorkflowState.IDLE, WorkflowState.COMPLETED, 
                                        WorkflowState.ERROR, WorkflowState.STOPPED):
            if not messagebox.askyesno("Confirm Exit", 
                "Programming is in progress. Are you sure you want to exit?"):
                return
                
        # Stop device detector
        self.device_detector.stop()
        
        # Save state
        self._save_state()
        
        # Destroy window
        self.root.destroy()