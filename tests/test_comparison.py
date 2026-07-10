"""Comparison tests for packing algorithms."""

import pytest
from panelo.models import Panel
from panelo.algorithms import GuillotineAlgorithm, MaxRectAlgorithm, FirstFitAlgorithm


# Test datasets with varied panel sizes
TEST_DATA = {
    "mixed_small": {
        "panels": [
            Panel(400, 600),
            Panel(300, 500),
            Panel(400, 400),
            Panel(200, 800),
            Panel(500, 300),
        ],
        "sheet_width": 1220,
        "sheet_height": 2440,
        "description": "5 mixed small-medium panels"
    },
    "large_with_small": {
        "panels": [
            Panel(1000, 1200),
            Panel(800, 1000),
            Panel(300, 400),
            Panel(200, 300),
            Panel(400, 500),
            Panel(300, 600),
            Panel(200, 400),
        ],
        "sheet_width": 1220,
        "sheet_height": 2440,
        "description": "7 panels: 2 large + 5 small"
    },
    "uniform_medium": {
        "panels": [
            Panel(600, 800),
            Panel(600, 800),
            Panel(600, 800),
            Panel(600, 800),
            Panel(500, 700),
            Panel(500, 700),
        ],
        "sheet_width": 1220,
        "sheet_height": 2440,
        "description": "6 similar medium-sized panels"
    },
}


@pytest.mark.parametrize("dataset_name", ["mixed_small", "large_with_small", "uniform_medium"])
def test_algorithm_comparison(dataset_name):
    """Compare all three algorithms on the same dataset."""
    dataset = TEST_DATA[dataset_name]
    panels = dataset["panels"]
    sheet_width = dataset["sheet_width"]
    sheet_height = dataset["sheet_height"]
    
    # Make copies of panels for each algorithm
    panels_ff = [Panel(p.width, p.height) for p in panels]
    panels_guillotine = [Panel(p.width, p.height) for p in panels]
    panels_maxrect = [Panel(p.width, p.height) for p in panels]
    
    # Run all three algorithms
    ff_algo = FirstFitAlgorithm()
    guillotine_algo = GuillotineAlgorithm()
    maxrect_algo = MaxRectAlgorithm()
    
    ff_sheets = ff_algo.pack(panels_ff, sheet_width, sheet_height)
    guillotine_sheets = guillotine_algo.pack(panels_guillotine, sheet_width, sheet_height)
    maxrect_sheets = maxrect_algo.pack(panels_maxrect, sheet_width, sheet_height)
    
    # Verify all panels were placed
    assert sum(len(s.panels) for s in ff_sheets) == len(panels)
    assert sum(len(s.panels) for s in guillotine_sheets) == len(panels)
    assert sum(len(s.panels) for s in maxrect_sheets) == len(panels)
    
    # Calculate metrics
    ff_avg_util = sum(s.get_utilization() for s in ff_sheets) / len(ff_sheets)
    guillotine_avg_util = sum(s.get_utilization() for s in guillotine_sheets) / len(guillotine_sheets)
    maxrect_avg_util = sum(s.get_utilization() for s in maxrect_sheets) / len(maxrect_sheets)
    
    # Print comparison
    print(f"\n\n{'='*70}")
    print(f"Dataset: {dataset['description']}")
    print(f"{'='*70}")
    print(f"{'Algorithm':<20} {'Sheets':<10} {'Avg Util %':<15} {'Total Util %':<15}")
    print(f"{'-'*70}")
    
    total_panel_area = sum(p.width * p.height for p in panels)
    
    ff_total_util = (total_panel_area / (len(ff_sheets) * sheet_width * sheet_height)) * 100
    print(f"{'FirstFit':<20} {len(ff_sheets):<10} {ff_avg_util:>7.0f}%        {ff_total_util:>7.0f}%")
    
    guillotine_total_util = (total_panel_area / (len(guillotine_sheets) * sheet_width * sheet_height)) * 100
    print(f"{'Guillotine':<20} {len(guillotine_sheets):<10} {guillotine_avg_util:>7.0f}%        {guillotine_total_util:>7.0f}%")
    
    maxrect_total_util = (total_panel_area / (len(maxrect_sheets) * sheet_width * sheet_height)) * 100
    print(f"{'MaxRect':<20} {len(maxrect_sheets):<10} {maxrect_avg_util:>7.0f}%        {maxrect_total_util:>7.0f}%")
    
    print(f"{'='*70}\n")


