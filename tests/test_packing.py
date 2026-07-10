"""Tests for implemented packing algorithms."""

import pytest
from panelo.models import Panel, Sheet
from panelo.algorithms import GuillotineAlgorithm, MaxRectAlgorithm, FirstFitAlgorithm


def test_firstfit_simple_pack():
    """Test FirstFitAlgorithm with simple panels."""
    packer = FirstFitAlgorithm()
    panels = [
        Panel(100, 200),
        Panel(150, 100),
        Panel(200, 200),
    ]
    
    sheets = packer.pack(panels, sheet_width=1000, sheet_height=1000)
    
    assert len(sheets) == 1
    assert len(sheets[0].panels) == 3
    assert sheets[0].get_utilization() > 0


def test_guillotine_simple_pack():
    """Test GuillotineAlgorithm with simple panels."""
    packer = GuillotineAlgorithm()
    panels = [
        Panel(100, 200),
        Panel(150, 100),
        Panel(200, 200),
    ]
    
    sheets = packer.pack(panels, sheet_width=1000, sheet_height=1000)
    
    assert len(sheets) == 1
    assert len(sheets[0].panels) == 3
    assert sheets[0].get_utilization() > 0


def test_maxrect_simple_pack():
    """Test MaxRectAlgorithm with simple panels."""
    packer = MaxRectAlgorithm()
    panels = [
        Panel(100, 200),
        Panel(150, 100),
        Panel(200, 200),
    ]
    
    sheets = packer.pack(panels, sheet_width=1000, sheet_height=1000)
    
    assert len(sheets) == 1
    assert len(sheets[0].panels) == 3
    assert sheets[0].get_utilization() > 0


def test_multiple_sheets_needed():
    """Test that multiple sheets are created when needed."""
    packer = GuillotineAlgorithm()
    panels = [
        Panel(800, 800),
        Panel(800, 800),
        Panel(800, 800),
    ]
    
    sheets = packer.pack(panels, sheet_width=1000, sheet_height=1000)
    
    assert len(sheets) >= 3  # Each 800x800 needs its own sheet


def test_panel_too_large():
    """Test error when panel is too large for sheet."""
    packer = GuillotineAlgorithm()
    panels = [Panel(1500, 1000)]
    
    with pytest.raises(ValueError, match="too large for sheet"):
        packer.pack(panels, sheet_width=1000, sheet_height=1000)


def test_empty_panels_list():
    """Test with empty panels list."""
    packer = GuillotineAlgorithm()
    sheets = packer.pack([], sheet_width=1000, sheet_height=1000)
    
    assert len(sheets) == 0


def test_rotation_enabled():
    """Test that panel rotation works."""
    packer = GuillotineAlgorithm()
    # Panel that fits better when rotated
    panels = [Panel(100, 900)]
    
    sheets = packer.pack(panels, sheet_width=1000, sheet_height=200)
    
    assert len(sheets) == 1
    assert len(sheets[0].panels) == 1
    # Should be rotated to fit
    assert sheets[0].panels[0].rotated is True
