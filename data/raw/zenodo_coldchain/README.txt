# Cold Chain Monitoring Dataset — README

## Title
Cold Chain Monitoring Dataset: Temperature, Humidity and Vibration Data
for TinyML Classification on ESP32 CAM

## Authors
- Gorka Manzanares López-Ocaña (Universidad Politécnica de Madrid, UPM)
- Ascensión López Vargas (Supervisor, UPM)

## Associated Work
This dataset was generated as part of the Master's Thesis:
"Internet de las Cosas e Inteligencia Artificial Aplicados a la Cadena de Frío"
Master in Automation and Robotics — Universidad Politécnica de Madrid (UPM), 2026.

## Description
This dataset contains sensor readings collected for training two TinyML
classification models deployed on ESP32 CAM microcontrollers, as part of
a cold chain monitoring system.

It includes two subsets:
1. Temperature & Humidity (DHT22 sensor): readings under correct conditions
   and anomalous scenarios (open door, rising temperature).
2. Vibrations (MPU6050 accelerometer, axes X/Y/Z): readings under three
   transport scenarios: normal, dangerous vibration and sudden shock.

Data was collected in a controlled laboratory environment using a thermal
insulated box, sampled at defined intervals and labeled for supervised
classification.

## File Structure
temperature_humidity/   — CSV files for each temperature/humidity scenario (normal, dooropen). There is a second database, file 2nd_experiment, with results obtained from measurements taken with the sensor in a refrigerator. The range of the data obtained is different from the other files.
vibrations/             — CSV files for each vibration scenario (normal, dangermove, shock)

## Data Format
CSV files with headers. Columns vary by subset:
- Temperature: timestamp, temperature (°C), humidity (%)
- Vibrations: timestamp, accX (m/s²), accY (m/s²), accZ (m/s²)

## License
Creative Commons Attribution 4.0 International (CC BY 4.0)
You are free to share and adapt the data, provided appropriate credit is given.

## Date of Collection
November - December 2025