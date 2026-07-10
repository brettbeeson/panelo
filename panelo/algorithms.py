"""Packing algorithms for panel optimization."""

from abc import ABC, abstractmethod
from typing import List
from panelo.models import Panel, Sheet


class Packer(ABC):
    """Abstract base class for packing algorithms."""
    
    @abstractmethod
    def pack(
        self,
        panels: List[Panel],
        sheet_width: float,
        sheet_height: float,
        kerf: float = 0.0,
    ) -> List[Sheet]:
        """Pack panels onto sheets.
        
        Args:
            panels: List of panels to pack
            sheet_width: Width of each sheet in millimeters
            sheet_height: Height of each sheet in millimeters
            
        Returns:
            List of sheets with panels positioned on them
        """
        pass


class GuillotineAlgorithm(Packer):
    """Guillotine cut algorithm - cuts go completely across the sheet.
    
    This algorithm subdivides the sheet into free rectangles after each
    placement, using only cuts that go all the way across (like a guillotine).
    Good for manual cutting workflows.
    """
    
    def pack(
        self,
        panels: List[Panel],
        sheet_width: float,
        sheet_height: float,
        kerf: float = 0.0,
    ) -> List[Sheet]:
        """Pack panels using guillotine cut algorithm.
        
        Args:
            panels: List of panels to pack
            sheet_width: Width of each sheet in millimeters
            sheet_height: Height of each sheet in millimeters
            
        Returns:
            List of sheets with panels positioned on them
        """
        if not panels:
            return []
        
        # Sort panels by area (largest first)
        sorted_panels = sorted(panels, key=lambda p: p.width * p.height, reverse=True)
        sheets: List[Sheet] = []
        free_rects: List[List[tuple]] = []  # Free rectangles for each sheet: [(x, y, w, h), ...]
        
        for panel in sorted_panels:
            placed = False
            
            # Try to place on existing sheets
            for i, sheet in enumerate(sheets):
                result = self._find_best_rect(panel, free_rects[i], kerf)
                if result:
                    rect_idx, x, y, rotated = result
                    placed_panel = Panel(panel.width, panel.height, x, y, rotated, label=panel.label)
                    sheet.add_panel(placed_panel)
                    
                    # Split the used rectangle with guillotine cut
                    self._split_rect(free_rects[i], rect_idx, placed_panel, kerf)
                    placed = True
                    break
            
            # Create new sheet if needed
            if not placed:
                new_sheet = Sheet(sheet_width, sheet_height)
                new_free_rects = [(0, 0, sheet_width, sheet_height)]
                
                result = self._find_best_rect(panel, new_free_rects, kerf)
                if result:
                    rect_idx, x, y, rotated = result
                    placed_panel = Panel(panel.width, panel.height, x, y, rotated, label=panel.label)
                    new_sheet.add_panel(placed_panel)
                    
                    self._split_rect(new_free_rects, rect_idx, placed_panel, kerf)
                    sheets.append(new_sheet)
                    free_rects.append(new_free_rects)
                else:
                    raise ValueError(f"Panel {panel.width}×{panel.height} is too large for sheet {sheet_width}×{sheet_height}")
        
        return sheets
    
    def _find_best_rect(self, panel: Panel, rects: List[tuple], kerf: float) -> tuple:
        """Find best free rectangle for panel.
        
        Args:
            panel: Panel to place
            rects: List of free rectangles (x, y, w, h)
            
        Returns:
            Tuple of (rect_index, x, y, rotated) or None if no fit
        """
        best_idx = None
        best_x = None
        best_y = None
        best_rotated = False
        best_area_diff = float('inf')
        
        for i, (x, y, w, h) in enumerate(rects):
            normal_w = panel.width + kerf
            normal_h = panel.height + kerf
            rotated_w = panel.height + kerf
            rotated_h = panel.width + kerf

            # Try normal orientation
            if normal_w <= w and normal_h <= h:
                area_diff = (w * h) - (normal_w * normal_h)
                if area_diff < best_area_diff:
                    best_idx = i
                    best_x = x
                    best_y = y
                    best_rotated = False
                    best_area_diff = area_diff
            
            # Try rotated orientation
            if rotated_w <= w and rotated_h <= h:
                area_diff = (w * h) - (rotated_w * rotated_h)
                if area_diff < best_area_diff:
                    best_idx = i
                    best_x = x
                    best_y = y
                    best_rotated = True
                    best_area_diff = area_diff
        
        if best_idx is not None:
            return (best_idx, best_x, best_y, best_rotated)
        return None
    
    def _split_rect(self, rects: List[tuple], rect_idx: int, panel: Panel, kerf: float) -> None:
        """Split a rectangle after placing a panel using guillotine cut.
        
        Args:
            rects: List of free rectangles
            rect_idx: Index of rectangle to split
            panel: Panel that was placed
        """
        x, y, w, h = rects[rect_idx]
        panel_w = (panel.height if panel.rotated else panel.width) + kerf
        panel_h = (panel.width if panel.rotated else panel.height) + kerf
        
        # Remove the used rectangle
        rects.pop(rect_idx)
        
        # Create new free rectangles using guillotine cuts
        # Right rectangle
        if panel_w < w:
            rects.append((x + panel_w, y, w - panel_w, h))
        
        # Top rectangle
        if panel_h < h:
            rects.append((x, y + panel_h, panel_w, h - panel_h))