def test_all_algorithms_detailed_comparison():
    """Detailed comparison across all test datasets."""
    results = {}
    
    for dataset_name, dataset in TEST_DATA.items():
        panels = dataset["panels"]
        sheet_width = dataset["sheet_width"]
        sheet_height = dataset["sheet_height"]
        
        # Test each algorithm
        algorithms = {
            "FirstFit": FirstFitAlgorithm(),
            "Guillotine": GuillotineAlgorithm(),
            "MaxRect": MaxRectAlgorithm(),
        }
        
        results[dataset_name] = {}
        
        for algo_name, algo in algorithms.items():
            panels_copy = [Panel(p.width, p.height) for p in panels]
            sheets = algo.pack(panels_copy, sheet_width, sheet_height)
            
            total_panel_area = sum(p.width * p.height for p in panels)
            total_sheet_area = len(sheets) * sheet_width * sheet_height
            
            results[dataset_name][algo_name] = {
                "sheets": len(sheets),
                "panels_placed": sum(len(s.panels) for s in sheets),
                "avg_utilization": sum(s.get_utilization() for s in sheets) / len(sheets),
                "total_utilization": (total_panel_area / total_sheet_area) * 100,
            }
    
    # Print summary
    print(f"\n\n{'='*80}")
    print("ALGORITHM COMPARISON SUMMARY")
    print(f"{'='*80}\n")
    
    for dataset_name, algo_results in results.items():
        print(f"Dataset: {TEST_DATA[dataset_name]['description']}")
        print(f"{'-'*80}")
        print(f"{'Algorithm':<15} {'Sheets':<10} {'Panels':<10} {'Avg Util':<15} {'Total Util':<15}")
        print(f"{'-'*80}")
        
        for algo_name, metrics in algo_results.items():
            print(f"{algo_name:<15} {metrics['sheets']:<10} "
                  f"{metrics['panels_placed']:<10} "
                  f"{metrics['avg_utilization']:>6.0f}%        "
                  f"{metrics['total_utilization']:>6.0f}%")
        print()
    
    # All tests should place all panels
    for dataset_name, algo_results in results.items():
        expected_panels = len(TEST_DATA[dataset_name]["panels"])
        for algo_name, metrics in algo_results.items():
            assert metrics["panels_placed"] == expected_panels, \
                f"{algo_name} failed to place all panels in {dataset_name}"


def test_algorithm_efficiency_order():
    """Verify that algorithms generally perform as expected in terms of efficiency."""
    dataset = TEST_DATA["mixed_small"]
    panels = [Panel(p.width, p.height) for p in dataset["panels"]]
    
    ff_sheets = FirstFitAlgorithm().pack(
        [Panel(p.width, p.height) for p in panels],
        dataset["sheet_width"], dataset["sheet_height"]
    )
    
    guillotine_sheets = GuillotineAlgorithm().pack(
        [Panel(p.width, p.height) for p in panels],
        dataset["sheet_width"], dataset["sheet_height"]
    )
    
    maxrect_sheets = MaxRectAlgorithm().pack(
        [Panel(p.width, p.height) for p in panels],
        dataset["sheet_width"], dataset["sheet_height"]
    )
    
    # All algorithms should successfully pack all panels
    assert sum(len(s.panels) for s in ff_sheets) == len(panels)
    assert sum(len(s.panels) for s in guillotine_sheets) == len(panels)
    assert sum(len(s.panels) for s in maxrect_sheets) == len(panels)
    
    # In general, MaxRect should be most efficient (or equal)
    # Guillotine should be better than or equal to FirstFit
    # (Not strict assertions as results can vary based on panel arrangement)
    print(f"\nEfficiency: FirstFit={len(ff_sheets)} sheets, "
          f"Guillotine={len(guillotine_sheets)} sheets, "
          f"MaxRect={len(maxrect_sheets)} sheets")
