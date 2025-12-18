"""
Label generation and printing module.

Generates rating labels from SVG templates and prints via system printer.
"""
import io
import sys
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from config.settings import CONFIG
from utils.logger import get_logger

# Conditional imports for SVG rendering
try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    SVG_AVAILABLE = True
except ImportError:
    SVG_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class LabelStatus(Enum):
    """Label generation/printing status."""
    SUCCESS = "success"
    TEMPLATE_NOT_FOUND = "template_not_found"
    RENDER_ERROR = "render_error"
    PRINT_ERROR = "print_error"
    PRINTER_NOT_FOUND = "printer_not_found"
    LIBRARY_MISSING = "library_missing"


@dataclass
class LabelResult:
    """Result of label operation."""
    status: LabelStatus
    message: str
    png_path: Optional[Path] = None
    
    @property
    def success(self) -> bool:
        return self.status == LabelStatus.SUCCESS
    
    @property
    def output_path(self) -> Optional[str]:
        return str(self.png_path) if self.png_path else None


class LabelGenerator:
    """
    Generates and prints rating labels for ENERGIS PDU devices.
    
    Uses SVG templates with placeholder replacement.
    """
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize label generator.
        
        Args:
            template_dir: Directory containing SVG templates
        """
        # Allow older call style LabelGenerator(logger)
        if template_dir is not None and not isinstance(template_dir, str):
            self._logger = template_dir  # type: ignore[assignment]
            self._template_dir = Path(CONFIG.TEMPLATE_DIR)
        else:
            self._logger = get_logger()
            self._template_dir = Path(template_dir) if template_dir else Path(CONFIG.TEMPLATE_DIR)
        self._printer_name = CONFIG.PRINTER_NAME
    
    @property
    def template_dir(self) -> Path:
        """Get template directory."""
        return self._template_dir
    
    @template_dir.setter
    def template_dir(self, path: str) -> None:
        """Set template directory."""
        self._template_dir = Path(path)
    
    @property
    def printer_name(self) -> str:
        """Get configured printer name."""
        return self._printer_name
    
    @printer_name.setter
    def printer_name(self, name: str) -> None:
        """Set printer name."""
        self._printer_name = name
    
    def check_dependencies(self) -> tuple[bool, str]:
        """
        Check if required libraries are available.
        
        Returns:
            Tuple of (available, message)
        """
        if not SVG_AVAILABLE:
            return False, "svglib/reportlab not installed. Run: pip install svglib reportlab"
        if not PIL_AVAILABLE:
            return False, "Pillow not installed. Run: pip install Pillow"
        return True, "All label dependencies available"
    
    def get_template_path(self, region: str) -> Path:
        """Get SVG template path for region."""
        template_name = CONFIG.get_label_template(region)
        return self._template_dir / template_name
    
    def generate_label(
        self,
        serial_number: str,
        region: str,
        output_path: Optional[str] = None
    ) -> LabelResult:
        """
        Generate label PNG from SVG template.
        
        Args:
            serial_number: Device serial number
            region: Region code for template selection
            output_path: Optional output PNG path
        
        Returns:
            LabelResult with status and output path
        """
        self._logger.info(
            "LabelGenerator",
            f"Generating label for SN={serial_number}, Region={region}"
        )
        
        # Check dependencies
        deps_ok, deps_msg = self.check_dependencies()
        if not deps_ok:
            self._logger.error("LabelGenerator", deps_msg)
            return LabelResult(
                status=LabelStatus.LIBRARY_MISSING,
                message=deps_msg
            )
        
        # Get template
        template_path = self.get_template_path(region)
        if not template_path.exists():
            msg = f"Template not found: {template_path}"
            self._logger.error("LabelGenerator", msg)
            return LabelResult(
                status=LabelStatus.TEMPLATE_NOT_FOUND,
                message=msg
            )
        
        try:
            # Read and modify SVG
            svg_content = template_path.read_text(encoding='utf-8')
            svg_modified = svg_content.replace(
                CONFIG.LABEL_SERIAL_PLACEHOLDER,
                serial_number
            )
            
            # Create temp SVG file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.svg',
                delete=False,
                encoding='utf-8'
            ) as tmp_svg:
                tmp_svg.write(svg_modified)
                tmp_svg_path = tmp_svg.name
            
            # Convert SVG to PNG
            drawing = svg2rlg(tmp_svg_path)
            if drawing is None:
                raise ValueError("Failed to parse SVG")
            
            # Calculate size in pixels
            width_px = int(CONFIG.LABEL_WIDTH_MM / 25.4 * CONFIG.LABEL_DPI)
            height_px = int(CONFIG.LABEL_HEIGHT_MM / 25.4 * CONFIG.LABEL_DPI)
            
            # Determine output path
            if output_path:
                png_path = Path(output_path)
            else:
                png_path = Path(tempfile.gettempdir()) / f"label_{serial_number}.png"
            
            # Render to PNG
            png_path.parent.mkdir(parents=True, exist_ok=True)
            renderPM.drawToFile(
                drawing,
                str(png_path),
                fmt="PNG",
                dpi=CONFIG.LABEL_DPI
            )
            
            # Resize to exact dimensions and set DPI metadata
            self._resize_image(png_path, width_px, height_px, dpi=CONFIG.LABEL_DPI)
            
            # Clean up temp file
            Path(tmp_svg_path).unlink(missing_ok=True)
            
            self._logger.success(
                "LabelGenerator",
                f"Label generated: {png_path}"
            )
            return LabelResult(
                status=LabelStatus.SUCCESS,
                message="Label generated successfully",
                png_path=png_path
            )
        
        except Exception as e:
            msg = f"Label generation error: {e}"
            self._logger.error("LabelGenerator", msg)
            return LabelResult(
                status=LabelStatus.RENDER_ERROR,
                message=msg
            )
    
    # Compatibility wrapper expected by GUI
    def generate(self, serial_number: str, region: str):
        return self.generate_label(serial_number=serial_number, region=region)
    
    def _resize_image(self, path: Path, width: int, height: int, dpi: int = 300) -> None:
        """Resize image to exact dimensions and embed DPI metadata."""
        if not PIL_AVAILABLE:
            return
        
        try:
            with Image.open(path) as img:
                if img.size != (width, height):
                    img = img.resize((width, height), Image.LANCZOS)
                # Always save with explicit DPI so printers can honor physical size
                img.save(path, "PNG", dpi=(dpi, dpi))
        except Exception as e:
            self._logger.warning("LabelGenerator", f"Resize warning: {e}")
    
    def print_label(self, png_path: str) -> LabelResult:
        """
        Print label PNG to configured printer.
        
        Args:
            png_path: Path to PNG file
        
        Returns:
            LabelResult with print status
        """
        png_file = Path(png_path)
        
        if not png_file.exists():
            return LabelResult(
                status=LabelStatus.RENDER_ERROR,
                message=f"PNG file not found: {png_path}"
            )
        
        self._logger.info(
            "LabelGenerator",
            f"Printing label to {self._printer_name}"
        )
        
        if sys.platform == "win32":
            return self._print_windows(png_file)
        else:
            return self._print_linux(png_file)
    
    def _print_windows(self, png_path: Path) -> LabelResult:
        """Print using Windows PowerShell with .NET PrintDocument, selecting 'Label_' paper and scaling to page bounds."""
        try:
            printer = self._printer_name.replace('"', '`"')
            file_arg = str(png_path).replace('"', '`"')
            paper_name = "Label_"
            # Use placeholder replacement to avoid Python format/f-string brace conflicts
            ps_template = """
