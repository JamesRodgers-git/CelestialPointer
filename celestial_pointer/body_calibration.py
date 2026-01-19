"""
Body calibration module for aligning base rotation with IMU magnetometer.
"""

import os
import math
import time
from .config import BODY_CALIBRATION_OFFSET, BODY_CALIBRATION_FILE
from .motor_controller import MotorController
from .imu_controller import IMUController


class BodyCalibrationController:
    """Handles body calibration to align base rotation with IMU magnetometer."""
    
    def __init__(self, motor_controller, imu_controller):
        """
        Initialize body calibration controller.
        
        Args:
            motor_controller: MotorController instance
            imu_controller: IMUController instance
        """
        self.motor_controller = motor_controller
        self.imu_controller = imu_controller
        self.offset = self._load_calibration()
    
    def _load_calibration(self):
        """Load body calibration offset from file."""
        if os.path.exists(BODY_CALIBRATION_FILE):
            try:
                with open(BODY_CALIBRATION_FILE, 'r') as f:
                    offset = float(f.read().strip())
                print(f"Loaded body calibration offset: {offset:.2f} degrees")
                return offset
            except Exception as e:
                print(f"Warning: Could not load body calibration: {e}")
                return BODY_CALIBRATION_OFFSET
        return BODY_CALIBRATION_OFFSET
    
    def _save_calibration(self, offset):
        """Save body calibration offset to file."""
        try:
            with open(BODY_CALIBRATION_FILE, 'w') as f:
                f.write(f"{offset:.6f}")
            print(f"Saved body calibration offset: {offset:.2f} degrees")
            return True
        except Exception as e:
            print(f"Error saving body calibration: {e}")
            return False
    
    def calibrate_body(self):
        """
        Calibrate body orientation by aligning laser with north.
        
        The user should point the laser north, then this function will:
        1. Read the IMU magnetometer heading (should be ~0° when pointing north)
        2. Get current motor 1 position
        3. Calculate and save the offset
        
        Returns:
            bool: True if calibration successful, False otherwise
        """
        print("\n" + "=" * 60)
        print("BODY CALIBRATION")
        print("=" * 60)
        print("\nThis calibration aligns the base rotation (Motor 1) with the IMU magnetometer.")
        print("The offset will be used to correctly calculate azimuth for pointing.")
        print("\nInstructions:")
        print("1. Point the laser directly north (magnetic north)")
        print("2. Make sure the device is level")
        print("3. The IMU will read the magnetometer heading")
        print("4. The current motor position will be recorded")
        print("5. An offset will be calculated and saved")
        print("\n" + "-" * 60)
        
        # Test magnetometer first
        print("\nTesting magnetometer...")
        if not self.imu_controller.test_magnetometer():
            print("\n⚠ WARNING: Magnetometer test failed!")
            print("Body calibration may not work correctly.")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                return False
        
        input("\nWhen the laser is pointing north, press Enter to continue...")
        
        # Take multiple readings for accuracy
        print("\nTaking readings...")
        headings = []
        for i in range(10):
            heading = self.imu_controller.get_heading()
            headings.append(heading)
            print(f"  Reading {i+1}/10: Heading = {heading:.2f}°")
            time.sleep(0.1)
        
        # Check if all readings are zero (indicates magnetometer not working)
        if all(h == 0.0 for h in headings):
            print("\n⚠ WARNING: All magnetometer readings are 0.0°")
            print("This suggests the magnetometer is not being read correctly.")
            print("Please check:")
            print("  1. IMU is properly connected (SCL/SDA pins)")
            print("  2. IMU library supports magnetometer (MPU9250/GY9250)")
            print("  3. IMU has been calibrated")
            response = input("\nContinue anyway? (y/N): ")
            if response.lower() != 'y':
                return False
        
        # Calculate average heading
        avg_heading = sum(headings) / len(headings)
        
        # Get current motor 1 angle
        motor1_angle = self.imu_controller.get_heading()
        
        # Calculate offset
        # When laser points north (0° azimuth), motor should be at position where:
        # motor_angle - offset = imu_heading
        # So: offset = motor_angle - imu_heading
        # But we want: when imu_heading = 0 (north), motor_angle should be 0
        # So: offset = motor_angle - avg_heading
        offset = motor1_angle - avg_heading
        
        # Normalize offset to -180 to 180
        while offset > 180:
            offset -= 360
        while offset < -180:
            offset += 360
        
        print(f"\nCalibration Results:")
        print(f"  Average IMU heading: {avg_heading:.2f}°")
        print(f"  Current motor 1 angle: {motor1_angle:.2f}°")
        print(f"  Calculated offset: {offset:.2f}°")
        print(f"\nThis means: motor_angle = imu_heading + {offset:.2f}°")
        
        # Save calibration
        if self._save_calibration(offset):
            self.offset = offset
            print("\n✓ Body calibration saved successfully!")
            return True
        else:
            print("\n✗ Failed to save body calibration")
            return False
    
    def get_offset(self):
        """Get the current body calibration offset."""
        return self.offset
    
    def apply_offset(self, imu_heading):
        """
        Apply calibration offset to IMU heading to get motor angle.
        
        Args:
            imu_heading: IMU magnetometer heading in degrees
            
        Returns:
            float: Motor 1 angle in degrees
        """
        motor_angle = imu_heading + self.offset
        # Normalize to 0-360
        while motor_angle < 0:
            motor_angle += 360
        while motor_angle >= 360:
            motor_angle -= 360
        return motor_angle

