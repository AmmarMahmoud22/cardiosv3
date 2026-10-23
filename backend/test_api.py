import requests
import json

# Test root endpoint
print("Testing root endpoint...")
response = requests.get('http://127.0.0.1:49232/')
print(f"Root endpoint response: {response.json()}\n")

# Test prediction endpoint
print("Testing prediction endpoint...")
test_data = {
    "BMI": 25,
    "Smoking": "No",
    "AlcoholDrinking": "No",
    "Stroke": "No",
    "PhysicalHealth": 0,
    "MentalHealth": 0,
    "DiffWalking": "No",
    "Sex": "Male",
    "AgeCategory": "18-24",
    "Race": "White",
    "Diabetic": "No",
    "PhysicalActivity": "Yes",
    "GenHealth": "Very good",
    "SleepTime": 7,
    "Asthma": "No",
    "KidneyDisease": "No",
    "SkinCancer": "No"
}

response = requests.post('http://127.0.0.1:49232/predict', json=test_data)
print(f"Prediction endpoint response: {response.json()}")
