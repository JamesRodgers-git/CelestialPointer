# Celestial Pointer API Specification

**Version:** 1.0  
**Base URL:** `http://localhost:8000` (default)  
**API Type:** RESTful JSON API  
**Documentation:** Interactive API docs available at `http://localhost:8000/docs`

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Common Response Formats](#common-response-formats)
4. [Status & Information Endpoints](#status--information-endpoints)
5. [Pointing Endpoints](#pointing-endpoints)
6. [Laser Control Endpoints](#laser-control-endpoints)
7. [Default Body Management](#default-body-management)
8. [Tracking Control](#tracking-control)
9. [Satellite Management](#satellite-management)
10. [Error Handling](#error-handling)
11. [Data Models](#data-models)

---

## Overview

The Celestial Pointer API provides control over a laser pointing system that can point at stars, planets, satellites, and arbitrary orientations. The system uses stepper motors for base rotation and laser elevation control, with an IMU for orientation sensing.

### Base URL
```
http://localhost:8000
```

### Content Type
All requests and responses use `application/json`.

---

## Authentication

Currently, the API does not require authentication. All endpoints are accessible without credentials.

---

## Common Response Formats

### Success Response
Most endpoints return a JSON object with status information:
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1
}
```

### Error Response
Errors return HTTP status codes and JSON error details:
```json
{
  "detail": "Error message describing what went wrong"
}
```

Common HTTP status codes:
- `200 OK` - Request successful
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service temporarily unavailable

---

## Status & Information Endpoints

### GET `/`
Get API information.

**Response:**
```json
{
  "name": "Celestial Pointer API",
  "version": "0.1.0",
  "status": "running"
}
```

### GET `/status`
Get current system status.

**Response:**
```json
{
  "laser_on": false,
  "current_target": {
    "type": "satellite",
    "id": "25544",
    "azimuth": 180.5,
    "elevation": 45.2
  },
  "default_target": {
    "type": "satellite",
    "id": "ISS"
  },
  "tracking_enabled": true,
  "is_trackable": true,
  "motor1_angle": 180.0,
  "motor2_angle": 45.0,
  "elevation_range": {
    "min": -50.0,
    "max": 90.0
  }
}
```

**Response (if system not initialized):**
```json
{
  "status": "not_initialized"
}
```

---

## Pointing Endpoints

### POST `/target/orientation`
Point at a specific azimuth and elevation.

**Request Body:**
```json
{
  "azimuth": 180.0,    // degrees (0-360)
  "elevation": 45.0    // degrees (-90 to 90)
}
```

**Response:**
```json
{
  "status": "pointing",
  "azimuth": 180.0,
  "elevation": 45.0,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1
}
```

### POST `/target/star`
Point at a star by name or HIP number.

**Request Body:**
```json
{
  "star_name": "Sirius"  // or "HIP32349" or "32349"
}
```

**Response:**
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1,
  "star_name": "Sirius",
  "hip_number": 32349
}
```

### POST `/target/planet`
Point at a planet by name.

**Request Body:**
```json
{
  "planet_name": "Mars"  // or "Moon", "Jupiter", etc.
}
```

**Response:**
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1
}
```

### POST `/target/satellite`
Point at a satellite by ID (NORAD ID or name).

**Request Body:**
```json
{
  "satellite_id": "25544"  // or "ISS", or satellite name
}
```

**Response:**
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1
}
```

**Note:** The satellite must be in the preloaded satellite list. Use `GET /satellites` to see available satellites.


### POST `/target/nearest-group`
Find and track the nearest visible satellite above horizon from configured groups.

**Request Body:**
```json
{
  "groups": [  // optional, uses config default if not provided
    {
      "group_name": "stations",
      "limit": null
    },
    {
      "group_name": "visual",
      "limit": null
    }
  ],
  "min_elevation": 0.0  // optional, minimum elevation in degrees
}
```

**Response:**
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1,
  "group_tracking": true,
  "satellite_id": "25544",
  "sticky_duration": 60.0
}
```

**Note:** This enables group tracking mode, which will automatically switch to better bodies after the sticky duration expires.

### POST `/target/default`
Point at the currently set default body.

**Response (for star/planet/satellite/orientation):**
```json
{
  "status": "pointing",
  "azimuth": 180.5,
  "elevation": 45.2,
  "motor1_delta": 5.3,
  "motor2_delta": -2.1
}
```

**Error:** Returns `404` if no default body is set.

### POST `/detarget`
Stop pointing and turn off laser.

**Response:**
```json
{
  "status": "detargeted",
  "laser_off": true
}
```

---

## Laser Control Endpoints

### POST `/laser/toggle`
Toggle laser on/off or set specific state.

**Request Body:**
```json
{
  "state": null  // null = toggle, true = on, false = off
}
```

**Response:**
```json
{
  "status": "laser_on",
  "laser_state": true
}
```

### GET `/laser/status`
Get current laser status.

**Response:**
```json
{
  "laser_on": true,
  "min_elevation": -50.0,
  "max_elevation": 90.0
}
```

---

## Default Body Management

### POST `/default-target`
Set a default body that can be activated later.

**Request Body:**
```json
{
  "target_type": "satellite",  // "star", "planet", "satellite", "orientation"
  "target_value": "ISS",      // star name, planet name, satellite ID, or "orientation"
  "azimuth": null,             // required for "orientation" type
  "elevation": null            // required for "orientation" type
}
```

**Example for satellite:**
```json
{
  "target_type": "satellite",
  "target_value": "ISS"
}
```

**Example for orientation:**
```json
{
  "target_type": "orientation",
  "target_value": "orientation",
  "azimuth": 180.0,
  "elevation": 45.0
}
```

**Response:**
```json
{
  "status": "default_target_set",
  "default_target": {
    "type": "satellite",
    "id": "ISS"
  }
}
```

### GET `/default-target`
Get the currently set default body.

**Response:**
```json
{
  "default_target": {
    "type": "satellite",
    "id": "ISS"
  }
}
```

**Response (if no default body):**
```json
{
  "default_target": null
}
```

### DELETE `/default-target`
Clear the default body.

**Response:**
```json
{
  "status": "default_target_cleared"
}
```

---

## Tracking Control

### POST `/tracking/enable`
Enable automatic body tracking.

**Response:**
```json
{
  "status": "tracking_enabled",
  "tracking": true
}
```

### POST `/tracking/disable`
Disable automatic body tracking.

**Response:**
```json
{
  "status": "tracking_disabled",
  "tracking": false
}
```

### GET `/tracking/status`
Get current tracking status.

**Response:**
```json
{
  "tracking_enabled": true,
  "update_frequency": 5.0,
  "min_movement_threshold": 0.5,
  "current_target": {
    "type": "satellite",
    "id": "25544",
    "azimuth": 180.5,
    "elevation": 45.2
  },
  "is_trackable": true
}
```

---

## Satellite Management

### GET `/satellites`
Get list of all preloaded satellites with their names, pointing information, and current visibility.

**Query Parameters:**
- `format` (optional): `"table"` for formatted table output, `"json"` for JSON (default)

**Response (JSON format):**
```json
{
  "count": 100,
  "satellites": [
    {
      "name": "ISS (ZARYA)",
      "norad_id": "25544",
      "elevation": 75.30,
      "azimuth": 120.45,
      "visible": true,
      "endpoint": "/target/satellite",
      "method": "POST",
      "payload": {
        "satellite_id": "25544"
      },
      "example_curl": "curl -X POST http://localhost:8000/target/satellite -H \"Content-Type: application/json\" -d '{\"satellite_id\": \"25544\"}'"
    }
  ]
}
```

**Response (Table format):**
When `?format=table` is used, returns a plain text formatted table suitable for command-line viewing. Satellites are sorted by elevation with the most visible (highest elevation) at the bottom.

---

## Error Handling

### Common Error Responses

**404 Not Found:**
```json
{
  "detail": "Star 'InvalidStar' not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "System not initialized"
}
```

**503 Service Unavailable:**
```json
{
  "detail": "Satellite '25544' position not available"
}
```

### Error Scenarios

1. **Body Not Found**: When requesting a star, planet, or satellite that doesn't exist
2. **System Not Initialized**: When the system hasn't finished starting up
3. **Position Unavailable**: When a satellite's position can't be calculated (network issues, TLE data unavailable)
4. **Out of Range**: When a body is below the minimum elevation range

---

## Data Models

### OrientationTarget
```typescript
{
  azimuth: number;      // 0-360 degrees
  elevation: number;    // -90 to 90 degrees
}
```

### StarTarget
```typescript
{
  star_name: string;    // Star name or HIP number (e.g., "Sirius", "HIP32349", "32349")
}
```

### PlanetTarget
```typescript
{
  planet_name: string;  // Planet name (e.g., "Mars", "Moon", "Jupiter")
}
```

### SatelliteTarget
```typescript
{
  satellite_id: string; // NORAD ID or satellite name (e.g., "25544", "ISS")
}
```

### LaserToggle
```typescript
{
  state?: boolean | null; // null = toggle, true = on, false = off
}
```

### DefaultTarget
```typescript
{
  target_type: "star" | "planet" | "satellite" | "orientation";
  target_value: string;
  azimuth?: number;      // Required for "orientation" type
  elevation?: number;    // Required for "orientation" type
}
```

### GroupTarget
```typescript
{
  groups?: Array<{
    group_name: string;
    limit?: number | null;
  }>;
  min_elevation?: number;
}
```

---

## Usage Examples

### Point at a Star
```bash
curl -X POST http://localhost:8000/target/star \
  -H "Content-Type: application/json" \
  -d '{"star_name": "Sirius"}'
```

### Point at a Satellite
```bash
curl -X POST http://localhost:8000/target/satellite \
  -H "Content-Type: application/json" \
  -d '{"satellite_id": "25544"}'
```

### Get Available Satellites (Formatted Table)
```bash
curl http://localhost:8000/satellites?format=table
```

### Enable Tracking
```bash
curl -X POST http://localhost:8000/tracking/enable
```

### Toggle Laser
```bash
curl -X POST http://localhost:8000/laser/toggle \
  -H "Content-Type: application/json" \
  -d '{"state": null}'
```

### Set Default Target
```bash
curl -X POST http://localhost:8000/default-target \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "satellite",
    "target_value": "ISS"
  }'
```

### Get System Status
```bash
curl http://localhost:8000/status
```

---

## Notes for Frontend Developers

1. **Tracking Updates**: When tracking is enabled, the system automatically updates motor positions at the configured frequency (default: 5 Hz). The frontend should poll `/status` periodically to get current state.

2. **Motor Movement**: Motor movements may take time to complete. The system prevents overlapping movements, so rapid successive commands may be queued.

3. **Satellite Availability**: Only preloaded satellites are available. Use `GET /satellites` to see what's available. Satellites are preloaded on startup from the "visual" group (100 brightest satellites).

4. **Group Tracking**: The `/target/nearest-group` endpoint enables automatic body switching. The system will stick to a body for a configurable duration (default: 60 seconds) before rechecking for better bodies.

5. **Error Recovery**: If a target position can't be calculated (e.g., satellite below horizon, network issues), the API will return appropriate error codes. The frontend should handle these gracefully.

6. **Real-time Updates**: For real-time updates, consider using WebSockets or polling `/status` at regular intervals (e.g., every 200-500ms).

---

## Interactive API Documentation

FastAPI provides interactive API documentation at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

These provide interactive testing interfaces and detailed schema information.

---

## Version History

- **v1.0** - Initial API specification
  - All pointing endpoints
  - Laser control
  - Tracking control
  - Satellite management
  - Default body management

