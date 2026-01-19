"""
Tests for calibration controller.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from celestial_pointer.calibration import CalibrationController
from celestial_pointer.motor_controller import MotorController
from celestial_pointer.laser_controller import LaserController


class TestCalibrationController(unittest.TestCase):
    """Test cases for CalibrationController."""
    
    @patch('celestial_pointer.calibration.GPIO')
    @patch('celestial_pointer.motor_controller.RPi.GPIO')
    @patch('celestial_pointer.motor_controller.RpiMotorLib')
    @patch('celestial_pointer.laser_controller.GPIO')
    def setUp(self, mock_laser_gpio, mock_motor_rpimotor, mock_motor_gpio, mock_gpio):
        """Set up test fixtures."""
        motor_controller = MotorController()
        laser_controller = LaserController()
        self.controller = CalibrationController(motor_controller, laser_controller)
    
    def test_initialization(self):
        """Test calibration controller initialization."""
        self.assertFalse(self.controller.calibrated)
        self.assertEqual(self.controller.calibration_position, 0)
    
    @patch('time.sleep')
    def test_button_detection(self, mock_sleep):
        """Test button press detection."""
        # Mock GPIO input
        with patch.object(self.controller, 'is_button_pressed', return_value=True):
            self.assertTrue(self.controller.is_button_pressed())
        
        with patch.object(self.controller, 'is_button_pressed', return_value=False):
            self.assertFalse(self.controller.is_button_pressed())
    
    @patch('time.sleep')
    def test_calibration_success(self, mock_sleep):
        """Test successful calibration."""
        # Mock button to be pressed after a few steps
        button_press_count = [0]
        
        def mock_button():
            button_press_count[0] += 1
            return button_press_count[0] > 5
        
        with patch.object(self.controller, 'is_button_pressed', side_effect=mock_button):
            with patch.object(self.controller.motor_controller, 'move_motor2'):
                with patch.object(self.controller.motor_controller, 'reset_motor2_position'):
                    result = self.controller.calibrate_z_axis(max_steps=100, step_size=1)
                    self.assertTrue(result)
                    self.assertTrue(self.controller.calibrated)


if __name__ == '__main__':
    unittest.main()


