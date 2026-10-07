const mobileMenuBtn = document.getElementById("mobileMenuBtn");
const navigation = document.querySelector(".nav-links");

if (mobileMenuBtn && navigation) {
    mobileMenuBtn.addEventListener("click", function () {
        navigation.classList.toggle("mobile-open");
        mobileMenuBtn.setAttribute("aria-expanded", navigation.classList.contains("mobile-open"));
    });
}

/* ─── LOCATION PICKER (Homepage) ──────────────────────────────────── */
const locationTrigger = document.getElementById("locationTrigger");
const locationPopup = document.getElementById("locationPopup");
const locationPopupClose = document.getElementById("locationPopupClose");
const locationManualInput = document.getElementById("locationManualInput");
const locationApply = document.getElementById("locationApply");
const locationUseCurrent = document.getElementById("useCurrentLocation");
const locationExamples = document.getElementById("locationExamples");
const locationMessage = document.getElementById("locationMessage");
const locationInput = document.getElementById("location");

function showLocationMessage(text) {
    if (locationMessage) {
        locationMessage.textContent = text;
        locationMessage.hidden = false;
    }
}

function clearLocationMessage() {
    if (locationMessage) {
        locationMessage.hidden = true;
        locationMessage.textContent = "";
    }
}

function openLocationPopup() {
    if (locationPopup) {
        locationPopup.hidden = false;
        if (locationTrigger) locationTrigger.setAttribute("aria-expanded", "true");
        if (locationManualInput) locationManualInput.focus();
    }
}

function closeLocationPopup() {
    if (locationPopup) {
        locationPopup.hidden = true;
        if (locationTrigger) locationTrigger.setAttribute("aria-expanded", "false");
    }
}

function applyLocation(value) {
    if (!value) return;
    if (locationInput) locationInput.value = value;
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

    if (locationInput) {
        locationInput.value = "Current Location";
    }
    closeLocationPopup();
}

function onLocationError(error) {
    if (error.code === 1) {
        showLocationMessage("Location access was denied. You can enter your location manually. To re-enable, click the lock icon in your browser's address bar and allow location access.");
    } else if (error.code === 2) {
        showLocationMessage("Unable to detect your location. Please enter your area manually.");
    } else if (error.code === 3) {
        showLocationMessage("Location request timed out. Please try again or enter your area manually.");
    } else {
        showLocationMessage("An unknown error occurred. Please enter your area manually.");
    }
}

if (locationTrigger && locationPopup) {
    const togglePopup = function (event) {
        event.preventDefault();
        event.stopPropagation();
        if (locationPopup.hidden) {
            clearLocationMessage();
            openLocationPopup();
        } else {
            closeLocationPopup();
        }
    };
    locationTrigger.addEventListener("click", togglePopup);
    if (locationInput) {
        locationInput.addEventListener("click", function(event) {
            event.stopPropagation();
            if (locationPopup.hidden) {
                clearLocationMessage();
                openLocationPopup();
            }
        });
    }
}

if (locationPopup) {
    locationPopup.addEventListener("click", function (event) {
        event.stopPropagation();
    });
}

if (locationPopupClose) {
    locationPopupClose.addEventListener("click", function () {
        closeLocationPopup();
    });
}

if (locationExamples && locationManualInput) {
    locationExamples.addEventListener("click", function (event) {
        const chip = event.target.closest(".location-chip");
        if (!chip) return;
        locationManualInput.value = chip.textContent.trim();
        clearLocationMessage();
    });
}

if (locationApply && locationManualInput) {
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
            if (locationApply) locationApply.click();
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
    if (!locationPopup || locationPopup.hidden) return;
    if (locationPopup.contains(event.target) || locationTrigger.contains(event.target)) return;
    closeLocationPopup();
});

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && locationPopup && !locationPopup.hidden) {
        closeLocationPopup();
    }
});