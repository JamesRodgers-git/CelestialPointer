"""
Tests for motor controller.
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from celestial_pointer.motor_controller import MotorController
from celestial_pointer.config import MOTOR1_PINS, MOTOR2_PINS


class TestMotorController(unittest.TestCase):
    """Test cases for MotorController."""
    
    @patch('celestial_pointer.motor_controller.RPi.GPIO')
    @patch('celestial_pointer.motor_controller.RpiMotorLib')
    def setUp(self, mock_rpimotor, mock_gpio):
        """Set up test fixtures."""
        self.controller = MotorController()
    
    def test_initialization(self):
        """Test motor controller initialization."""
        self.assertIsNotNone(self.controller.motor1)
        self.assertIsNotNone(self.controller.motor2)
        self.assertEqual(self.controller.motor1_position, 0)
        self.assertEqual(self.controller.motor2_position, 0)
    
    def test_position_tracking(self):
        """Test position tracking."""
        # Mock motor movement
        with patch.object(self.controller.motor1, 'motor_run'):
            self.controller.move_motor1(100, clockwise=False)
            self.assertEqual(self.controller.get_motor1_position(), 100)
        
        with patch.object(self.controller.motor2, 'motor_run'):
            self.controller.move_motor2(50, clockwise=False)
            self.assertEqual(self.controller.get_motor2_position(), 50)
    
    def test_degree_calculations(self):
        """Test degree-based movements."""
        # Test that degrees are converted to steps correctly
        initial_pos = self.controller.get_motor1_position()
        
        with patch.object(self.controller.motor1, 'motor_run'):
            self.controller.move_motor1_degrees(90.0)
            # Should have moved some steps
            self.assertNotEqual(self.controller.get_motor1_position(), initial_pos)
    
    def test_reset_position(self):
        """Test position reset."""
        self.controller.motor1_position = 100
        self.controller.reset_motor1_position()
        self.assertEqual(self.controller.get_motor1_position(), 0)
        
        self.controller.motor2_position = 50
        self.controller.reset_motor2_position()
        self.assertEqual(self.controller.get_motor2_position(), 0)


if __name__ == '__main__':
    unittest.main()


