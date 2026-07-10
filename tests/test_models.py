"""Tests for panelo models."""

import pytest
from panelo.models import Panel, Sheet


def test_panel_creation():
    """Test creating a panel with basic dimensions."""
    panel = Panel(width=100, height=200)
    
    assert panel.width == 100
    assert panel.height == 200
    assert panel.x == 0
    assert panel.y == 0
    assert panel.rotated is False


def test_panel_with_position():
    """Test creating a panel with position coordinates."""
    panel = Panel(width=100, height=200, x=50, y=75, rotated=True)
    
    assert panel.width == 100
    assert panel.height == 200
    assert panel.x == 50
    assert panel.y == 75
    assert panel.rotated is True


def test_sheet_add_panel():
    """Test adding panels to a sheet."""
    sheet = Sheet(width=1220, height=2440)
    panel1 = Panel(width=100, height=200)
    panel2 = Panel(width=150, height=250)
    
    assert len(sheet.panels) == 0
    
    sheet.add_panel(panel1)
    assert len(sheet.panels) == 1
    
    sheet.add_panel(panel2)
    assert len(sheet.panels) == 2


def test_sheet_utilization():
    """Test sheet utilization calculation."""
    sheet = Sheet(width=1000, height=1000)  # 1,000,000 mm²
    
    # Empty sheet
    assert sheet.get_utilization() == 0.0
    
    # Add panel covering 25% of sheet
    panel1 = Panel(width=500, height=500)  # 250,000 mm²
    sheet.add_panel(panel1)
    assert sheet.get_utilization() == 25.0
    
    # Add another panel covering 10% of sheet
    panel2 = Panel(width=200, height=500)  # 100,000 mm²
    sheet.add_panel(panel2)
    assert sheet.get_utilization() == 35.0
