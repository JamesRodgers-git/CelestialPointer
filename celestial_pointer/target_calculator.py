"""
Target calculator for astronomical objects, satellites, and planes.
Uses Skyfield for accurate astronomical calculations.
"""

import math
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Any
import warnings
from skyfield.api import wgs84
from skyfield.api import load, Topos, Loader, Star, EarthSatellite
from skyfield.data import hipparcos
import requests



# Suppress skyfield warnings about ephemeris files
warnings.filterwarnings('ignore', category=DeprecationWarning)


class TargetCalculator:
    """Calculates target positions for various objects using Skyfield."""
    
    def __init__(self, latitude: float, longitude: float, altitude: float = 0.0, load_star_chart: bool = True):
        """
        Initialize target calculator.
        
        Args:
            latitude: Observer latitude in degrees
            longitude: Observer longitude in degrees
            altitude: Observer altitude in meters (default: 0)
            load_star_chart: Whether to load the star catalog (default: True)
        """
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.load_star_chart = load_star_chart
        
        # Initialize Skyfield
        self._init_skyfield()
        
        # Preload brightest 100 satellites on startup
        self._preload_brightest_satellites()
    
    def _init_skyfield(self):
        """Initialize Skyfield components."""
        try:

            self.ts = load.timescale()
            self.eph = load('de421.bsp')  # Planetary ephemeris
            self.loader = Loader('~/.skyfield-data/')
            
            # Create observer location
            self.observer_topos = Topos(
                latitude_degrees=self.latitude,
                longitude_degrees=self.longitude,
                elevation_m=self.altitude
            )

            earth = self.eph['earth']
            self.observer_wgs84 = earth + wgs84.latlon(self.latitude, self.longitude, elevation_m=self.altitude)

            
            # Load star catalog (Hipparcos catalog) if enabled
            if self.load_star_chart:
                try:
                    with self.loader.open(hipparcos.URL) as f:
                        self.star_catalog = hipparcos.load_dataframe(f)
                    self.stars_loaded = True
                    print("Star catalog loaded successfully.")
                except Exception as e:
                    print(f"Warning: Could not load star catalog: {e}")
                    self.stars_loaded = False
                    self.star_catalog = None
            else:
                print("Star chart loading disabled (LOAD_STAR_CHART=False).")
                self.stars_loaded = False
                self.star_catalog = None
            
            # Satellite TLE data (will be loaded on demand)
            self.satellites = {}
            self.skyfield_available = True
            
        except ImportError:
            print("Warning: Skyfield not available. Install with: pip3 install skyfield")
            self.skyfield_available = False
            self.ts = None
            self.eph = None
            self.observer = None
            self.stars_loaded = False
            self.star_catalog = None
            self.satellites = {}
    
    def _get_altaz(self, astrometric) -> Tuple[float, float]:
        """
        Get altitude and azimuth from an astrometric position.
        
        Args:
            astrometric: Skyfield astrometric position
            
        Returns:
            tuple: (azimuth_degrees, elevation_degrees)
        """
        if not self.skyfield_available:
            return None, None
        
        try:
            alt, az, distance = astrometric.apparent().altaz()
            return math.degrees(az.radians), math.degrees(alt.radians)
        except AttributeError:
            # If astrometric doesn't have apparent(), try altaz() directly
            try:
                alt, az, distance = astrometric.altaz()
                return math.degrees(az.radians), math.degrees(alt.radians)
            except Exception:
                return None, None
    
    def get_star_position(self, star_name: str, time: Optional[datetime] = None) -> Optional[Tuple[float, float]]:
        """
        Get position of a star by name or HIP number using Skyfield star catalog.
        
        Args:
            star_name: Name of the star (e.g., "Sirius", "Polaris") or HIP number (e.g., "HIP32349", "32349")
            time: Observation time (default: now)
            
        Returns:
            tuple: (azimuth_degrees, elevation_degrees) or None if not found
        """
        # Check if it's a HIP number
        star_input = star_name.strip()
        if star_input.upper().startswith('HIP'):
            hip_number = star_input[3:].strip()
            try:
                hip_int = int(hip_number)
                return self.get_star_by_hip(hip_int, time)
            except ValueError:
                pass
        elif star_input.isdigit():
            # Just a number, assume it's a HIP number
            try:
                hip_int = int(star_input)
                return self.get_star_by_hip(hip_int, time)
            except ValueError:
                pass
        
        # Not a HIP number, try by name
        if not self.skyfield_available or not self.stars_loaded:
            # Fallback to simple catalog
            return self._get_star_position_fallback(star_name)
        
        if time is None:
            t = self.ts.now()
        else:
            t = self.ts.from_datetime(time)
        
        # Common star names mapping to Hipparcos IDs
        # Hipparcos catalog uses HIP numbers, but we can search by name
        star_name_map = {
            'sirius': 'HIP32349',
            'polaris': 'HIP11767',
            'vega': 'HIP91262',
            'arcturus': 'HIP69673',
            'capella': 'HIP24608',
            'rigel': 'HIP24436',
            'betelgeuse': 'HIP27989',
            'altair': 'HIP97649',
            'spica': 'HIP65474',
            'antares': 'HIP80763',
            'deneb': 'HIP102098',
            'fomalhaut': 'HIP113368',
            'regulus': 'HIP49669',
            'castor': 'HIP36850',
            'pollux': 'HIP37826',
        }
        
        star_key = star_name.lower().strip()
        
        # Try to find star by name in catalog
        try:
            # Search in star catalog by name (simplified - in production, use proper name resolution)
            if star_key in star_name_map:
                # Extract HIP number and use it
                hip_str = star_name_map[star_key][3:]  # Remove "HIP" prefix
                try:
                    hip_int = int(hip_str)
                    return self.get_star_by_hip(hip_int, time)
                except ValueError:
                    pass
            
            # Try searching catalog by approximate name matching
            # This is a simplified approach - for production, use a proper star name database
            star_names_lower = self.star_catalog.index.str.lower() if hasattr(self.star_catalog.index, 'str') else []
            
            # Fallback to coordinate-based lookup
            return self._get_star_position_fallback(star_name)
            
        except Exception as e:
            print(f"Error looking up star {star_name}: {e}")
            return self._get_star_position_fallback(star_name)
    
    def get_star_by_hip(self, hip_number: int, time: Optional[datetime] = None) -> Optional[Tuple[float, float]]:
        """
        Get position of a star by its Hipparcos (HIP) catalog number.
        
        Args:
            hip_number: HIP catalog number (e.g., 32349 for Sirius)
            time: Observation time (default: now)
            
        Returns:
            tuple: (azimuth_degrees, elevation_degrees) or None if not found
        """
        if not self.skyfield_available:
            return None
        
        if time is None:
            t = self.ts.now()
        else:
            t = self.ts.from_datetime(time)
        
        try:
            # Try to load from Hipparcos catalog if available
            if self.stars_loaded and self.star_catalog is not None:
                try:
                    # Look up star in catalog by HIP number
                    if hip_number in self.star_catalog.index:
                        star_row = self.star_catalog.loc[hip_number]
                        # Create star from catalog data using RA and Dec
                        # The catalog has 'ra_degrees' and 'dec_degrees' columns
                        # Access DataFrame values correctly
                        ra_degrees = star_row['ra_degrees'] if 'ra_degrees' in star_row else star_row.get('ra_degrees', 0)
                        dec_degrees = star_row['dec_degrees'] if 'dec_degrees' in star_row else star_row.get('dec_degrees', 0)
                        ra_hours = ra_degrees / 15.0  # Convert degrees to hours
                        
                        # Create star object
                        star = Star(ra_hours=ra_hours, dec_degrees=dec_degrees)
                        # Observe star from observer location
                        astrometric = self.observer.at(t).observe(star)
                        alt, az, distance = astrometric.apparent().altaz()
                        return math.degrees(az.radians), math.degrees(alt.radians)
                except Exception as e:
                    print(f"Error loading star HIP{hip_number} from catalog: {e}")
            
            # Fallback: Try loading star catalog directly
            try:

                # Load catalog on demand
                with load.open(hipparcos.URL) as f:
                    df = hipparcos.load_dataframe(f)
                
                if hip_number in df.index:
                    star_row = df.loc[hip_number]
                    # Extract RA and Dec from catalog
                    ra_degrees = star_row['ra_degrees'] if 'ra_degrees' in star_row else star_row.get('ra_degrees', 0)
                    dec_degrees = star_row['dec_degrees'] if 'dec_degrees' in star_row else star_row.get('dec_degrees', 0)
                    ra_hours = ra_degrees / 15.0  # Convert degrees to hours
                    
                    # Create star object
                    star = Star(ra_hours=ra_hours, dec_degrees=dec_degrees)
                    # Observe star from observer location
                    astrometric = self.observer.at(t).observe(star)
                    alt, az, distance = astrometric.apparent().altaz()
                    return math.degrees(az.radians), math.degrees(alt.radians)
            except Exception as e:
                print(f"Error loading star HIP{hip_number}: {e}")
            
            return None
            
        except Exception as e:
            print(f"Error calculating star position for HIP{hip_number}: {e}")
            return None
    
    def _get_star_position_fallback(self, star_name: str) -> Optional[Tuple[float, float]]:
        """Fallback star position using coordinate lookup."""
        # Star catalog with RA/Dec coordinates
        star_catalog = {
            "sirius": (6.752, -16.716),  # RA (hours), Dec (degrees)
            "polaris": (2.530, 89.264),
            "vega": (18.615, 38.784),
            "arcturus": (14.261, 19.182),
            "capella": (5.278, 45.998),
            "rigel": (5.242, -8.201),
            "betelgeuse": (5.919, 7.407),
            "altair": (19.846, 8.868),
            "spica": (13.420, -11.161),
            "antares": (16.490, -26.432),
            "deneb": (20.690, 45.280),
            "fomalhaut": (22.961, -29.622),
            "regulus": (10.140, 11.967),
            "castor": (7.577, 31.888),
            "pollux": (7.755, 28.026),
        }
        
        star_key = star_name.lower().strip()
        if star_key not in star_catalog:
            return None
        
        if not self.skyfield_available:
            # Use manual calculation if skyfield not available
            return self._calculate_azimuth_elevation_manual(star_catalog[star_key][0], star_catalog[star_key][1])
        
        # Use Skyfield for accurate calculation
        try:
            ra_hours, dec_degrees = star_catalog[star_key]
            
            # Create star object
            star = Star(ra_hours=ra_hours, dec_degrees=dec_degrees)
            
            # Calculate position
            t = self.ts.now()
            # Observe star from observer location
            astrometric = self.observer_wgs84.at(t).observe(star)
            alt, az, distance = astrometric.apparent().altaz()
            return math.degrees(az.radians), math.degrees(alt.radians)
        except Exception as e:
            print(f"Error calculating star position: {e}")
            return self._calculate_azimuth_elevation_manual(ra_hours, dec_degrees)
    
    def get_planet_position(self, planet_name: str, time: Optional[datetime] = None) -> Optional[Tuple[float, float]]:
        """
        Get position of a planet by name using Skyfield.
        
        Args:
            planet_name: Name of the planet (e.g., "Mars", "Jupiter")
            time: Observation time (default: now)
            
        Returns:
            tuple: (azimuth_degrees, elevation_degrees) or None if not found
        """
        if not self.skyfield_available:
            return None
        
        if time is None:
            t = self.ts.now()
        else:
            t = self.ts.from_datetime(time)
        
        # Planet mapping to Skyfield ephemeris names
        planets = {
            'mercury': 'mercury',
            'venus': 'venus',
            'earth': 'earth',
            'mars': 'mars barycenter',
            'jupiter': 'jupiter barycenter',
            'saturn': 'saturn barycenter',
            'uranus': 'uranus barycenter',
            'neptune': 'neptune barycenter',
            'pluto': 'pluto barycenter',
        }
        
        planet_key = planet_name.lower().strip()
        if planet_key not in planets:
            return None
        
        try:
            # Get planet from ephemeris (this is a position function)
            planet = self.eph[planets[planet_key]]
            # Observe planet from observer location
            astrometric = self.observer_wgs84.at(t).observe(planet)
            alt, az, distance = astrometric.apparent().altaz()
            return az.degrees, alt.degrees
        except Exception as e:
            print(f"Error calculating planet position: {e}")
            return None
    
    def get_moon_position(self, time=None):
        if not self.skyfield_available:
            return None

        t = self.ts.now() if time is None else self.ts.from_datetime(time)

        try:
            moon = self.eph["moon"]
            astrometric = self.observer_wgs84.at(t).observe(moon)
            alt, az, distance = astrometric.apparent().altaz()
            return az.degrees, alt.degrees
        except Exception as e:
            print(f"Error calculating moon position: {e}")
            return None

    
    def _preload_brightest_satellites(self):
        """Preload the brightest/visible satellites and stations on startup."""
        if not self.skyfield_available:
            print("Skyfield not available, skipping preloading of brightest satellites")
            return
        
        print("Preloading brightest 100 satellites...")
        # Use "visual" group which contains the brightest/visible satellites
        # "brightest" is not a valid Celestrak group name
        result = self.load_satellite_group("visual")
        if result['loaded'] == 0:
            # Fallback to "stations" if "visual" fails
            print("Visual group failed, trying stations group...")
            result = self.load_satellite_group("stations")
        print(f"Preloaded {result['loaded']} satellites (failed: {result['failed']})")
    
    def get_satellite_position(self, satellite_id: str, time: Optional[datetime] = None) -> Optional[Tuple[float, float]]:
        """
        Get position of a satellite by ID using pre-loaded satellite data.
        
        Args:
            satellite_id: Satellite identifier (e.g., "ISS", "25544", or satellite name)
            time: Observation time (default: now)
            
        Returns:
            tuple: (azimuth_degrees, elevation_degrees) or None if not found
        """
        if not self.skyfield_available:
            return None
        
        if time is None:
            t = self.ts.now()
        else:
            t = self.ts.from_datetime(time)
        
        # Handle special cases
        original_id = satellite_id
        if satellite_id.upper() == "ISS" or satellite_id == "25544":
            satellite_id = "25544"  # ISS NORAD ID
        
        # Check if it's already loaded (by NORAD ID or name)
        if satellite_id in self.satellites:
            try:
                satellite = self.satellites[satellite_id]
                difference = satellite - self.observer_topos
                topocentric = difference.at(t)
                alt, az, distance = topocentric.altaz()
                return math.degrees(az.radians), math.degrees(alt.radians)
            except Exception as e:
                print(f"Error calculating position for loaded satellite {satellite_id}: {e}")
                return None
        
        # Try searching by name in pre-loaded satellites (case-insensitive)
        search_term_upper = satellite_id.upper()
        for key, satellite in self.satellites.items():
            # Check if key is a name (not a numeric NORAD ID) and matches
            if not key.isdigit() and search_term_upper in key.upper():
                try:
                    difference = satellite - self.observer_topos
                    topocentric = difference.at(t)
                    alt, az, distance = topocentric.altaz()
                    return math.degrees(az.radians), math.degrees(alt.radians)
                except Exception as e:
                    continue
        
        # Not found in pre-loaded satellites
        print(f"Satellite '{original_id}' not found in pre-loaded satellites")
        return None
    
    def _load_satellite(self, satellite_id: str):
        """Load satellite TLE data from Celestrak."""
        try:
            
            # Normalize satellite ID
            original_id = satellite_id
            if satellite_id.upper() == "ISS":
                satellite_id = "25544"  # ISS NORAD ID
            
            # Try multiple URLs and methods
            urls = [
                'https://celestrak.org/NORAD/elements/stations.txt',
                'https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle',
            ]
            
            for url in urls:
                try:
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        lines = response.text.strip().split('\n')
                        # TLE format: name line, line 1, line 2 (repeats)
                        for i in range(0, len(lines), 3):
                            if i + 2 < len(lines):
                                name_line = lines[i].strip()
                                line1 = lines[i + 1].strip()
                                line2 = lines[i + 2].strip()
                                
                                # Check if this is our satellite by NORAD ID (first number in line 1)
                                # TLE line 1 format: "1 NNNNNU ..." where NNNNN is NORAD ID
                                if line1.startswith('1 '):
                                    try:
                                        # Extract NORAD ID - it's the second field, first 5 digits
                                        parts = line1.split()
                                        if len(parts) >= 2:
                                            norad_id = parts[1][:5]  # First 5 digits
                                            if satellite_id == norad_id or original_id.upper() in name_line.upper():
                                                satellite = EarthSatellite(line1, line2, name_line, self.ts)
                                                self.satellites[satellite_id] = satellite
                                                self.satellites[original_id] = satellite  # Also store under original ID
                                                print(f"Successfully loaded satellite {original_id} (NORAD {satellite_id})")
                                                return
                                    except (IndexError, ValueError) as e:
                                        # Skip malformed TLE lines
                                        continue
                except (requests.RequestException, requests.Timeout) as e:
                    print(f"Failed to fetch TLE from {url}: {e}")
                    continue
            
            # Alternative: Try loading from Skyfield's built-in satellite loader
            try:
                print(f"Trying Skyfield's built-in TLE loader for {satellite_id}...")
                satellites = load.tle_file('https://celestrak.org/NORAD/elements/stations.txt')
                for sat in satellites:
                    # Check if this satellite matches
                    if hasattr(sat, 'model') and hasattr(sat.model, 'satnum'):
                        if str(sat.model.satnum) == satellite_id:
                            self.satellites[satellite_id] = sat
                            self.satellites[original_id] = sat
                            print(f"Successfully loaded satellite {original_id} (NORAD {satellite_id}) via Skyfield")
                            return
            except Exception as e:
                print(f"Skyfield TLE loader failed: {e}")
            
            # If still not found, raise error with more details
            raise ValueError(f"Satellite {original_id} (NORAD {satellite_id}) not found in TLE data. "
                           f"Check network connection and Celestrak availability.")
                
        except ValueError:
            # Re-raise ValueError as-is (it has our custom message)
            raise
        except Exception as e:
            print(f"Error loading satellite TLE for {satellite_id}: {e}")
            raise ValueError(f"Failed to load satellite {satellite_id}: {str(e)}")
    
    def load_satellite_group(self, group_name: str, limit: Optional[int] = 200) -> Dict[str, Any]:
        """
        Load a group of satellites from Celestrak.
        
        Args:
            group_name: Celestrak group name (e.g., "stations", "brightest")
            limit: Maximum number of satellites to load (None = no limit)
            
        Returns:
            dict: {"loaded": int, "failed": int, "satellites": list of satellite info}
        """
        if not self.skyfield_available:
            return {"loaded": 0, "failed": 0, "satellites": []}
        
        try:
            from skyfield.api import EarthSatellite, load
            import requests
            
            url = f'https://celestrak.org/NORAD/elements/gp.php?GROUP={group_name}&FORMAT=tle'
            
            print(f"Loading satellite group '{group_name}' from Celestrak...")
            response = requests.get(url, timeout=30)
            
            if response.status_code != 200:
                print(f"Failed to load group '{group_name}': HTTP {response.status_code}")
                return {"loaded": 0, "failed": 0, "satellites": []}
            
            # Check if response contains an error message
            response_text = response.text.strip()
            if "Invalid query" in response_text or "not found" in response_text.lower():
                print(f"Error: Group '{group_name}' is not a valid Celestrak group")
                print(f"Response: {response_text[:200]}")
                return {"loaded": 0, "failed": 0, "satellites": []}
            
            lines = response_text.split('\n')
            if len(lines) < 3:
                print(f"Warning: Received insufficient data from Celestrak (only {len(lines)} lines)")
                print(f"First 200 chars: {response_text[:200]}")
                return {"loaded": 0, "failed": 0, "satellites": []}
            
            loaded_count = 0
            failed_count = 0
            satellites_info = []
            
            # TLE format: name line, line 1, line 2 (repeats)
            for i in range(0, len(lines), 3):
                if limit is not None and loaded_count >= limit:
                    break
                    
                if i + 2 < len(lines):
                    name_line = lines[i].strip()
                    line1 = lines[i + 1].strip()
                    line2 = lines[i + 2].strip()
                    
                    # Extract NORAD ID from line 1
                    if line1.startswith('1 '):
                        try:
                            parts = line1.split()
                            if len(parts) >= 2:
                                norad_id = parts[1][:5]
                                
                                try:
                                    satellite = EarthSatellite(line1, line2, name_line, self.ts)
                                    self.satellites[norad_id] = satellite
                                    self.satellites[name_line.strip()] = satellite  # Also store by name
                                    
                                    satellites_info.append({
                                        "norad_id": norad_id,
                                        "name": name_line.strip(),
                                        "satellite": satellite
                                    })
                                    loaded_count += 1
                                except Exception as e:
                                    failed_count += 1
                                    continue
                        except (IndexError, ValueError):
                            failed_count += 1
                            continue
            
            print(f"Loaded {loaded_count} satellites from group '{group_name}' (failed: {failed_count})")
            return {
                "loaded": loaded_count,
                "failed": failed_count,
                "satellites": satellites_info
            }
            
        except Exception as e:
            print(f"Error loading satellite group '{group_name}': {e}")
            return {"loaded": 0, "failed": 0, "satellites": []}
    
    def find_nearest_visible_satellite(self, groups: List[Dict[str, Any]], 
                                       min_elevation: float = 0.0,
                                       time: Optional[datetime] = None) -> Optional[Tuple[str, str, float, float]]:
        """
        Find the nearest visible satellite above the horizon from loaded groups.
        
        Args:
            groups: List of group configs with "group_name" and optional "limit"
            min_elevation: Minimum elevation in degrees (default: 0.0 = horizon)
            time: Observation time (default: now)
            
        Returns:
            tuple: (satellite_id, satellite_name, azimuth, elevation) or None if none found
        """
        if not self.skyfield_available:
            return None
        
        # Load all groups
        all_satellites = []
        for group_config in groups:
            group_name = group_config.get("group_name")
            limit = group_config.get("limit")
            
            if group_name:
                result = self.load_satellite_group(group_name, limit)
                all_satellites.extend(result["satellites"])
        
        if not all_satellites:
            return None
        
        # Get observation time
        if time is None:
            t = self.ts.now()
        else:
            t = self.ts.from_datetime(time)
        
        # Find the satellite with highest elevation above min_elevation
        best_satellite = None
        best_elevation = min_elevation - 1.0  # Start below minimum
        
        for sat_info in all_satellites:
            try:
                satellite = sat_info["satellite"]
                norad_id = sat_info["norad_id"]
                name = sat_info["name"]
                
                difference = satellite - self.observer_topos
                topocentric = difference.at(t)
                alt, az, distance = topocentric.altaz()
                
                elevation_deg = math.degrees(alt.radians)
                
                # Check if above minimum elevation and better than current best
                if elevation_deg >= min_elevation and elevation_deg > best_elevation:
                    best_elevation = elevation_deg
                    azimuth_deg = math.degrees(az.radians)
                    best_satellite = (norad_id, name, azimuth_deg, elevation_deg)
            except Exception as e:
                # Skip satellites that can't be calculated
                continue
        
        return best_satellite
    
    def get_preloaded_satellites(self) -> List[Dict[str, Any]]:
        """
        Get list of all preloaded satellites with their names, IDs, and current visibility.
        
        Returns:
            list: List of dictionaries with 'name', 'norad_id', 'id', 'elevation', and 'azimuth'
        """
        if not self.skyfield_available:
            return []
        
        satellites_list = []
        seen_satellites = set()  # Track satellite objects we've already processed
        t = self.ts.now()  # Current time for position calculation
        
        # Iterate through all satellites, but only add unique ones
        for key, satellite in self.satellites.items():
            # Use the satellite object itself as the unique identifier
            if satellite in seen_satellites:
                continue
            
            # Only process NORAD ID keys (numeric keys)
            if key.isdigit():
                norad_id = key
                seen_satellites.add(satellite)
                
                # Find the name for this satellite (it's stored as another key)
                name = None
                for name_key, sat_obj in self.satellites.items():
                    if not name_key.isdigit() and sat_obj is satellite:
                        name = name_key
                        break
                
                if name is None:
                    name = f"NORAD {norad_id}"
                
                # Calculate current position
                elevation = None
                azimuth = None
                try:
                    difference = satellite - self.observer_topos
                    topocentric = difference.at(t)
                    alt, az, distance = topocentric.altaz()
                    elevation = math.degrees(alt.radians)
                    azimuth = math.degrees(az.radians)
                except Exception as e:
                    # If calculation fails, set elevation to very low value
                    elevation = -90.0
                    azimuth = 0.0
                
                satellites_list.append({
                    "name": name,
                    "norad_id": norad_id,
                    "id": norad_id,  # Use NORAD ID for API pointing
                    "elevation": elevation,
                    "azimuth": azimuth
                })
        
        # Sort by elevation (lowest first), so highest is at bottom
        # Satellites below horizon (negative elevation) will be at top
        satellites_list.sort(key=lambda x: x["elevation"], reverse=False)
        
        return satellites_list
    
    def get_iss_position(self, time: Optional[datetime] = None) -> Optional[Tuple[float, float]]:
        """
        Get current position of the International Space Station.
        
        Args:
            time: Observation time (default: now)
            
        Returns:
            tuple: (azimuth_degrees, elevation_degrees) or None if not available
        """
        return self.get_satellite_position("ISS", time)
    
    
    def _calculate_azimuth_elevation_manual(self, ra_hours: float, dec_degrees: float,
                                           time: Optional[datetime] = None) -> Tuple[float, float]:
        """
        Manual calculation of azimuth/elevation from RA/Dec (fallback).
        
        Args:
            ra_hours: Right ascension in hours
            dec_degrees: Declination in degrees
            time: Observation time (default: now)
            
        Returns:
            tuple: (azimuth_degrees, elevation_degrees)
        """
        if time is None:
            time = datetime.utcnow()
        
        # Convert RA to radians
        ra_rad = math.radians(ra_hours * 15.0)  # RA in hours to degrees
        dec_rad = math.radians(dec_degrees)
        lat_rad = math.radians(self.latitude)
        lon_rad = math.radians(self.longitude)
        
        # Calculate Local Sidereal Time
        lst_hours = self._calculate_lst(time)
        lst_rad = math.radians(lst_hours * 15.0)
        
        # Hour angle
        ha_rad = lst_rad - ra_rad
        
        # Calculate elevation (altitude)
        sin_elevation = (math.sin(lat_rad) * math.sin(dec_rad) +
                        math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad))
        elevation_rad = math.asin(sin_elevation)
        elevation = math.degrees(elevation_rad)
        
        # Calculate azimuth
        cos_azimuth = ((math.sin(dec_rad) - math.sin(lat_rad) * sin_elevation) /
                      (math.cos(lat_rad) * math.cos(elevation_rad)))
        azimuth_rad = math.acos(max(-1, min(1, cos_azimuth)))
        
        # Determine quadrant
        if math.sin(ha_rad) > 0:
            azimuth_rad = 2 * math.pi - azimuth_rad
        
        azimuth = math.degrees(azimuth_rad) % 360
        
        return azimuth, elevation
    
    def _calculate_lst(self, time: datetime) -> float:
        """
        Calculate Local Sidereal Time.
        
        Args:
            time: Observation time
            
        Returns:
            LST in hours
        """
        jd = self._julian_day(time)
        t = (jd - 2451545.0) / 36525.0
        
        # Greenwich Mean Sidereal Time
        gmst = (280.46061837 + 360.98564736629 * (jd - 2451545.0) +
                0.000387933 * t * t - t * t * t / 38710000.0) % 360.0
        
        # Local Sidereal Time
        lst = (gmst + self.longitude) % 360.0
        
        return lst / 15.0  # Convert to hours
    
    def _julian_day(self, time: datetime) -> float:
        """Calculate Julian Day."""
        a = (14 - time.month) // 12
        y = time.year + 4800 - a
        m = time.month + 12 * a - 3
        
        jdn = (time.day + (153 * m + 2) // 5 + 365 * y +
               y // 4 - y // 100 + y // 400 - 32045)
        
        jd = jdn + (time.hour - 12) / 24.0 + time.minute / 1440.0 + time.second / 86400.0
        
        return jd
