const searchInput = document.getElementById("searchInput");
const locationInput = document.getElementById("locationInput");
const searchButton = document.getElementById("searchButton");
const doctorCards = document.querySelectorAll(".doctor-card");
const specializationFilters = document.querySelectorAll(".specialization-filter");
const locationFilters = document.querySelectorAll(".location-filter");
const experienceFilters = document.querySelectorAll('input[name="experience"]');
const doctorCount = document.getElementById("doctorCount");
const noResults = document.querySelector(".no-results");
const clearFilters = document.getElementById("clearFilters");

function filterDoctors() {
    const searchValue = searchInput.value.toLowerCase();
    const locationValue = locationInput.value.toLowerCase();

    const selectedSpecializations = Array.from(specializationFilters)
        .filter(filter => filter.checked)
        .map(filter => filter.value.toLowerCase());
    const selectedLocations = Array.from(locationFilters)
        .filter(filter => filter.checked)
        .map(filter => filter.value.toLowerCase());
    const selectedExperience = document.querySelector('input[name="experience"]:checked').value;

    let visibleDoctors = 0;

    doctorCards.forEach(function (card) {
        const name = card.dataset.name.toLowerCase();
        const specialization = card.dataset.specialization.toLowerCase();
        const location = card.dataset.location.toLowerCase();
        const experience = Number(card.dataset.experience);

        const matchesSearch = name.includes(searchValue) || specialization.includes(searchValue);
        const matchesLocation = location.includes(locationValue);
        const matchesSelectedLocation = selectedLocations.length === 0 ||
            selectedLocations.some(value => location.includes(value));
        const matchesSpecialization = selectedSpecializations.length === 0 ||
            selectedSpecializations.some(value => specialization.includes(value));

        let matchesExperience = true;
        if (selectedExperience === "1-5") {
            matchesExperience = experience >= 1 && experience <= 5;
        } else if (selectedExperience === "5-10") {
            matchesExperience = experience >= 5 && experience <= 10;
        } else if (selectedExperience === "10+") {
            matchesExperience = experience >= 10;
        }

        if (matchesSearch && matchesLocation && matchesSelectedLocation &&
            matchesSpecialization && matchesExperience) {
            card.style.display = "grid";
            visibleDoctors++;
        } else {
            card.style.display = "none";
        }
    });

    doctorCount.textContent = visibleDoctors;
    noResults.style.display = visibleDoctors === 0 ? "block" : "none";
}

if (searchButton) searchButton.addEventListener("click", filterDoctors);
if (searchInput) searchInput.addEventListener("input", filterDoctors);
if (locationInput) locationInput.addEventListener("input", filterDoctors);

specializationFilters.forEach(filter => filter.addEventListener("change", filterDoctors));
locationFilters.forEach(filter => filter.addEventListener("change", filterDoctors));
experienceFilters.forEach(filter => filter.addEventListener("change", filterDoctors));

if (clearFilters) clearFilters.addEventListener("click", function () {
    searchInput.value = "";
    locationInput.value = "";
    specializationFilters.forEach(filter => { filter.checked = false; });
    locationFilters.forEach(filter => { filter.checked = false; });
    document.querySelector('input[name="experience"][value="all"]').checked = true;
    filterDoctors();
});

filterDoctors();

// ─── LOCATION PICKER ─────────────────────────────────────────────
const locationTrigger = document.getElementById("locationTrigger");
const locationPopup = document.getElementById("locationPopup");
const locationPopupClose = document.getElementById("locationPopupClose");
const locationManualInput = document.getElementById("locationManualInput");
const locationApply = document.getElementById("locationApply");
const locationUseCurrent = document.getElementById("useCurrentLocation");
const locationExamples = document.getElementById("locationExamples");
const locationMessage = document.getElementById("locationMessage");

function showLocationMessage(text) {
    locationMessage.textContent = text;
    locationMessage.hidden = false;
}

function clearLocationMessage() {
    locationMessage.hidden = true;
    locationMessage.textContent = "";
}

function openLocationPopup() {
    locationPopup.hidden = false;
    locationTrigger.setAttribute("aria-expanded", "true");
    locationManualInput.focus();
}

function closeLocationPopup() {
    locationPopup.hidden = true;
    locationTrigger.setAttribute("aria-expanded", "false");
}

function applyLocation(value) {
    if (!value) return;
    locationInput.value = value;
    filterDoctors();
    closeLocationPopup();
}

function distanceInKm(lat1, lon1, lat2, lon2) {
    const toRad = deg => deg * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function nearestClinicCity(latitude, longitude) {
    const node = document.getElementById("clinicLocations");
    if (!node) return null;
    let clinics;
    try {
        clinics = JSON.parse(node.textContent);
    } catch (error) {
        return null;
    }
    let best = null;
    let bestDistance = Infinity;
    clinics.forEach(function (entry) {
        const distance = distanceInKm(latitude, longitude, Number(entry[1]), Number(entry[2]));
        if (distance < bestDistance) {
            bestDistance = distance;
            best = entry[0];
        }
    });
    return best;
}

function onLocationSuccess(position) {
    const latitude = position.coords.latitude;
    const longitude = position.coords.longitude;
    const nearest = nearestClinicCity(latitude, longitude);

    if (nearest) {
        applyLocation(nearest);
        return;
    }

    locationInput.value = "Current Location";
    filterDoctors();
    closeLocationPopup();
}

function onLocationError(error) {
    if (error.code === 1) {
        showLocationMessage("Location access was denied. You can enter your location manually.");
    } else {
        showLocationMessage("Unable to detect your location. Please enter your area manually.");
    }
}

if (locationTrigger) {
    locationTrigger.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        if (locationPopup.hidden) {
            clearLocationMessage();
            openLocationPopup();
        } else {
            closeLocationPopup();
        }
    });
}

if (locationPopup) {
    locationPopup.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
    });
    locationPopup.addEventListener("submit", function (event) {
        event.preventDefault();
    });
}

if (locationPopupClose) {
    locationPopupClose.addEventListener("click", function () {
        closeLocationPopup();
    });
}

if (locationExamples) {
    locationExamples.addEventListener("click", function (event) {
        const chip = event.target.closest(".location-chip");
        if (!chip) return;
        locationManualInput.value = chip.textContent.trim();
        clearLocationMessage();
    });
}

if (locationApply) {
    locationApply.addEventListener("click", function () {
        const value = locationManualInput.value.trim();
        if (!value) {
            showLocationMessage("Please enter an area or locality.");
            return;
        }
        applyLocation(value);
    });
}

if (locationManualInput) {
    locationManualInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            locationApply.click();
        }
    });
    locationManualInput.addEventListener("input", clearLocationMessage);
}

if (locationUseCurrent) {
    locationUseCurrent.addEventListener("click", function () {
        clearLocationMessage();

        if (!navigator || !navigator.geolocation) {
            showLocationMessage("Location detection is not supported. Please enter your area manually.");
            return;
        }

        showLocationMessage("Requesting your location...");
        locationUseCurrent.disabled = true;

        navigator.geolocation.getCurrentPosition(
            onLocationSuccess,
            onLocationError,
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
        );

        setTimeout(function () {
            locationUseCurrent.disabled = false;
        }, 1200);
    });
}

document.addEventListener("click", function (event) {
    if (locationPopup.hidden) return;
    if (locationPopup.contains(event.target) || locationTrigger.contains(event.target)) return;
    closeLocationPopup();
});

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !locationPopup.hidden) {
        closeLocationPopup();
    }
});