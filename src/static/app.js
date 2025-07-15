document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const messageDiv = document.getElementById("message");

  // Function to fetch activities from API
  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      const activities = await response.json();

      activitiesList.innerHTML = "";

      // Populate activities list
      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";

        const spotsLeft = details.max_participants - details.participants.length;

        activityCard.innerHTML = `
          <h4>${name}</h4>
          <p>${details.description}</p>
          <p><strong>Schedule:</strong> ${details.schedule}</p>
          <p><strong>Availability:</strong> ${spotsLeft} spots left</p>
          <div class="participants-section">
            <strong>Participants:</strong>
            <ul class="participants-list">
              ${details.participants.length > 0
                ? details.participants.map(email => `
                  <li class="participant-row">
                    <span>${email}</span>
                    <span class="delete-participant" title="Unregister" data-activity="${name}" data-email="${email}">🗑️</span>
                  </li>
                `).join("")
                : `<li><em>No participants yet</em></li>`}
            </ul>
          </div>
        `;

        activitiesList.appendChild(activityCard);

        // Add option to select dropdown
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });

      document.querySelectorAll('.delete-participant').forEach(icon => {
        icon.addEventListener('click', async (e) => {
          const activity = icon.getAttribute('data-activity');
          const email = icon.getAttribute('data-email');
          if (confirm(`Unregister ${email} from ${activity}?`)) {
            try {
              const res = await fetch(`/activities/${encodeURIComponent(activity)}/unregister`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
              });
              if (!res.ok) {
                const err = await res.json();
                alert(err.detail || 'Failed to unregister');
              } else {
                fetchActivities();
              }
            } catch (err) {
              alert('Error unregistering participant');
            }
          }
        });
      });
    } catch (error) {
      activitiesList.innerHTML = "<p>Failed to load activities. Please try again later.</p>";
      console.error("Error fetching activities:", error);
    }
  }

  // Handle form submission
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const activity = document.getElementById("activity").value;

    try {
      const response = await fetch(`/activities/${encodeURIComponent(activity)}/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email })
      });

      if (!response.ok) {
        const error = await response.json();
        messageDiv.textContent = error.detail || "Failed to sign up.";
        messageDiv.className = "error";
      } else {
        messageDiv.textContent = "Successfully signed up!";
        messageDiv.className = "success";
        fetchActivities(); // Refresh the activity list dynamically
      }
    } catch (error) {
      messageDiv.textContent = "An error occurred. Please try again later.";
      messageDiv.className = "error";
    }
  });

  // Initialize app
  fetchActivities();
});
