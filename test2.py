#!/usr/bin/env python3
"""
Test script for stepper motors using rpimotorlib.
Tests both base rotation motor and laser z-plane movement motor.
"""

import time
import RPi.GPIO as GPIO
from RpiMotorLib import RpiMotorLib

# Convert physical pins to GPIO/BCM pin numbers
# Motor 1: Base rotation (physical pins 32, 36, 38, 40)
# Physical pin 32 = GPIO 12, 36 = GPIO 16, 38 = GPIO 20, 40 = GPIO 21
motor1_pins = [12, 16, 20, 21]  # IN1, IN2, IN3, IN4

# Motor 2: Laser z-plane movement (physical pins 29, 31, 33, 35)
# Physical pin 29 = GPIO 5, 31 = GPIO 6, 33 = GPIO 13, 35 = GPIO 19
motor2_pins = [5, 6, 13, 19]  # IN1, IN2, IN3, IN4

# Initialize GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Initialize motors (28BYJ-48 stepper motor with ULN2003 driver)
motor1 = RpiMotorLib.BYJMotor("Motor1", "28BYJ")
motor2 = RpiMotorLib.BYJMotor("Motor2", "28BYJ")

def test_motor(motor, pins, name, steps=20, delay=0.01):
    """Test a motor by moving it forward and backward."""
    print(f"\nTesting {name}...")
    
    try:
        print(f"  Moving {name} forward {steps} steps...")
        motor.motor_run(
            pins,           # GPIO pins
            delay,          # Delay between steps (seconds)
            steps,          # Number of steps
            False,          # Clockwise (False = forward)
            False,          # Verbose
            "half",         # Step type: "full", "half", "wave"
            0.01            # Initial delay
        )
        time.sleep(0.5)
        
        print(f"  Moving {name} backward {steps} steps...")
        motor.motor_run(
            pins,
            delay,
            steps,
            True,           # Clockwise (True = backward)
            False,
            "half",
            0.01
        )
        time.sleep(0.5)
        
        print(f"  ✓ {name} test completed successfully")
        return True
    except Exception as e:
        print(f"  ✗ {name} test failed: {e}")
        return False

def main():
    print("Starting motor tests using rpimotorlib...")
    print("=" * 50)
    
    try:
        # Test Motor 1 (base rotation)
        # motor1_success = test_motor(
        #     motor1, 
        #     motor1_pins, 
        #     "Motor 1 (Base Rotation)", 
        #     steps=300,
        #     delay=0.001
        # )
        
        #Test Motor 2 (laser z-plane)
        motor2_success = test_motor(
            motor2, 
            motor2_pins, 
            "Motor 2 (Laser Z-Plane)", 
            steps=20,
            delay=0.01
        )
        
        print("\n" + "=" * 50)
        print("Test Summary:")
        # print(f"  Motor 1: {'PASS' if motor1_success else 'FAIL'}")
        print(f"  Motor 2: {'PASS' if motor2_success else 'FAIL'}")
        
    finally:
        # Cleanup GPIO
        GPIO.cleanup()
        print("\nGPIO cleaned up. Test complete.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        GPIO.cleanup()
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        GPIO.cleanup()

