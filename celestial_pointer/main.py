"""
Main application entry point for Celestial Pointer.
"""

import sys
import time
import RPi.GPIO as GPIO
from .config import (
    LASER_DEFAULT_MIN_ELEVATION, API_HOST, API_PORT, LOAD_STAR_CHART,
    USE_MAGNETOMETER_FOR_MOTOR1, USE_DEFAULT_TARGET_ON_STARTUP
)
from .motor_controller import MotorController
from .laser_controller import LaserController
from .imu_controller import IMUController
from .calibration import CalibrationController
from .body_calibration import BodyCalibrationController
from .target_calculator import TargetCalculator
from .api import initialize_api, run_api
import argparse


class CelestialPointer:
    """Main application class."""
    
    def __init__(self, latitude: float, longitude: float, altitude: float = 0.0,
                 min_elevation: float = None):
        """
        Initialize Celestial Pointer.
        
        Args:
            latitude: Observer latitude in degrees
            longitude: Observer longitude in degrees
            altitude: Observer altitude in meters
            min_elevation: Minimum laser elevation in degrees
        """
        print("Initializing Celestial Pointer...")
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Initialize controllers
        self.laser_controller = LaserController(
            min_elevation=min_elevation if min_elevation is not None else LASER_DEFAULT_MIN_ELEVATION
        )
        self.imu_controller = IMUController()
        # Motor controller needs IMU and body calibration for magnetometer-based angle
        # Only pass IMU if magnetometer is enabled
        motor1_imu = self.imu_controller if USE_MAGNETOMETER_FOR_MOTOR1 else None
        self.motor_controller = MotorController(
            imu_controller=motor1_imu,
            body_calibration_controller=None  # Will be set after body_calibration_controller is created
        )
        self.calibration_controller = CalibrationController(
            self.motor_controller,
            self.laser_controller
        )
        self.body_calibration_controller = BodyCalibrationController(
            self.motor_controller,
            self.imu_controller
        )
        # Update motor controller with body calibration reference (only if using magnetometer)
        if USE_MAGNETOMETER_FOR_MOTOR1:
            self.motor_controller.body_calibration_controller = self.body_calibration_controller
        self.target_calculator = TargetCalculator(latitude, longitude, altitude, load_star_chart=LOAD_STAR_CHART)
        
        # Calibration state
        self.calibrated = False
        self.body_calibrated = False
        
        print("Initialization complete.")
    
    def calibrate(self):
        """Perform system calibration."""
        print("\n" + "=" * 60)
        print("CALIBRATION")
        print("=" * 60)
        
        # Calibrate laser Z-axis
        print("\nCalibrating laser Z-axis...")
        
        success = self.calibration_controller.calibrate_z_axis()
        if not success:
            print("ERROR: Calibration failed!")
            return False
        
        self.calibrated = True
        print("\nCalibration complete!")
        return True
    
    def is_calibrated(self):
        """Check if system is calibrated."""
        return self.calibrated
    
    def calibrate_body(self):
        """Perform body calibration (align base rotation with IMU magnetometer)."""
        success = self.body_calibration_controller.calibrate_body()
        if success:
            self.body_calibrated = True
        return success
    
    def is_body_calibrated(self):
        """Check if body calibration has been performed."""
        return self.body_calibrated
    
    def run_api_server(self):
        """Run the API server."""
        # Initialize API with controllers
        initialize_api(
            self.target_calculator,
            self.motor_controller,
            self.laser_controller,
            self.imu_controller,
            self.body_calibration_controller
        )
        
        print(f"\nStarting API server on {API_HOST}:{API_PORT}")
        print("API documentation available at http://localhost:8000/docs")
        
        try:
            run_api()
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.shutdown()
    
    def shutdown(self):
        """Shutdown and cleanup."""
        print("Shutting down Celestial Pointer...")
        
        # Turn off laser
        self.laser_controller.turn_off()
        
        # Cleanup GPIO
        GPIO.cleanup()
        
        print("Shutdown complete.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Celestial Pointer - Laser pointing system")
    parser.add_argument("--latitude", type=float, required=True,
                       help="Observer latitude in degrees")
    parser.add_argument("--longitude", type=float, required=True,
                       help="Observer longitude in degrees")
    parser.add_argument("--altitude", type=float, default=0.0,
                       help="Observer altitude in meters (default: 0)")
    parser.add_argument("--min-elevation", type=float, default=None,
                       help="Minimum laser elevation in degrees (default: -10)")
    parser.add_argument("--calibrate", action="store_true",
                       help="Run calibration before starting API",
                       default=True)
    parser.add_argument("--body-calibrate", action="store_true",
                       help="Run body calibration (align base rotation with IMU magnetometer)")
    parser.add_argument("--calibrate-magnetometer", action="store_true",
                       help="Calibrate magnetometer separately (move device in figure-8 pattern)")
    parser.add_argument("--skip-calibration", action="store_true",
                       help="Skip calibration check (use with caution)")
    parser.add_argument("--test-180", action="store_true",
                       help="Test both motors by rotating exactly 180 degrees")
    
    args = parser.parse_args()

    print("This is the Star Pointer Beta 0.1")
    print("This project points a laser at stars, planets, satellites using a laser controlled by 2 stepper motors and an IMU for outdoor enjoyment with friends and family.")
    
    try:
        # Create application
        app = CelestialPointer(
            latitude=args.latitude,
            longitude=args.longitude,
            altitude=args.altitude,
            min_elevation=args.min_elevation
        )
        
        # Magnetometer calibrate if requested (can be done independently)
        if args.calibrate_magnetometer:
            if not app.imu_controller.calibrate_magnetometer():
                print("Magnetometer calibration failed. Exiting.")
                sys.exit(1)
            # Exit after magnetometer calibration (don't start API)
            print("\nMagnetometer calibration complete. Exiting.")
            sys.exit(0)
        
        # Body calibrate if requested (can be done independently)
        if args.body_calibrate:
            if not app.calibrate_body():
                print("Body calibration failed. Exiting.")
                sys.exit(1)
            # Exit after body calibration (don't start API)
            print("\nBody calibration complete. Exiting.")
            sys.exit(0)
        
        # Test 180 degree rotation if requested
        if args.test_180:
            app.motor_controller.test_180_degree_rotation(laser_controller=app.laser_controller)
            print("\nTest complete. Exiting.")
            app.shutdown()
            sys.exit(0)
        
        # Calibrate if requested
        if args.calibrate:
            if not app.calibrate():
                print("Calibration failed. Exiting.")
                sys.exit(1)
        
        # Run API server
        app.run_api_server()
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")

        app.shutdown()

        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