class MaxRectAlgorithm(Packer):
    """Maximal rectangles algorithm - tracks all free rectangles.
    
    This algorithm maintains a list of all maximal free rectangles and
    uses heuristics to choose the best placement for each panel.
    Provides the most optimal packing but may create complex layouts.
    """
    
    def pack(
        self,
        panels: List[Panel],
        sheet_width: float,
        sheet_height: float,
        kerf: float = 0.0,
    ) -> List[Sheet]:
        """Pack panels using maximal rectangles algorithm.
        
        Args:
            panels: List of panels to pack
            sheet_width: Width of each sheet in millimeters
            sheet_height: Height of each sheet in millimeters
            
        Returns:
            List of sheets with panels positioned on them
        """
        if not panels:
            return []
        
        # Sort panels by area (largest first)
        sorted_panels = sorted(panels, key=lambda p: p.width * p.height, reverse=True)
        sheets: List[Sheet] = []
        free_rects: List[List[tuple]] = []  # Free rectangles for each sheet
        
        for panel in sorted_panels:
            placed = False
            
            # Try to place on existing sheets
            for i, sheet in enumerate(sheets):
                result = self._find_best_rect_bssf(panel, free_rects[i], kerf)
                if result:
                    rect_idx, x, y, rotated = result
                    placed_panel = Panel(panel.width, panel.height, x, y, rotated, label=panel.label)
                    sheet.add_panel(placed_panel)
                    
                    # Update free rectangles
                    self._place_rect(free_rects[i], placed_panel, kerf)
                    placed = True
                    break
            
            # Create new sheet if needed
            if not placed:
                new_sheet = Sheet(sheet_width, sheet_height)
                new_free_rects = [(0, 0, sheet_width, sheet_height)]
                
                result = self._find_best_rect_bssf(panel, new_free_rects, kerf)
                if result:
                    rect_idx, x, y, rotated = result
                    placed_panel = Panel(panel.width, panel.height, x, y, rotated, label=panel.label)
                    new_sheet.add_panel(placed_panel)
                    
                    self._place_rect(new_free_rects, placed_panel, kerf)
                    sheets.append(new_sheet)
                    free_rects.append(new_free_rects)
                else:
                    raise ValueError(f"Panel {panel.width}×{panel.height} is too large for sheet {sheet_width}×{sheet_height}")
        
        return sheets
    
    def _find_best_rect_bssf(self, panel: Panel, rects: List[tuple], kerf: float) -> tuple:
        """Find best free rectangle using Best Short Side Fit heuristic.
        
        Args:
            panel: Panel to place
            rects: List of free rectangles (x, y, w, h)
            
        Returns:
            Tuple of (rect_index, x, y, rotated) or None if no fit
        """
        best_idx = None
        best_x = None
        best_y = None
        best_rotated = False
        best_short_side = float('inf')
        
        for i, (x, y, w, h) in enumerate(rects):
            normal_w = panel.width + kerf
            normal_h = panel.height + kerf
            rotated_w = panel.height + kerf
            rotated_h = panel.width + kerf

            # Try normal orientation
            if normal_w <= w and normal_h <= h:
                leftover_x = w - normal_w
                leftover_y = h - normal_h
                short_side = min(leftover_x, leftover_y)
                
                if short_side < best_short_side:
                    best_idx = i
                    best_x = x
                    best_y = y
                    best_rotated = False
                    best_short_side = short_side
            
            # Try rotated orientation
            if rotated_w <= w and rotated_h <= h:
                leftover_x = w - rotated_w
                leftover_y = h - rotated_h
                short_side = min(leftover_x, leftover_y)
                
                if short_side < best_short_side:
                    best_idx = i
                    best_x = x
                    best_y = y
                    best_rotated = True
                    best_short_side = short_side
        
        if best_idx is not None:
            return (best_idx, best_x, best_y, best_rotated)
        return None
    
    def _place_rect(self, rects: List[tuple], panel: Panel, kerf: float) -> None:
        """Update free rectangles after placing a panel.
        
        Args:
            rects: List of free rectangles
            panel: Panel that was placed
        """
        panel_w = (panel.height if panel.rotated else panel.width) + kerf
        panel_h = (panel.width if panel.rotated else panel.height) + kerf
        
        new_rects = []
        
        for x, y, w, h in rects:
            # Check if this rect intersects with the placed panel
            if self._intersects(x, y, w, h, panel.x, panel.y, panel_w, panel_h):
                # Split the rectangle
                # Left
                if panel.x > x:
                    new_rects.append((x, y, panel.x - x, h))
                # Right
                if panel.x + panel_w < x + w:
                    new_rects.append((panel.x + panel_w, y, x + w - panel.x - panel_w, h))
                # Bottom
                if panel.y > y:
                    new_rects.append((x, y, w, panel.y - y))
                # Top
                if panel.y + panel_h < y + h:
                    new_rects.append((x, panel.y + panel_h, w, y + h - panel.y - panel_h))
            else:
                # Keep rect as is
                new_rects.append((x, y, w, h))
        
        # Remove redundant rectangles (contained within others)
        rects.clear()
        for rect in new_rects:
            if not self._is_contained(rect, new_rects):
                rects.append(rect)
    
    def _intersects(self, x1: float, y1: float, w1: float, h1: float,
                    x2: float, y2: float, w2: float, h2: float) -> bool:
        """Check if two rectangles intersect.
        
        Args:
            x1, y1, w1, h1: First rectangle
            x2, y2, w2, h2: Second rectangle
            
        Returns:
            True if rectangles intersect
        """
        return not (x1 + w1 <= x2 or x2 + w2 <= x1 or 
                   y1 + h1 <= y2 or y2 + h2 <= y1)
    
    def _is_contained(self, rect: tuple, rects: List[tuple]) -> bool:
        """Check if rectangle is contained within another.
        
        Args:
            rect: Rectangle to check (x, y, w, h)
            rects: List of rectangles
            
        Returns:
            True if rect is contained in another rect
        """
        x, y, w, h = rect
        
        for rx, ry, rw, rh in rects:
            if (rx, ry, rw, rh) == (x, y, w, h):
                continue
            
            if (rx <= x and ry <= y and 
                rx + rw >= x + w and ry + rh >= y + h):
                return True
        
        return False


