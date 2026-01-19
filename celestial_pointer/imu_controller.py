"""
IMU controller for GY9250 (MPU9250) orientation sensing.
"""

import time
import math
import os
import json
from .config import (
    IMU_I2C_ADDRESS, IMU_SAMPLE_RATE, IMU_CALIBRATION_SAMPLES,
    MAGNETOMETER_CALIBRATION_FILE, IMU_UPSIDE_DOWN, 
    IMU_ROTATION_OFFSET
)
from mpu9250_jmdev.registers import *
from mpu9250_jmdev.mpu_9250 import MPU9250

class IMUController:
    """Controls the GY9250 IMU for orientation sensing."""
    
    def __init__(self):
        """Initialize IMU controller."""
        self.imu = None
        self.calibrated = False
        self.magnetometer_calibrated = False
        self.calibration_offset = {'roll': 0, 'pitch': 0, 'yaw': 0}
        self._init_imu()
        # Load saved magnetometer calibration if available
        self._load_magnetometer_calibration()

        print("orientation and heading after calibration")
        orientation = self.get_orientation()
        print(f"Orientation: Roll={orientation['roll']:.2f}°, Pitch={orientation['pitch']:.2f}°, Yaw={orientation['yaw']:.2f}°")
        heading = self.get_heading()
        print(f"Heading: {heading:.2f}° (0° = North)")
    
    def _init_imu(self):
        """Initialize the IMU hardware."""
        try:  
            self.imu = MPU9250(
                address_ak=AK8963_ADDRESS,
                address_mpu_master=IMU_I2C_ADDRESS,
                address_mpu_slave=None,
                bus=1,
                gfs=GFS_1000,
                afs=AFS_8G,
                mfs=AK8963_BIT_16,
                mode=AK8963_MODE_C100HZ
            )
            
            self.imu.configure()
            print("IMU configured")

            print("Waiting 1 second for IMU to stabilize...")
            time.sleep(1)

            # Test magnetometer
            print("Testing magnetometer...")
            # test_magnetometer = self.test_magnetometer()
            # if not test_magnetometer:
            #     print("⚠ Warning: Magnetometer test failed!")
            #     print("Magnetometer calibration may be needed. Run with --calibrate-magnetometer")
            # else:
            #     print("✓ Magnetometer test passed")
            
            # print orientation and heading
            orientation = self.get_orientation()
            print(f"Orientation: Roll={orientation['roll']:.2f}°, Pitch={orientation['pitch']:.2f}°, Yaw={orientation['yaw']:.2f}°")
            heading = self.get_heading()
            print(f"Heading: {heading:.2f}° (0° = North)")

            # Calibrate accel/gyro only (not magnetometer)
            print("\nCalibrating accelerometer and gyroscope...")
            print("Please keep the device level and stationary...")
            time.sleep(1)
            self.imu.calibrateMPU6500()
            self.imu.configure()
            print("✓ Accelerometer and gyroscope calibrated")

          

            self.calibrated = True
        except (ImportError, NameError, AttributeError) as e:
            print(e)
            print("Warning: No IMU library found. Using mock IMU.")
            self.imu = None
            self.calibrated = False
    
    
    def get_orientation(self):
        """
        Get current orientation from IMU.
        
        Returns:
            dict: {'roll': degrees, 'pitch': degrees, 'yaw': degrees}
        """
        if self.imu is None:
            # Return mock data for testing
            return {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0}
        
        try:
            # Try mpu9250-jmdev
            if hasattr(self.imu, 'readAccelerometerMaster'):
                accel = self.imu.readAccelerometerMaster()
                gyro = self.imu.readGyroscopeMaster()
                
                # Calculate orientation from accelerometer (simple tilt)
                roll = math.atan2(accel[1], accel[2]) * 180 / math.pi
                pitch = math.atan2(-accel[0], math.sqrt(accel[1]**2 + accel[2]**2)) * 180 / math.pi
                
                # Try to get magnetometer data for yaw
                yaw = 0
                try:
                    if hasattr(self.imu, 'readMagnetometerMaster'):
                        mag = self.imu.readMagnetometerMaster()
                        if mag is not None and len(mag) >= 2:
                            # Calculate yaw from magnetometer (atan2(y, x) gives heading)
                            # mag[0] = X, mag[1] = Y, mag[2] = Z
                            yaw = math.atan2(mag[1], mag[0]) * 180 / math.pi
                            # If IMU is upside down, invert the yaw (add 180 degrees)
                            if IMU_UPSIDE_DOWN:
                                yaw = -yaw + IMU_ROTATION_OFFSET
                            # Debug: print magnetometer values
                            # print(f"Mag: X={mag[0]:.2f}, Y={mag[1]:.2f}, Z={mag[2]:.2f}, Yaw={yaw:.2f}")
                    elif hasattr(self.imu, 'readMagnetometer'):
                        # Alternative method name
                        mag = self.imu.readMagnetometer()
                        if mag is not None and len(mag) >= 2:
                            yaw = math.atan2(mag[1], mag[0]) * 180 / math.pi
                            # If IMU is upside down, invert the yaw (add 180 degrees)
                            if IMU_UPSIDE_DOWN:
                                yaw = -(yaw + IMU_ROTATION_OFFSET)
                except Exception as e:
                    # Print error for debugging
                    print(f"Magnetometer read error (mpu9250-jmdev): {e}")
                    pass  # Magnetometer not available or failed
                
            elif hasattr(self.imu, 'accel'):
                # mpu9250 library
                accel = self.imu.accel
                roll = math.atan2(accel.y, accel.z) * 180 / math.pi
                pitch = math.atan2(-accel.x, math.sqrt(accel.y**2 + accel.z**2)) * 180 / math.pi
                
                # Try to get magnetometer data
                yaw = 0
                try:
                    if hasattr(self.imu, 'mag'):
                        mag = self.imu.mag
                        if mag is not None:
                            yaw = math.atan2(mag.y, mag.x) * 180 / math.pi
                            # If IMU is upside down, invert the yaw (add 180 degrees)
                            if IMU_UPSIDE_DOWN:
                                yaw = -(yaw + IMU_ROTATION_OFFSET)
                    elif hasattr(self.imu, 'readMagnetometer'):
                        # Try direct method call
                        mag = self.imu.readMagnetometer()
                        if mag is not None:
                            if hasattr(mag, 'x') and hasattr(mag, 'y'):
                                yaw = math.atan2(mag.y, mag.x) * 180 / math.pi
                            elif isinstance(mag, (list, tuple)) and len(mag) >= 2:
                                yaw = math.atan2(mag[1], mag[0]) * 180 / math.pi
                            # If IMU is upside down, invert the yaw (add 180 degrees)
                            if IMU_UPSIDE_DOWN:
                                yaw = -(yaw + IMU_ROTATION_OFFSET)
                except Exception as e:
                    # Print error for debugging
                    print(f"Magnetometer read error (mpu9250): {e}")
                    pass
            else:
                # MPU6050
                accel_data = self.imu.get_accel_data()
                roll = math.atan2(accel_data['y'], accel_data['z']) * 180 / math.pi
                pitch = math.atan2(-accel_data['x'], 
                                  math.sqrt(accel_data['y']**2 + accel_data['z']**2)) * 180 / math.pi
                yaw = 0  # MPU6050 doesn't have magnetometer
            
            # Apply calibration offset
            roll += self.calibration_offset['roll']
            pitch += self.calibration_offset['pitch']
            yaw += self.calibration_offset['yaw']
            
            return {'roll': roll, 'pitch': pitch, 'yaw': yaw}
            
        except Exception as e:
            print(f"IMU read error: {e}")
            return {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0}
    
    def get_heading(self):
        """
        Get current heading (yaw) from IMU magnetometer.
        
        Returns:
            float: Heading in degrees (0-360, where 0 is North)
        """
        if self.imu is None:
            print("Warning: IMU not initialized, returning 0 for heading")
            return 0.0
        
        # Try to read magnetometer directly for better accuracy
        try:
            # Try mpu9250-jmdev
            if hasattr(self.imu, 'readMagnetometerMaster'):
                try:
                    mag = self.imu.readMagnetometerMaster()
                    if mag is not None and len(mag) >= 2:
                        yaw = math.atan2(mag[1], mag[0]) * 180 / math.pi
                        # If IMU is upside down, invert the yaw (add 180 degrees)
                        if IMU_UPSIDE_DOWN:
                            yaw = -(yaw + IMU_ROTATION_OFFSET)
                        # Apply calibration offset
                        yaw += self.calibration_offset['yaw']
                        # Normalize to 0-360
                        while yaw < 0:
                            yaw += 360
                        while yaw >= 360:
                            yaw -= 360
                        return yaw
                except Exception as e:
                    print(f"Error reading magnetometer (readMagnetometerMaster): {e}")
            
            # Try mpu9250 library
            elif hasattr(self.imu, 'mag'):
                try:
                    mag = self.imu.mag
                    if mag is not None:
                        yaw = math.atan2(mag.y, mag.x) * 180 / math.pi
                        # If IMU is upside down, invert the yaw (add 180 degrees)
                        if IMU_UPSIDE_DOWN:
                            yaw = -(yaw + IMU_ROTATION_OFFSET)
                        # Apply calibration offset
                        yaw += self.calibration_offset['yaw']
                        # Normalize to 0-360
                        while yaw < 0:
                            yaw += 360
                        while yaw >= 360:
                            yaw -= 360
                        return yaw
                except Exception as e:
                    print(f"Error reading magnetometer (mag attribute): {e}")
        except Exception as e:
            print(f"Error in get_heading: {e}")
        
        # Fallback to orientation method
        orientation = self.get_orientation()
        yaw = orientation['yaw']
        # Normalize to 0-360
        while yaw < 0:
            yaw += 360
        while yaw >= 360:
            yaw -= 360
        return yaw
    
    def test_magnetometer(self):
        """
        Test magnetometer reading using the high-level orientation and heading functions.
        
        Returns:
            bool: True if magnetometer appears to be working
        """
        if self.imu is None:
            print("IMU not initialized")
            return False
        
        print("\nTesting magnetometer...")
        print(f"IMU type: {type(self.imu)}")
        
        # Try to enable/configure magnetometer if methods exist
        try:
            # Check for I2C passthrough mode (needed for AK8963 access)
            if hasattr(self.imu, 'enableI2CBypass'):
                self.imu.enableI2CBypass()
                print("Enabled I2C bypass mode for magnetometer access")
            elif hasattr(self.imu, 'setI2CBypass'):
                self.imu.setI2CBypass(True)
                print("Set I2C bypass mode for magnetometer access")
            
            if hasattr(self.imu, 'enableMagnetometer'):
                self.imu.enableMagnetometer()
                print("Called enableMagnetometer()")
            if hasattr(self.imu, 'configureMagnetometer'):
                self.imu.configureMagnetometer()
                print("Called configureMagnetometer()")
            if hasattr(self.imu, 'setMagnetometerMode'):
                self.imu.setMagnetometerMode(0x02)  # Continuous measurement mode
                print("Set magnetometer to continuous mode (0x02)")
            if hasattr(self.imu, 'resetMagnetometer'):
                self.imu.resetMagnetometer()
                print("Reset magnetometer")
            
            # Try to read magnetometer WHO_AM_I register (should be 0x48 for AK8963)
            if hasattr(self.imu, 'readMagnetometerWhoAmI'):
                who_am_i = self.imu.readMagnetometerWhoAmI()
                print(f"Magnetometer WHO_AM_I: 0x{who_am_i:02X} (expected 0x48 for AK8963)")
            elif hasattr(self.imu, 'getMagnetometerID'):
                mag_id = self.imu.getMagnetometerID()
                print(f"Magnetometer ID: 0x{mag_id:02X} (expected 0x48 for AK8963)")
        except Exception as e:
            print(f"Note: Magnetometer configuration methods: {e}")
        
        # Wait a moment for magnetometer to stabilize
        print("\nWaiting for magnetometer to stabilize...")
        time.sleep(0.5)
        
        # Test using get_orientation() method
        print("\nTesting get_orientation()...")
        try:
            orientation = self.get_orientation()
            print(f"Orientation: Roll={orientation['roll']:.2f}°, Pitch={orientation['pitch']:.2f}°, Yaw={orientation['yaw']:.2f}°")
            
            # Check if yaw is valid (not zero, which might indicate magnetometer not working)
            if orientation['yaw'] == 0.0:
                print("⚠ Warning: Yaw is 0.0° - magnetometer may not be working")
                print("This could indicate:")
                print("  1. Magnetometer not properly initialized")
                print("  2. Hardware connection issue")
                print("  3. Magnetometer in sleep/power-down mode")
        except Exception as e:
            print(f"Error getting orientation: {e}")
            return False
        
        # Test using get_heading() method
        print("\nTesting get_heading()...")
        try:
            heading = self.get_heading()
            print(f"Heading: {heading:.2f}° (0° = North)")
            
            # Check if heading is valid
            if heading == 0.0:
                print("⚠ Warning: Heading is 0.0° - magnetometer may not be working")
            
            # Test multiple readings to check for stability
            print("\nTesting heading stability (5 readings)...")
            headings = []
            for i in range(5):
                h = self.get_heading()
                headings.append(h)
                print(f"  Reading {i+1}/5: {h:.2f}°")
                time.sleep(0.1)
            
            # Check variance
            avg_heading = sum(headings) / len(headings)
            variance = sum((h - avg_heading) ** 2 for h in headings) / len(headings)
            print(f"\nAverage heading: {avg_heading:.2f}°")
            print(f"Heading variance: {variance:.2f}°²")
            
            if variance > 100:  # Large variance indicates unstable readings
                print("⚠ Warning: High variance in heading readings")
                print("Possible causes:")
                print("  1. Strong magnetic interference")
                print("  2. Magnetometer calibration needed")
                print("  3. Device movement during test")
                return False
            
            print("\n✓ Magnetometer test passed!")
            print(f"  Using orientation yaw: {orientation['yaw']:.2f}°")
            print(f"  Using heading: {heading:.2f}°")
            return True
            
        except Exception as e:
            print(f"Error getting heading: {e}")
            return False
    
    def get_quaternion(self):
        """
        Get orientation as quaternion (if supported).
        
        Returns:
            dict: {'w': float, 'x': float, 'y': float, 'z': float}
        """
        orientation = self.get_orientation()
        roll = math.radians(orientation['roll'])
        pitch = math.radians(orientation['pitch'])
        yaw = math.radians(orientation['yaw'])
        
        # Convert Euler angles to quaternion
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)
        
        return {
            'w': cr * cp * cy + sr * sp * sy,
            'x': sr * cp * cy - cr * sp * sy,
            'y': cr * sp * cy + sr * cp * sy,
            'z': cr * cp * sy - sr * sp * cy
        }
    
    def _load_magnetometer_calibration(self):
        """
        Load saved magnetometer calibration (mbias and magScale) from file.
        
        Returns:
            bool: True if calibration loaded successfully, False otherwise
        """
        if self.imu is None:
            return False
        
        calibration_file = MAGNETOMETER_CALIBRATION_FILE
        if not os.path.exists(calibration_file):
            print(f"No saved magnetometer calibration found at {calibration_file}")
            print("Run with --calibrate-magnetometer to calibrate the magnetometer")
            return False
        
        try:
            with open(calibration_file, 'r') as f:
                data = json.load(f)
            
            mbias = data.get('mbias')
            magScale = data.get('magScale')
            
            if mbias is None or magScale is None:
                print("Invalid magnetometer calibration file format")
                return False
            
            # Apply calibration to IMU
            # Note: The library may store these as lists or tuples, so handle both formats
            try:
                if hasattr(self.imu, 'mbias'):
                    # Convert to list if needed (some libraries expect lists)
                    if isinstance(mbias, list):
                        self.imu.mbias = mbias
                    elif isinstance(mbias, (tuple, dict)):
                        # Convert tuple or dict to list
                        if isinstance(mbias, dict):
                            mbias = [mbias.get('x', 0), mbias.get('y', 0), mbias.get('z', 0)]
                        else:
                            mbias = list(mbias)
                        self.imu.mbias = mbias
                    else:
                        self.imu.mbias = mbias
                    print(f"Loaded magnetometer bias (mbias): {self.imu.mbias}")
                
                if hasattr(self.imu, 'magScale'):
                    # Convert to list if needed
                    if isinstance(magScale, list):
                        self.imu.magScale = magScale
                    elif isinstance(magScale, (tuple, dict)):
                        # Convert tuple or dict to list
                        if isinstance(magScale, dict):
                            magScale = [magScale.get('x', 1), magScale.get('y', 1), magScale.get('z', 1)]
                        else:
                            magScale = list(magScale)
                        self.imu.magScale = magScale
                    else:
                        self.imu.magScale = magScale
                    print(f"Loaded magnetometer scale (magScale): {self.imu.magScale}")
                
                # Some libraries may need a method call to apply the calibration
                if hasattr(self.imu, 'applyMagnetometerCalibration'):
                    self.imu.applyMagnetometerCalibration()
                elif hasattr(self.imu, 'setMagnetometerCalibration'):
                    self.imu.setMagnetometerCalibration(mbias, magScale)
                
                self.magnetometer_calibrated = True
                print("✓ Magnetometer calibration loaded and applied successfully")

                print("Calculated heading: ", self.get_heading())
                print("--------------------------------")
                return True
            except Exception as e:
                print(f"Error applying magnetometer calibration: {e}")
                return False
            
        except Exception as e:
            print(f"Error loading magnetometer calibration: {e}")
            return False
    
    def _save_magnetometer_calibration(self):
        """
        Save magnetometer calibration (mbias and magScale) to file.
        
        Returns:
            bool: True if calibration saved successfully, False otherwise
        """
        if self.imu is None:
            return False
        
        try:
            # Get calibration values from IMU
            mbias = None
            magScale = None
            
            if hasattr(self.imu, 'mbias'):
                mbias = self.imu.mbias
            if hasattr(self.imu, 'magScale'):
                magScale = self.imu.magScale
            
            if mbias is None or magScale is None:
                print("Error: Magnetometer calibration values not found in IMU object")
                print(f"  mbias exists: {hasattr(self.imu, 'mbias')}")
                print(f"  magScale exists: {hasattr(self.imu, 'magScale')}")
                if hasattr(self.imu, 'mbias'):
                    print(f"  mbias value: {self.imu.mbias}")
                if hasattr(self.imu, 'magScale'):
                    print(f"  magScale value: {self.imu.magScale}")
                return False
            
            # Convert to JSON-serializable format (lists)
            # Handle numpy arrays, tuples, etc.
            try:
                import numpy as np
                if isinstance(mbias, np.ndarray):
                    mbias = mbias.tolist()
                if isinstance(magScale, np.ndarray):
                    magScale = magScale.tolist()
            except ImportError:
                pass  # numpy not available, assume already serializable
            
            # Convert tuples to lists
            if isinstance(mbias, tuple):
                mbias = list(mbias)
            if isinstance(magScale, tuple):
                magScale = list(magScale)
            
            # Save to file
            calibration_file = MAGNETOMETER_CALIBRATION_FILE
            data = {
                'mbias': mbias,
                'magScale': magScale
            }
            
            with open(calibration_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✓ Magnetometer calibration saved to {calibration_file}")
            print(f"  mbias: {mbias}")
            print(f"  magScale: {magScale}")
            return True
            
        except Exception as e:
            print(f"Error saving magnetometer calibration: {e}")
            return False
    
    def calibrate_magnetometer(self):
        """
        Calibrate the magnetometer separately from accel/gyro.
        
        This should be done by moving the device in a figure-8 pattern
        to capture a full range of magnetic field data.
        
        Returns:
            bool: True if calibration successful, False otherwise
        """
        if self.imu is None:
            print("IMU not initialized")
            return False
        
        print("\n" + "=" * 60)
        print("MAGNETOMETER CALIBRATION")
        print("=" * 60)
        print("\nThis calibration corrects for hard iron (offset) and soft iron (scaling) effects.")
        print("\nInstructions:")
        print("1. Hold the device and move it slowly in a figure-8 pattern")
        print("2. Rotate it in all directions to capture a full range of magnetic field data")
        print("3. Continue for about 30-60 seconds")
        print("4. Keep the device away from strong magnetic fields or metal objects")
        print("\n" + "-" * 60)
        
        response = input("\nPress Enter to start calibration (or 'q' to quit): ")
        if response.lower() == 'q':
            return False
        
        print("\nStarting magnetometer calibration...")
        print("Move the device in a figure-8 pattern...")
        print("This will take about 30-60 seconds...")
        time.sleep(2)
        
        try:
            # Try different possible method names for magnetometer calibration
            calibration_method = None
            if hasattr(self.imu, 'calibrateAK8963'):
                calibration_method = 'calibrateAK8963'
            elif hasattr(self.imu, 'calibrateMagnetometer'):
                calibration_method = 'calibrateMagnetometer'
            elif hasattr(self.imu, 'calibrateMag'):
                calibration_method = 'calibrateMag'
            elif hasattr(self.imu, 'calibrate'):
                # Check if calibrate() handles magnetometer (might need a parameter)
                calibration_method = 'calibrate'
            
            if calibration_method:
                print(f"Using calibration method: {calibration_method}")
                if calibration_method == 'calibrate':
                    # Try calling calibrate() - it might handle magnetometer automatically
                    # or might need a parameter
                    try:
                        self.imu.calibrate()
                    except TypeError:
                        # Might need a parameter
                        try:
                            self.imu.calibrate(magnetometer=True)
                        except:
                            # Try without parameter but catch error
                            print("Note: calibrate() may not handle magnetometer")
                else:
                    # Call the specific magnetometer calibration method
                    getattr(self.imu, calibration_method)()
                
                print("✓ Magnetometer calibration complete")
                
                # Wait a moment for calibration values to be set
                time.sleep(0.5)
                
                # Verify calibration values exist
                if not (hasattr(self.imu, 'mbias') and hasattr(self.imu, 'magScale')):
                    print("⚠ Warning: Calibration completed but mbias/magScale not found")
                    print("Available attributes:", [a for a in dir(self.imu) if 'mag' in a.lower() or 'bias' in a.lower() or 'scale' in a.lower()])
                    return False
                
                # Save calibration to file
                if self._save_magnetometer_calibration():
                    self.magnetometer_calibrated = True
                    return True
                else:
                    print("⚠ Warning: Calibration completed but failed to save")
                    return False
            else:
                print("Error: IMU library does not support magnetometer calibration")
                print("Available methods with 'mag' or 'cal':")
                relevant_methods = [m for m in dir(self.imu) if 'mag' in m.lower() or 'cal' in m.lower()]
                for m in relevant_methods:
                    print(f"  - {m}")
                return False
                
        except Exception as e:
            print(f"Error during magnetometer calibration: {e}")
            import traceback
            traceback.print_exc()
            return False

