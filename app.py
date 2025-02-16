from flask import Flask, request, jsonify
from Script import predict_snow_day  # Import prediction function from Script.py
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allows frontend to call this backend

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json()
    location = data.get("location")
    date = data.get("date")
    
    if not location or not date:
        return jsonify({"error": "Missing location or date"}), 400

    percentage = predict_snow_day(location, date)
    
    return jsonify({"percentage": percentage})

if __name__ == "__main__":
    app.run(debug=True)