Add-Type -AssemblyName System.Drawing
$img = [System.Drawing.Image]::FromFile("__FILE__")
$doc = New-Object System.Drawing.Printing.PrintDocument
$doc.PrinterSettings.PrinterName = "__PRINTER__"
# Try select paper size named Label_
$ps = $doc.PrinterSettings.PaperSizes | Where-Object { $_.PaperName -eq "__PAPER__" }
if (-not $ps) { $ps = $doc.PrinterSettings.PaperSizes | Where-Object { $_.PaperName -like "Label*" } | Select-Object -First 1 }
if ($ps) { $doc.DefaultPageSettings.PaperSize = $ps }
$doc.DefaultPageSettings.Margins = New-Object System.Drawing.Printing.Margins(0,0,0,0)
$doc.PrintController = New-Object System.Drawing.Printing.StandardPrintController
$doc.add_PrintPage({ param($sender, $e)
    # Scale to margin bounds (like full-page photo)
    $bounds = $e.MarginBounds
    $iw = [double]$img.Width
    $ih = [double]$img.Height
    $ratio = $iw / $ih
    $tw = [int]$bounds.Width
    $th = [int]($tw / $ratio)
    if ($th -gt $bounds.Height) {
        $th = [int]$bounds.Height
        $tw = [int]($th * $ratio)
    }
    $x = [int]($bounds.X + (($bounds.Width - $tw) / 2))
    $y = [int]($bounds.Y + (($bounds.Height - $th) / 2))
    $rect = New-Object System.Drawing.Rectangle($x, $y, $tw, $th)
    $e.Graphics.DrawImage($img, $rect)
    $e.HasMorePages = $false
})
$doc.Print()
$img.Dispose()
$doc.Dispose()
"""
            ps_script = (
                ps_template
                .replace("__FILE__", file_arg)
                .replace("__PRINTER__", printer)
                .replace("__PAPER__", paper_name)
            )
            cmd = ["powershell", "-NoProfile", "-Command", ps_script]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                self._logger.success("LabelGenerator", "Print job sent")
                return LabelResult(
                    status=LabelStatus.SUCCESS,
                    message="Print job sent successfully",
                    png_path=png_path
                )
            else:
                msg = f"Print error: {result.stderr or result.stdout}"
                self._logger.error("LabelGenerator", msg)
                return LabelResult(
                    status=LabelStatus.PRINT_ERROR,
                    message=msg,
                    png_path=png_path
                )
        except subprocess.TimeoutExpired:
            return LabelResult(
                status=LabelStatus.PRINT_ERROR,
                message="Print job timed out",
                png_path=png_path
            )
        except Exception as e:
            return LabelResult(
                status=LabelStatus.PRINT_ERROR,
                message=f"Print error: {e}",
                png_path=png_path
            )
    
    def _print_linux(self, png_path: Path) -> LabelResult:
        """Print using CUPS on Linux."""
        try:
            # Use lp command
            cmd = ["lp", "-d", self._printer_name, str(png_path)]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self._logger.success("LabelGenerator", "Print job sent via CUPS")
                return LabelResult(
                    status=LabelStatus.SUCCESS,
                    message="Print job sent successfully",
                    png_path=png_path
                )
            else:
                # Check if printer exists
                if "Unknown" in result.stderr or "not found" in result.stderr.lower():
                    return LabelResult(
                        status=LabelStatus.PRINTER_NOT_FOUND,
                        message=f"Printer not found: {self._printer_name}",
                        png_path=png_path
                    )
                
                msg = f"Print error: {result.stderr}"
                self._logger.error("LabelGenerator", msg)
                return LabelResult(
                    status=LabelStatus.PRINT_ERROR,
                    message=msg,
                    png_path=png_path
                )
        
        except FileNotFoundError:
            return LabelResult(
                status=LabelStatus.PRINT_ERROR,
                message="CUPS (lp command) not found. Install cups.",
                png_path=png_path
            )
        except Exception as e:
            return LabelResult(
                status=LabelStatus.PRINT_ERROR,
                message=f"Print error: {e}",
                png_path=png_path
            )
    
    def generate_and_print(
        self,
        serial_number: str,
        region: str,
        output_path: Optional[str] = None
    ) -> LabelResult:
        """
        Generate label and print in one operation.
        
        Args:
            serial_number: Device serial number
            region: Region code
            output_path: Optional path to save PNG
        
        Returns:
            LabelResult with final status
        """
        # Generate label
        result = self.generate_label(serial_number, region, output_path)
        if not result.success:
            return result
        
        # Print label
        return self.print_label(str(result.png_path))
    
    def list_printers(self) -> list[str]:
        """
        Get list of available system printers.
        
        Returns:
            List of printer names
        """
        if sys.platform == "win32":
            return self._list_printers_windows()
        else:
            return self._list_printers_linux()
    
    def _list_printers_windows(self) -> list[str]:
        """List printers on Windows."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
        except:
            pass
        return []
    
    def _list_printers_linux(self) -> list[str]:
        """List printers on Linux via CUPS."""
        try:
            result = subprocess.run(
                ["lpstat", "-p"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                printers = []
                for line in result.stdout.split('\n'):
                    if line.startswith('printer '):
                        parts = line.split()
                        if len(parts) >= 2:
                            printers.append(parts[1])
                return printers
        except:
            pass
        return []