class FirstFitAlgorithm(Packer):
    """First fit decreasing algorithm - simple greedy approach.
    
    Sorts panels by size (largest first) and places each panel on the
    first sheet where it fits, creating new sheets as needed.
    Simplest algorithm but may waste more material.
    """
    
    def pack(
        self,
        panels: List[Panel],
        sheet_width: float,
        sheet_height: float,
        kerf: float = 0.0,
    ) -> List[Sheet]:
        """Pack panels using first fit decreasing algorithm.
        
        Args:
            panels: List of panels to pack
            sheet_width: Width of each sheet in millimeters
            sheet_height: Height of each sheet in millimeters
            
        Returns:
            List of sheets with panels positioned on them
        """
        if not panels:
            return []
        
        # Sort panels by area (largest first)
        sorted_panels = sorted(panels, key=lambda p: p.width * p.height, reverse=True)
        sheets: List[Sheet] = []
        
        for panel in sorted_panels:
            placed = False
            
            # Try to place on existing sheets
            for sheet in sheets:
                if self._try_place_panel(panel, sheet, sheet_width, sheet_height, kerf):
                    placed = True
                    break
            
            # Create new sheet if needed
            if not placed:
                new_sheet = Sheet(sheet_width, sheet_height)
                if self._try_place_panel(panel, new_sheet, sheet_width, sheet_height, kerf):
                    sheets.append(new_sheet)
                else:
                    # Panel too large for sheet
                    raise ValueError(f"Panel {panel.width}×{panel.height} is too large for sheet {sheet_width}×{sheet_height}")
        
        return sheets
    
    def _try_place_panel(
        self,
        panel: Panel,
        sheet: Sheet,
        sheet_width: float,
        sheet_height: float,
        kerf: float,
    ) -> bool:
        """Try to place a panel on a sheet.
        
        Args:
            panel: Panel to place
            sheet: Sheet to place on
            sheet_width: Width of sheet
            sheet_height: Height of sheet
            
        Returns:
            True if panel was placed, False otherwise
        """
        step = max(1, int(10 if kerf == 0 else min(10, kerf)))

        # Try to find a position for the panel
        for y in range(0, int(sheet_height), step):  # Grid search for candidate positions
            for x in range(0, int(sheet_width), step):
                # Try normal orientation
                if self._can_place_at(panel, x, y, sheet, sheet_width, sheet_height, rotated=False, kerf=kerf):
                    placed_panel = Panel(panel.width, panel.height, x, y, rotated=False, label=panel.label)
                    sheet.add_panel(placed_panel)
                    return True
                
                # Try rotated orientation
                if self._can_place_at(panel, x, y, sheet, sheet_width, sheet_height, rotated=True, kerf=kerf):
                    placed_panel = Panel(panel.width, panel.height, x, y, rotated=True, label=panel.label)
                    sheet.add_panel(placed_panel)
                    return True
        
        return False
    
    def _can_place_at(
        self,
        panel: Panel,
        x: float,
        y: float,
        sheet: Sheet,
        sheet_width: float,
        sheet_height: float,
        rotated: bool,
        kerf: float,
    ) -> bool:
        """Check if panel can be placed at given position.
        
        Args:
            panel: Panel to place
            x: X coordinate
            y: Y coordinate
            sheet: Sheet to place on
            sheet_width: Width of sheet
            sheet_height: Height of sheet
            rotated: Whether to rotate panel 90°
            
        Returns:
            True if panel can be placed, False otherwise
        """
        w = (panel.height if rotated else panel.width) + kerf
        h = (panel.width if rotated else panel.height) + kerf
        
        # Check if panel fits on sheet
        if x + w > sheet_width or y + h > sheet_height:
            return False
        
        # Check for overlaps with existing panels
        for existing in sheet.panels:
            ex_w = (existing.height if existing.rotated else existing.width) + kerf
            ex_h = (existing.width if existing.rotated else existing.height) + kerf
            
            # Check rectangle overlap
            if not (x + w <= existing.x or 
                    x >= existing.x + ex_w or
                    y + h <= existing.y or 
                    y >= existing.y + ex_h):
                return False
        
        return True
