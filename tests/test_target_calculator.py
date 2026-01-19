"""
Tests for target calculator.
"""

import unittest
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from celestial_pointer.target_calculator import TargetCalculator


class TestTargetCalculator(unittest.TestCase):
    """Test cases for TargetCalculator."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use test coordinates (San Francisco)
        self.calculator = TargetCalculator(latitude=37.7749, longitude=-122.4194, altitude=0.0)
    
    def test_initialization(self):
        """Test calculator initialization."""
        self.assertIsNotNone(self.calculator.latitude)
        self.assertIsNotNone(self.calculator.longitude)
        self.assertEqual(self.calculator.altitude, 0.0)
    
    def test_star_position(self):
        """Test star position calculation."""
        # Test known star
        position = self.calculator.get_star_position("Sirius")
        self.assertIsNotNone(position)
        azimuth, elevation = position
        self.assertIsInstance(azimuth, (int, float))
        self.assertIsInstance(elevation, (int, float))
        self.assertTrue(0 <= azimuth <= 360)
        self.assertTrue(-90 <= elevation <= 90)
    
    def test_star_not_found(self):
        """Test handling of unknown star."""
        position = self.calculator.get_star_position("NonexistentStar")
        self.assertIsNone(position)
    
    def test_azimuth_elevation_calculation(self):
        """Test azimuth/elevation calculation."""
        # Test with known coordinates
        azimuth, elevation = self.calculator.calculate_azimuth_elevation(
            target_ra=6.752,  # Sirius RA in hours
            target_dec=-16.716  # Sirius Dec in degrees
        )
        self.assertIsInstance(azimuth, (int, float))
        self.assertIsInstance(elevation, (int, float))
        self.assertTrue(0 <= azimuth <= 360)
        self.assertTrue(-90 <= elevation <= 90)
    
    def test_julian_day(self):
        """Test Julian Day calculation."""
        test_date = datetime(2024, 1, 1, 12, 0, 0)
        jd = self.calculator._julian_day(test_date)
        self.assertIsInstance(jd, float)
        self.assertGreater(jd, 2400000)  # Should be a reasonable JD


if __name__ == '__main__':
    unittest.main()


