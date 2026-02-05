"""
Main application entry point for Celestial Pointer.
"""

import sys
import time
import RPi.GPIO as GPIO
from .config import (
    LASER_DEFAULT_MIN_ELEVATION, API_HOST, API_PORT, LOAD_STAR_CHART,
    USE_DEFAULT_TARGET_ON_STARTUP
)
from .motor_controller import MotorController
from .laser_controller import LaserController
from .calibration import CalibrationController
from .target_calculator import TargetCalculator
from .display_controller import DisplayController
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
        
        # Initialize display controller first
        self.display_controller = DisplayController(i2c_address=0x27)
        self.display_controller.show_booting()
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Initialize controllers
        self.laser_controller = LaserController(
            min_elevation=min_elevation if min_elevation is not None else LASER_DEFAULT_MIN_ELEVATION
        )

        self.motor_controller = MotorController()
        self.calibration_controller = CalibrationController(
            self.motor_controller,
            self.laser_controller
        )

        self.target_calculator = TargetCalculator(latitude, longitude, altitude, load_star_chart=LOAD_STAR_CHART)
        
        self.calibrated = self.calibrate()
        
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
            self.display_controller
        )
        
        # Show IP address on display before ready
        if self.display_controller:
            self.display_controller.show_ip_address()
        

        
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
        
        # Close display
        if hasattr(self, 'display_controller') and self.display_controller:
            self.display_controller.close()
        
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
    parser.add_argument("--test-180", action="store_true",
                       help="Test both motors by rotating 180 degrees for laser and 360 for body")
    
    args = parser.parse_args()

    print("This is the Star Pointer Beta 0.1")
    print("This project points a laser at stars, planets, satellites using a laser controlled by 2 stepper motors for outdoor enjoyment with friends and family.")
    
    try:
        # Create application
        app = CelestialPointer(
            latitude=args.latitude,
            longitude=args.longitude,
            altitude=args.altitude,
            min_elevation=args.min_elevation
        )
        
        # Test 180 degree rotation if requested
        if args.test_180:
            app.motor_controller.test_180_degree_rotation(laser_controller=app.laser_controller)
            print("\nTest complete. Exiting.")
            app.shutdown()
            sys.exit(0)
        

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

