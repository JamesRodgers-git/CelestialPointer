#!/usr/bin/env python3
"""
Keyboard control for motors and laser.
Dvorak layout: A=counterclockwise, E=clockwise, ,=increase Z, o=decrease Z
Space=toggle laser, +/-=adjust speed, q=quit
"""

import time
import RPi.GPIO as GPIO
from RpiMotorLib import RpiMotorLib
import threading
import sys

# Convert physical pins to GPIO/BCM pin numbers
# Motor 1: Base rotation (physical pins 32, 36, 38, 40)
motor1_pins = [12, 16, 20, 21]  # IN1, IN2, IN3, IN4

# Motor 2: Laser z-plane movement (physical pins 29, 31, 33, 35)
motor2_pins = [5, 6, 13, 19]  # IN1, IN2, IN3, IN4

# Relay: physical pin 11 = GPIO 17
RELAY_PIN = 17

# Motor settings
MOTOR_STEP_TYPE = "half"
INITIAL_DELAY = 0.1  # Start very slow (0.1s = 10 steps per second)
MIN_DELAY = 0.001    # Fastest (0.001s = 1000 steps per second)
MAX_DELAY = 0.5      # Slowest (0.5s = 2 steps per second)
DELAY_STEP = 0.01    # Adjustment increment

# Initialize GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Setup relay pin
GPIO.setup(RELAY_PIN, GPIO.OUT)
# Most relay modules are active-low: LOW = ON, HIGH = OFF
GPIO.output(RELAY_PIN, GPIO.LOW)  # Start with laser OFF

# Initialize motors
motor1 = RpiMotorLib.BYJMotor("Motor1", "28BYJ")
motor2 = RpiMotorLib.BYJMotor("Motor2", "28BYJ")

# Global state
current_delay = INITIAL_DELAY
laser_on = False
motor1_running = False
motor2_running = False
motor1_direction = None  # False=forward (counterclockwise), True=backward (clockwise)
motor2_direction = None  # False=forward (increase Z), True=backward (decrease Z)
motor_lock = threading.Lock()

def set_laser(state):
    """Turn laser on or off."""
    global laser_on
    laser_on = state
    # Most relay modules are active-low: LOW = ON, HIGH = OFF
    GPIO.output(RELAY_PIN, GPIO.HIGH if state else GPIO.LOW)
    status = "Off" if state else "OFF"
    print(f"\n[Laser: {status}]")

def motor1_worker():
    """Worker thread for continuous motor 1 movement."""
    global motor1_running, motor1_direction, current_delay
    
    while True:
        with motor_lock:
            running = motor1_running
            direction = motor1_direction
            delay = current_delay
        
        if running and direction is not None:
            try:
                motor1.motor_run(
                    motor1_pins,
                    delay,
                    1,  # Single step
                    direction,  # False=counterclockwise, True=clockwise
                    False,
                    MOTOR_STEP_TYPE,
                    0.0
                )
            except Exception as e:
                print(f"Motor 1 error: {e}")
        else:
            time.sleep(0.01)  # Small delay when not running

def motor2_worker():
    """Worker thread for continuous motor 2 movement."""
    global motor2_running, motor2_direction, current_delay
    
    while True:
        with motor_lock:
            running = motor2_running
            direction = motor2_direction
            delay = current_delay
        
        if running and direction is not None:
            try:
                motor2.motor_run(
                    motor2_pins,
                    delay,
                    1,  # Single step
                    direction,  # False=increase Z, True=decrease Z
                    False,
                    MOTOR_STEP_TYPE,
                    0.0
                )
            except Exception as e:
                print(f"Motor 2 error: {e}")
        else:
            time.sleep(0.01)  # Small delay when not running

def print_status():
    """Print current status."""
    speed_pct = int((MAX_DELAY - current_delay) / (MAX_DELAY - MIN_DELAY) * 100)
    print(f"\r[Speed: {speed_pct}% | Delay: {current_delay:.3f}s | Laser: {'ON' if laser_on else 'OFF'}]", end='', flush=True)

