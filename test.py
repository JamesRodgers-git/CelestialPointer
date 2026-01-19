#!/usr/bin/env python3
"""
Test script for stepper motors using gpiozero and lgpio.
Tests both base rotation motor and laser z-plane movement motor.
"""

from gpiozero import StepperMotor
from gpiozero.pins.lgpio import LGPIOFactory
import time

# Initialize lgpio pin factory
factory = LGPIOFactory()

# Motor 1: Base rotation (pins 32, 36, 38, 40)
motor1 = StepperMotor(
    coil1=(32, 36),  # IN1, IN2
    coil2=(38, 40),  # IN3, IN4
    pin_factory=factory
)

# Motor 2: Laser z-plane movement (pins 29, 31, 33, 35)
motor2 = StepperMotor(
    coil1=(29, 31),  # IN1, IN2
    coil2=(33, 35),  # IN3, IN4
    pin_factory=factory
)

def test_motor(motor, name, steps=10):
    """Test a motor by moving it forward and backward."""
    print(f"\nTesting {name}...")
    
    try:
        print(f"  Moving {name} forward {steps} steps...")
        motor.step(steps)
        time.sleep(0.5)
        
        print(f"  Moving {name} backward {steps} steps...")
        motor.step(-steps)
        time.sleep(0.5)
        
        print(f"  ✓ {name} test completed successfully")
        return True
    except Exception as e:
        print(f"  ✗ {name} test failed: {e}")
        return False

def main():
    print("Starting motor tests...")
    print("=" * 50)
    
    # Test Motor 1 (base rotation)
    motor1_success = test_motor(motor1, "Motor 1 (Base Rotation)", steps=20)
    
    # Test Motor 2 (laser z-plane)
    # motor2_success = test_motor(motor2, "Motor 2 (Laser Z-Plane)", steps=20)
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print(f"  Motor 1: {'PASS' if motor1_success else 'FAIL'}")
    # print(f"  Motor 2: {'PASS' if motor2_success else 'FAIL'}")
    
    # Cleanup
    motor1.close()
    # motor2.close()
    print("\nMotors closed. Test complete.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        motor1.close()
        # motor2.close()
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        motor1.close()
        # motor2.close()

