"""
Tests for laser controller.
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from celestial_pointer.laser_controller import LaserController
from celestial_pointer.config import LASER_MAX_ELEVATION, LASER_MIN_ELEVATION


class TestLaserController(unittest.TestCase):
    """Test cases for LaserController."""
    
    @patch('celestial_pointer.laser_controller.GPIO')
    def setUp(self, mock_gpio):
        """Set up test fixtures."""
        self.controller = LaserController()
    
    def test_initialization(self):
        """Test laser controller initialization."""
        self.assertFalse(self.controller.is_on())
        self.assertEqual(self.controller.min_elevation, LASER_MIN_ELEVATION)
        self.assertEqual(self.controller.max_elevation, LASER_MAX_ELEVATION)
    
    def test_turn_on_off(self):
        """Test turning laser on and off."""
        self.controller.turn_on()
        self.assertTrue(self.controller.is_on())
        
        self.controller.turn_off()
        self.assertFalse(self.controller.is_on())
    
    def test_toggle(self):
        """Test laser toggle."""
        initial_state = self.controller.is_on()
        self.controller.toggle()
        self.assertNotEqual(self.controller.is_on(), initial_state)
        
        self.controller.toggle()
        self.assertEqual(self.controller.is_on(), initial_state)
    
    def test_elevation_range_check(self):
        """Test elevation range checking."""
        # Valid elevation
        is_valid, clamped = self.controller.check_elevation_range(45.0)
        self.assertTrue(is_valid)
        self.assertEqual(clamped, 45.0)
        
        # Too high
        is_valid, clamped = self.controller.check_elevation_range(100.0)
        self.assertFalse(is_valid)
        self.assertEqual(clamped, LASER_MAX_ELEVATION)
        
        # Too low
        is_valid, clamped = self.controller.check_elevation_range(-20.0)
        self.assertFalse(is_valid)
        self.assertEqual(clamped, LASER_MIN_ELEVATION)
    
    @patch('time.sleep')
    def test_flash(self, mock_sleep):
        """Test laser flashing."""
        self.controller.flash(count=2)
        # Should have toggled on/off multiple times
        self.assertFalse(self.controller.is_on())  # Ends off if started off


if __name__ == '__main__':
    unittest.main()