def main():
    global current_delay, motor1_running, motor2_running, motor1_direction, motor2_direction
    
    print("=" * 60)
    print("Motor and Laser Keyboard Control")
    print("=" * 60)
    print("Controls (Dvorak layout):")
    print("  A = Counterclockwise (Motor 1 forward)")
    print("  E = Clockwise (Motor 1 backward)")
    print("  , = Increase Z angle (Motor 2 forward)")
    print("  o = Decrease Z angle (Motor 2 backward)")
    print("  SPACE = Toggle laser")
    print("  + = Increase speed (decrease delay)")
    print("  - = Decrease speed (increase delay)")
    print("  q = Quit")
    print("=" * 60)
    print("\nStarting with VERY SLOW speed for safety...")
    print("Press keys to control. Hold keys for continuous movement.\n")
    
    # Start motor worker threads
    m1_thread = threading.Thread(target=motor1_worker, daemon=True)
    m2_thread = threading.Thread(target=motor2_worker, daemon=True)
    m1_thread.start()
    m2_thread.start()
    
    try:
        # Try keyboard library first (best for press/release detection)
        import keyboard
        
        def on_key_event(event):
            global current_delay, motor1_running, motor2_running, motor1_direction, motor2_direction
            
            if event.event_type == keyboard.KEY_DOWN:
                if event.name == 'a':
                    with motor_lock:
                        motor1_running = True
                        motor1_direction = False
                    print_status()
                elif event.name == 'e':
                    with motor_lock:
                        motor1_running = True
                        motor1_direction = True
                    print_status()
                elif event.name == ',':
                    with motor_lock:
                        motor2_running = True
                        motor2_direction = False
                    print_status()
                elif event.name == 'o':
                    with motor_lock:
                        motor2_running = True
                        motor2_direction = True
                    print_status()
                elif event.name == 'space':
                    set_laser(not laser_on)
                    print_status()
                elif event.name == '+' or event.name == '=':
                    with motor_lock:
                        current_delay = max(MIN_DELAY, current_delay - DELAY_STEP)
                    print_status()
                elif event.name == '-' or event.name == '_':
                    with motor_lock:
                        current_delay = min(MAX_DELAY, current_delay + DELAY_STEP)
                    print_status()
                elif event.name == 'q':
                    return False
                    
            elif event.event_type == keyboard.KEY_UP:
                if event.name in ['a', 'e']:
                    with motor_lock:
                        motor1_running = False
                        motor1_direction = None
                    print_status()
                elif event.name in [',', 'o']:
                    with motor_lock:
                        motor2_running = False
                        motor2_direction = None
                    print_status()
            
            return True
        
        keyboard.hook(on_key_event)
        print_status()
        print("\n(Note: keyboard library may require sudo on Raspberry Pi)")
        keyboard.wait('q')
        
    except ImportError:
        # Fallback to termios for systems without keyboard library
        print("Note: keyboard library not available, using termios (toggle mode)")
        print("Press keys to toggle movement on/off (not continuous)")
        import termios
        import tty
        
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        
        try:
            tty.setraw(sys.stdin.fileno())
            
            while True:
                ch = sys.stdin.read(1)
                
                if ch == 'a' or ch == 'A':
                    # Toggle counterclockwise
                    with motor_lock:
                        if motor1_running and motor1_direction == False:
                            motor1_running = False
                            motor1_direction = None
                        else:
                            motor1_running = True
                            motor1_direction = False
                    print_status()
                    
                elif ch == 'e' or ch == 'E':
                    # Toggle clockwise
                    with motor_lock:
                        if motor1_running and motor1_direction == True:
                            motor1_running = False
                            motor1_direction = None
                        else:
                            motor1_running = True
                            motor1_direction = True
                    print_status()
                    
                elif ch == ',':
                    # Toggle increase Z
                    with motor_lock:
                        if motor2_running and motor2_direction == False:
                            motor2_running = False
                            motor2_direction = None
                        else:
                            motor2_running = True
                            motor2_direction = False
                    print_status()
                    
                elif ch == 'o' or ch == 'O':
                    # Toggle decrease Z
                    with motor_lock:
                        if motor2_running and motor2_direction == True:
                            motor2_running = False
                            motor2_direction = None
                        else:
                            motor2_running = True
                            motor2_direction = True
                    print_status()
                    
                elif ch == ' ':
                    # Toggle laser
                    set_laser(not laser_on)
                    print_status()
                    
                elif ch == '+' or ch == '=':
                    # Increase speed
                    with motor_lock:
                        current_delay = max(MIN_DELAY, current_delay - DELAY_STEP)
                    print_status()
                    
                elif ch == '-' or ch == '_':
                    # Decrease speed
                    with motor_lock:
                        current_delay = min(MAX_DELAY, current_delay + DELAY_STEP)
                    print_status()
                    
                elif ch == 'q' or ch == 'Q' or ord(ch) == 3:  # Ctrl+C
                    break
                    
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    # Stop all motors
    with motor_lock:
        motor1_running = False
        motor2_running = False
        motor1_direction = None
        motor2_direction = None
    
    set_laser(False)
    time.sleep(0.5)  # Give threads time to stop
    
    print("\n\nShutting down...")
    GPIO.cleanup()
    print("GPIO cleaned up. Goodbye!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        GPIO.cleanup()
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        GPIO.cleanup()

