# IOT Car System

## AWS Domain  
- [autosiren.store](http://autosiren.store)  
- [www.autosiren.store](http://www.autosiren.store)  

---

## Database Schema  

### Users Table
```sql

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    google_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
### Cars Table
CREATE TABLE cars (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    model VARCHAR(100),
    license_plate VARCHAR(20),
    year INT,
    color VARCHAR(50),
    engine VARCHAR(100),
    transmission VARCHAR(50),
    drive_type VARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

### Sensors Table
CREATE TABLE sensor_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    motion_status ENUM('detected', 'clear') NOT NULL,
    temperature FLOAT,
    humidity FLOAT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    device_id VARCHAR(50) DEFAULT 'raspberry-pi'
);

### Connect an instance using AWS to run it 