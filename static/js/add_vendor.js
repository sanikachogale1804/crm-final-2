// static/js/add_vendor.js

document.getElementById("vendorForm").addEventListener("submit", async function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    const data = Object.fromEntries(formData.entries());

    // Optional: remove empty fields before sending
    Object.keys(data).forEach(key => {
        if (data[key] === "") delete data[key];
    });

    try {
        const response = await fetch("/api/vendors", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();
        const messageDiv = document.getElementById("message");

        if (result.success) {
            messageDiv.style.color = "green";
            messageDiv.innerText = `Vendor added successfully! Code: ${result.vendor_code}`;
            this.reset();
        } else {
            messageDiv.style.color = "red";
            messageDiv.innerText = `Error: ${result.message}`;
        }
    } catch (err) {
        console.error("Fetch error:", err);
        document.getElementById("message").style.color = "red";
        document.getElementById("message").innerText = `Error: ${err.message}`;
    }
});
