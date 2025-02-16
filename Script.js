function getPrediction() {
    let location = document.getElementById("location").value;
    let date = document.getElementById("date").value;

    if (!location || !date) {
        alert("Please enter both location and date.");
        return;
    }

    fetch("http://127.0.0.1:5000/predict", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ location: location, date: date })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById("result").innerText = 
            `The Percentage Chance Of A Snow Day In ${location} on ${date} is ${data.percentage}%`;
    })
    .catch(error => console.error("Error:", error));
}
