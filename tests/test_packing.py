"""Tests for implemented packing algorithms."""

import tempfile

import pytest
from panelo import output
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


def test_guillotine_complex_pack():
    packer = GuillotineAlgorithm()
    panels = [ 
        Panel(190,430),Panel(190,430),Panel(190,430),Panel(190,430),Panel(190,430),Panel(190,430),Panel(190,430),
        Panel(2030,190),Panel(2030,190)
    ]
    sheets = packer.pack(panels,2400,1200)
    # display svg
    tf = tempfile.NamedTemporaryFile(prefix="Panelo",suffix=".svg",delete=False)
    output.to_svg(sheets,tf.file.name)
    print(tf.name)


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


    # With two cuts we CAN fit in 400x3 => 1210 wide
    panels = [Panel(2400, 400), Panel(2400, 400), Panel(2400, 400)]

    packer.pack(panels, sheet_width=2400, sheet_height=1200+10, kerf=5.0)  



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


def test_guillotine_prefers_largest_remaining_rectangle():
    """Guillotine split should preserve the largest useful remainder."""
    packer = GuillotineAlgorithm()

    # Place a panel at the origin inside a 1000x1000 free rectangle.
    # Horizontal-first split keeps a 1000x800 free rectangle (area 800000),
    # while vertical-first would keep at most 800x800 (area 640000).
    # The heuristic should pick the split that maximizes the largest remainder.
    rects = [(0, 0, 1000, 1000)]
    placed = Panel(800, 200, x=0, y=0, rotated=False)
    packer._split_rect(rects, 0, placed, kerf=0)

    # Expect the chosen split to include the full-width top rectangle.
    assert (0, 200, 1000, 800) in rects
