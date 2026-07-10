"""Tests for panelo packing algorithms."""

import pytest
from panelo.models import Panel, Sheet
from panelo.algorithms import Packer, GuillotineAlgorithm, MaxRectAlgorithm, FirstFitAlgorithm

