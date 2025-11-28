// static/js/counter.js
const counterElement = document.getElementById('counter');

async function updateCounter() {
    try {
        // 1. Call your API Gateway
        const response = await fetch('https://t0x8ig4uml.execute-api.us-east-1.amazonaws.com/visitors');
        
        // 2. Extract the number from the JSON response
        const data = await response.json();
        
        // 3. Update the HTML
        counterElement.innerHTML = `Visitor Count: ${data}`;
    } catch (error) {
        console.error("Error fetching visitor count:", error);
        counterElement.innerHTML = "Visitor Count: --";
    }
}

updateCounter();