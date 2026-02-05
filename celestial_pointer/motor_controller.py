"""
Motor controller for base rotation and laser Z-axis movement.
"""

import time
import threading
import RPi.GPIO as GPIO
from RpiMotorLib import RpiMotorLib
from .config import (
    MOTOR1_PINS, MOTOR2_PINS, MOTOR_STEP_TYPE, MOTOR_DEFAULT_DELAY,
    MOTOR_STEPS_PER_REVOLUTION, MOTOR_DEGREES_PER_STEP, 
    MOTOR1_GEAR_RATIO, MOTOR2_GEAR_RATIO,
    LASER_MAX_ELEVATION, LASER_MIN_ELEVATION, MOTOR2_GEAR_OFFSET_STEPS
)

class MotorController:
    """Controls the two stepper motors for base rotation and laser elevation."""
    
    def __init__(self):
        """
        Initialize motor controller.
        
        Args:
        """
        self.motor1 = RpiMotorLib.BYJMotor("Motor1", "28BYJ")
        self.motor2 = RpiMotorLib.BYJMotor("Motor2", "28BYJ")

        # Motor state
        self.motor1_position = 0  # Steps from home (0 = home position) - used for movement only
        self.motor2_position = 0  # Steps from calibration (0 = 90 degrees relative to horizon)
        
        
        # Threading locks
        self.lock = threading.Lock()
        
        # Movement tracking (for preventing overlapping movements)
        self.motor1_moving_until = 0.0  # Timestamp when motor1 movement will complete
        self.motor2_moving_until = 0.0  # Timestamp when motor2 movement will complete
        
        # Calculate degrees per step accounting for gear ratios
        # Base: 512 steps = 360 degrees (external motor shaft)
        # Motor 1: Apply gear ratio for case rotation
        #   If gear_ratio = 0.5, motor rotates 2x for 1x case rotation
        #   So: degrees_per_step = base_degrees_per_step * gear_ratio
        self.motor1_degrees_per_step = MOTOR_DEGREES_PER_STEP * MOTOR1_GEAR_RATIO
        
        # Motor 2: Apply gear ratio for laser elevation
        #   If gear_ratio = 1.4286, motor rotates 1.4286x for 1x laser gear rotation
        #   So: degrees_per_step = base_degrees_per_step * gear_ratio
        self.motor2_degrees_per_step = MOTOR_DEGREES_PER_STEP * MOTOR2_GEAR_RATIO
        
        print(f"Motor 1: {MOTOR1_GEAR_RATIO:.4f}x gear ratio -> {self.motor1_degrees_per_step:.6f}° per step")
        print(f"Motor 2: {MOTOR2_GEAR_RATIO:.4f}x gear ratio -> {self.motor2_degrees_per_step:.6f}° per step")
        
    def move_motor1(self, steps, delay=None, clockwise=False):
        """
        Move motor 1 (base rotation).
        
        Args:
            steps: Number of steps to move
            delay: Delay between steps (seconds). If None, uses default.
            clockwise: True for clockwise, False for counterclockwise
        """
        if delay is None:
            delay = MOTOR_DEFAULT_DELAY

        # Calculate estimated movement time
        estimated_time = abs(steps) * delay
        movement_end_time = time.time() + (estimated_time * 1.1)  # Add 10% buffer
            
        with self.lock:
            try:
                # Update movement tracking
                self.motor1_moving_until = movement_end_time
                
                self.motor1.motor_run(
                    MOTOR1_PINS,
                    delay,
                    abs(steps),
                    clockwise,
                    False,  # verbose
                    MOTOR_STEP_TYPE,
                    0.0  # init_delay
                )

                self.motor1_position += steps
                
                # Clear movement tracking (movement complete)
                self.motor1_moving_until = 0.0

            except Exception as e:
                # Clear movement tracking on error
                self.motor1_moving_until = 0.0
                raise RuntimeError(f"Motor 1 movement failed: {e}")
    
    def move_motor2(self, steps, delay=None, clockwise=False):
        """
        Move motor 2 (laser Z-axis/elevation).
        
        Args:
            steps: Number of steps to move
            delay: Delay between steps (seconds). If None, uses default.
            clockwise: True for clockwise, False for counterclockwise
        """
        if delay is None:
            delay = MOTOR_DEFAULT_DELAY

        # Calculate estimated movement time
        estimated_time = abs(steps) * delay
        movement_end_time = time.time() + (estimated_time * 1.1)  # Add 10% buffer
            
        with self.lock:
            try:
                # Update movement tracking
                self.motor2_moving_until = movement_end_time
                
                self.motor2.motor_run(
                    MOTOR2_PINS,
                    delay,
                    abs(steps),
                    clockwise,
                    False,  # verbose
                    MOTOR_STEP_TYPE,
                    0.0  # init_delay
                )
                # Update position (forward = increase Z angle = counterclockwise = not clockwise)
                # If clockwise=False (forward), add steps. If clockwise=True (backward), subtract steps.
                if not clockwise:
                    self.motor2_position -= abs(steps)
                else:
                    self.motor2_position += abs(steps)
                
                # Clear movement tracking (movement complete)
                self.motor2_moving_until = 0.0
            except Exception as e:
                # Clear movement tracking on error
                self.motor2_moving_until = 0.0
                raise RuntimeError(f"Motor 2 movement failed: {e}")
    
    def move_motor2_calibration(self, steps, delay=None, clockwise=False, step_type=None):
        """
        Move motor 2 with custom step type (for calibration with full step mode).
        
        Args:
            steps: Number of steps to move
            delay: Delay between steps (seconds). If None, uses default.
            clockwise: True for clockwise, False for counterclockwise
            step_type: Step type ("full", "half", "wave"). If None, uses default.
        """
        if delay is None:
            delay = MOTOR_DEFAULT_DELAY
        if step_type is None:
            step_type = MOTOR_STEP_TYPE
        
        # Don't do anything if steps is 0
        if steps == 0:
            return
            
        with self.lock:
            try:
                
                old_position = self.motor2_position
                print(f"DEBUG Calibration: Moving {abs(steps)} steps, clockwise={clockwise}, old_position={old_position}")
                
                self.motor2.motor_run(
                    MOTOR2_PINS,
                    delay,
                    abs(steps),
                    clockwise,
                    False,  # verbose
                    step_type,  # Use specified step type (full for calibration)
                    0.0  # init_delay
                )

                self.motor2_position += steps
                
                print(f"DEBUG Calibration: New position={self.motor2_position} steps, angle={self.motor2_position * self.motor2_degrees_per_step:.2f}°")
            except Exception as e:
                raise RuntimeError(f"Motor 2 calibration movement failed: {e}")
    
    def move_motor1_degrees(self, degrees, delay=None, clockwise=False):
        """
        Move motor 1 by a specific number of degrees.
        
        Args:
            degrees: Degrees to move (positive = counterclockwise, negative = clockwise)
            delay: Delay between steps
            clockwise: Direction override (if None, determined by sign of degrees)
        """

        if delay is None:
            delay = MOTOR_DEFAULT_DELAY

        steps = int(degrees / self.motor1_degrees_per_step)

        clockwise = degrees > 0
        self.move_motor1(steps, delay, clockwise)
    
    def move_motor2_degrees(self, degrees, delay=None, clockwise=False, skip_bounds_check=False):
        """
        Move motor 2 by a specific number of degrees.
        
        Args:
            degrees: Degrees to move (positive = increase Z, negative = decrease Z)
            delay: Delay between steps
            clockwise: Direction override (if None, determined by sign of degrees)
            skip_bounds_check: Unused parameter (kept for backward compatibility)
        """
        if delay is None:
            delay = MOTOR_DEFAULT_DELAY
            
        steps = int(degrees / self.motor2_degrees_per_step) 

        clockwise = degrees > 0
        self.move_motor2(steps, delay, clockwise)
    
    def get_motor1_position(self):
        """Get current motor 1 position in steps."""
        with self.lock:
            return self.motor1_position
    
    def get_motor2_position(self):
        """Get current motor 2 position in steps."""
        with self.lock:
            return self.motor2_position
    
    def get_motor1_angle(self):
        """
        Get current motor 1 angle in degrees.
        """

        return self.motor1_position * self.motor1_degrees_per_step
        
    
    def get_motor2_angle(self):
        """Get current motor 2 angle in degrees (relative to calibration)."""
        angle = self.motor2_position * self.motor2_degrees_per_step
        return angle
    
    def is_motor1_moving(self):
        """Check if motor 1 is currently moving."""
        with self.lock:
            return self.motor1_moving_until > time.time()
    
    def is_motor2_moving(self):
        """Check if motor 2 is currently moving."""
        with self.lock:
            return self.motor2_moving_until > time.time()
    
    def are_motors_moving(self):
        """Check if either motor is currently moving."""
        return self.is_motor1_moving() or self.is_motor2_moving()
    
    def reset_motor1_position(self):
        """Reset motor 1 position counter to 0."""
        with self.lock:
            self.motor1_position = 0
    
    def reset_motor2_position(self):
        """Reset motor 2 position counter to 0 (calibration position)."""
        with self.lock:
            old_position = self.motor2_position
            old_angle = old_position * self.motor2_degrees_per_step
            self.motor2_position = 0
            print(f"DEBUG: Reset motor2_position from {old_position} steps ({old_angle:.2f}°) to 0 steps (0.00°)")
            # Verify reset worked
            if self.motor2_position != 0:
                print(f"ERROR: Reset failed! motor2_position is still {self.motor2_position}")
    
    def home_motor2(self, laser_controller=None, slow_mode=False, verbose=True):
        """
        Home motor 2 by moving up slowly to the stop button position.
        
        Moves motor 2 upward for LASER_CALIBRATION_STEPS, then resets position to 0.
        This positions the laser at maximum upward position (~90 degrees relative to horizon).
        
        Args:
            laser_controller: Optional LaserController to turn on/off laser during homing
            slow_mode: If True, uses slower movement (2x delay, smaller batches) to prevent damage
            verbose: If True, prints progress messages
            
        Returns:
            bool: True if homing successful, False otherwise
        """
        from .config import LASER_CALIBRATION_STEPS, CALIBRATION_STEP_DELAY, CALIBRATION_STEP_TYPE
        
        calibration_steps = LASER_CALIBRATION_STEPS
        
        if verbose:
            print("Homing motor 2...")
            if slow_mode:
                print(f"Moving up slowly {calibration_steps} steps to reach stop button...")
                print("Moving slowly to prevent damage when hitting the button.")
            else:
                print(f"Moving laser upward {calibration_steps} steps gently to reach calibration position...")
        
        # Turn on laser for visibility if provided
        # if laser_controller:
            # laser_controller.turn_on()
        
        try:
            # Configure movement parameters based on mode
            if slow_mode:
                steps_per_batch = 5  # Very small batches for slow, gentle movement
                delay = CALIBRATION_STEP_DELAY * 2  # Slower delay
                batch_pause = 0.2  # Brief pause between batches
                progress_interval = 25  # Show progress every 25 steps
            else:
                steps_per_batch = 10  # Normal batch size
                delay = CALIBRATION_STEP_DELAY
                batch_pause = 0.2  # Brief pause between batches
                progress_interval = 50  # Show progress every 50 steps
            
            total_batches = calibration_steps // steps_per_batch
            remainder = calibration_steps % steps_per_batch
            
            if verbose:
                print(f"Moving in {total_batches} batches of {steps_per_batch} steps...")
            
            # Move up in batches
            for batch in range(total_batches):
                self.move_motor2_calibration(
                    steps_per_batch,
                    delay=delay,
                    clockwise=False,  # False = forward = increase Z (move up)
                    step_type=CALIBRATION_STEP_TYPE
                )
                current_steps = (batch + 1) * steps_per_batch
                
                if verbose:
                    if current_steps % progress_interval == 0 or current_steps == total_batches * steps_per_batch:
                        print(f"  Moved {current_steps}/{calibration_steps} steps (angle: {self.get_motor2_angle():.2f}°)")
                
                time.sleep(batch_pause)
            
            # Move any remaining steps
            if remainder > 0:
                self.move_motor2_calibration(
                    remainder,
                    delay=delay,
                    clockwise=False,
                    step_type=CALIBRATION_STEP_TYPE
                )
                if verbose:
                    print(f"  Moved {calibration_steps}/{calibration_steps} steps (angle: {self.get_motor2_angle():.2f}°)")
            
            # Reset motor 2 position to 0 at calibration point
            if verbose:
                print(f"\nBefore reset: motor2_position = {self.get_motor2_position()} steps, angle = {self.get_motor2_angle():.2f}°")
            
            # move backwards MOTOR2_GEAR_OFFSET_STEPS steps to release pressure on the stop
            self.move_motor2_degrees(MOTOR2_GEAR_OFFSET_STEPS, clockwise=True, skip_bounds_check=True)

            self.reset_motor2_position()
            
            if verbose:
                print(f"After reset: motor2_position = {self.get_motor2_position()} steps, angle = {self.get_motor2_angle():.2f}°")
                print("✓ Motor 2 homed and reset to 0 (calibration position)")
            
            return True
            
        except Exception as e:
            if verbose:
                print(f"Error during motor 2 homing: {e}")
            return False
        finally:
            # Turn off laser if provided
            if laser_controller:
                laser_controller.turn_off()
    
    def get_motor1_angle_from_steps(self):
        """Get motor 1 angle from step count (for testing, ignores magnetometer)."""
        return self.motor1_position * self.motor1_degrees_per_step
    
    def test_180_degree_rotation(self, laser_controller=None):
        """
        Test both motors by rotating exactly 180 degrees.
        This helps verify gearing ratios and step accuracy.
        Includes motor 1 calibration process for accurate gear ratio determination.
        
        Args:
            laser_controller: Optional LaserController to turn on laser for calibration
        """
        print("\n" + "=" * 60)
        print("180 DEGREE ROTATION TEST")
        print("=" * 60)
        print("\nThis test will help you calibrate gear ratios accurately.")
        print("It includes a motor 1 calibration process and then tests both motors.")
        
        # Motor 2 homing setup
        print("\n" + "-" * 60)
        print("MOTOR 2 HOMING SETUP")
        print("-" * 60)
        print("\nMotor 2 needs to be homed before the test.")
        print("This will move motor 2 up slowly for a fixed number of steps")
        print("until it reaches the stop button, then reset its position to 0.")
        
        self.home_motor2(laser_controller=laser_controller, slow_mode=True, verbose=True)
        
        # Motor 1 calibration process
        print("\n" + "-" * 60)
        print("MOTOR 1 CALIBRATION FOR GEAR RATIO")
        print("-" * 60)
        print("\nThis process will help you mark a reference point on the wall")
        print("for extremely high accuracy gear ratio calibration.")
        print("\nSteps:")
        print("1. Laser will move down 90 degrees from home position")
        print("2. Laser will turn on")
        print("3. You'll mark a reference point on the wall")
        print("4. Motor 1 will rotate 360 degrees")
        print("5. You'll verify the laser returns to the same mark")
        print("6. Laser will turn off and move down another 90 degrees")
        
        response = input("\nPress Enter to start motor 1 calibration (or 's' to skip)... ")
        if response.lower() != 's':
            if laser_controller is None:
                print("⚠ Warning: No laser controller provided. Skipping motor 1 calibration.")
            else:
                # Step 1: Move laser down 90 degrees from calibration position
                print("\nStep 1: Moving laser down 90 degrees...")
                self.move_motor2_degrees(90.0, clockwise=None, skip_bounds_check=True)
                time.sleep(0.5)
                print("✓ Laser moved down 90 degrees")
                
                # Step 2: Turn on laser
                print("\nStep 2: Turning on laser...")
                laser_controller.turn_on()
                print("✓ Laser is on")
                
                # Step 3: Wait for user to mark reference point
                print("\nStep 3: Mark your reference point on the wall.")
                print("Position the laser where you want to mark, then press Enter to continue...")
                input()
                
                # Step 4: Reset motor 1 position to 0 (this is the reference position)
                print("\nStep 4: Setting motor 1 home position to 0...")
                self.reset_motor1_position()
                print("✓ Motor 1 home position set to 0")
                
                # Step 5: Rotate 360 degrees
                print("\nStep 5: Rotating motor 1 by 360 degrees...")
                print("Watch the laser - it should return to your mark when the rotation completes.")
                self.move_motor1_degrees(360.0, clockwise=None)
                time.sleep(0.5)
                print("✓ 360 degree rotation complete")
                
                # Step 6: Wait for user to verify and take notes
                print("\nStep 6: Verify the laser returned to your mark.")
                print("Take any notes you need, then press Enter to continue...")
                input()
                
                # Step 7: Turn off laser
                print("\nStep 7: Turning off laser...")
                laser_controller.turn_off()
                print("✓ Laser is off")
                
                # Step 8: Move laser down another 90 degrees (total 180 from home)
                print("\nStep 8: Moving laser down another 90 degrees (total 180 from home)...")
                self.move_motor2_degrees(90.0, clockwise=None, skip_bounds_check=True)
                time.sleep(0.5)
                print("✓ Laser moved down to 180 degrees from home")
                
                print("\n✓ Motor 1 calibration complete!")
        else:
            print("Skipping motor 1 calibration...")
        
        print("\n" + "-" * 60)
        print("Starting 180° rotation test in 2 seconds...")
        time.sleep(2)
        
        # Get starting positions (use step-based calculation for accuracy)
        start_motor1_angle = self.get_motor1_angle_from_steps()
        start_motor2_angle = self.get_motor2_angle()
        start_motor1_steps = self.get_motor1_position()
        start_motor2_steps = self.get_motor2_position()
        
        
        # Wait a moment for movement to complete
        time.sleep(0.5)
        
        print("\n" + "=" * 60)
    
    def close(self):
        """Clean up motor resources."""
        # Motors are controlled via GPIO, cleanup handled by main GPIO.cleanup()
        pass

