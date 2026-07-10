"""Data models for panelo."""

from typing import List


class Panel:
    """Represents a rectangular panel to be cut from a sheet.
    
    Attributes:
        width: Panel width in millimeters
        height: Panel height in millimeters
        x: X-coordinate position on sheet (default: 0)
        y: Y-coordinate position on sheet (default: 0)
        rotated: Whether panel is rotated 90° (default: False)
    """
    
    def __init__(
        self,
        width: float,
        height: float,
        x: float = 0,
        y: float = 0,
        rotated: bool = False,
        label: str = "",
    ):
        """Initialize a panel.
        
        Args:
            width: Panel width in millimeters
            height: Panel height in millimeters
            x: X-coordinate position (default: 0)
            y: Y-coordinate position (default: 0)
            rotated: Whether panel is rotated 90° (default: False)
            label: Optional panel label from input data
        """
        self.width = width
        self.height = height
        self.x = x
        self.y = y
        self.rotated = rotated
        self.label = label
    
    def __repr__(self) -> str:
        rotation = " (rotated)" if self.rotated else ""
        label = f" [{self.label}]" if self.label else ""
        return f"Panel({self.width}×{self.height} at ({self.x},{self.y}){rotation}{label})"


class Sheet:
    """Represents a plywood sheet with panels placed on it.
    
    Attributes:
        width: Sheet width in millimeters
        height: Sheet height in millimeters
        panels: List of panels placed on this sheet
    """
    
    def __init__(self, width: float, height: float):
        """Initialize a sheet.
        
        Args:
            width: Sheet width in millimeters
            height: Sheet height in millimeters
        """
        self.width = width
        self.height = height
        self.panels: List[Panel] = []
    
    def add_panel(self, panel: Panel) -> None:
        """Add a panel to this sheet.
        
        Args:
            panel: Panel to add
        """
        self.panels.append(panel)
    
    def get_utilization(self) -> float:
        """Calculate sheet utilization as percentage.
        
        Returns:
            Percentage of sheet area used by panels (0-100)
        """
        if not self.panels:
            return 0.0
        
        sheet_area = self.width * self.height
        panel_area = sum(p.width * p.height for p in self.panels)
        return (panel_area / sheet_area) * 100
    
    def __repr__(self) -> str:
        util = self.get_utilization()
        return f"Sheet({self.width}×{self.height}, {len(self.panels)} panels, {util:.1f}% utilized)"

