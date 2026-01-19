"""
Calibration module for laser Z-axis using the stop button.
"""

import time
import RPi.GPIO as GPIO
from .config import (
    BUTTON_PIN, CALIBRATION_BUTTON_DEBOUNCE, CALIBRATION_STEP_DELAY,
    CALIBRATION_STEP_TYPE, LASER_CALIBRATION_STEPS
)
from .motor_controller import MotorController
from .laser_controller import LaserController


class CalibrationController:
    """Handles calibration of the laser Z-axis using the stop button."""
    
    def __init__(self, motor_controller, laser_controller):
        """
        Initialize calibration controller.
        
        Args:
            motor_controller: MotorController instance
            laser_controller: LaserController instance
        """
        self.motor_controller = motor_controller
        self.laser_controller = laser_controller
        
        # Setup button pin with pull-up
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Calibration state
        self.calibrated = False
        self.calibration_position = 0  # Steps from home when button is pressed
    
    def is_button_pressed(self):
        """
        Check if calibration button is pressed.
        
        Returns:
            bool: True if button is pressed (LOW due to pull-up)
        """
        return GPIO.input(BUTTON_PIN) == GPIO.LOW
    
    def calibrate_z_axis(self, calibration_steps=100):
        """
        Calibrate the laser Z-axis by moving upward a fixed number of steps.
        
        The laser will move gently upward for the specified number of steps, which
        should be enough to reach the calibration button. After the movement completes,
        this position is set as the calibration point (90 degrees elevation).
        
        Note: The RpiMotorLib library uses 512 steps per motor shaft revolution,
        regardless of step type (full/half/wave). Motor 2 has additional gear
        reduction, so 512 steps = 252 degrees of laser gear rotation.
        
        Args:
            calibration_steps: Number of steps to move upward (default: 180)
            
        Returns:
            bool: True if calibration successful, False otherwise
        """

        if LASER_CALIBRATION_STEPS:
            calibration_steps = LASER_CALIBRATION_STEPS
            
        print("Starting Z-axis calibration...")
        print(f"Moving laser upward {calibration_steps} steps gently to reach calibration position...")
        print("The laser will move until it reaches the button and stops.")
        
        # Use the motor controller's homing function
        success = self.motor_controller.home_motor2(
            laser_controller=self.laser_controller,
            slow_mode=False,  # Normal speed for calibration
            verbose=True
        )
        
        if success:
            self.calibration_position = 0
            self.calibrated = True
            
            print(f"\nCalibration complete! Moved {calibration_steps} steps.")
            print("Laser is now calibrated at maximum upward position (~90 degrees relative to IMU plane).")
            
            return True
        else:
            print("Calibration failed.")
            return False
    
    def is_calibrated(self):
        """Check if calibration has been performed."""
        return self.calibrated
    
    def get_calibration_position(self):
        """Get the calibration position in steps."""
        return self.calibration_position

